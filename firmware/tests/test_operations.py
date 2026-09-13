"""The writable half: registry, validation, queue, cooldowns, and the executor's honesty."""

from __future__ import annotations

import pytest

from crowe import operations as ops
from crowe import watchdog


class FakePins:
    def __init__(self, real=True):
        self._real = real
        self.states: dict[str, bool] = {}
        self.pulses = 0

    def set(self, color, on):
        self.states[color] = bool(on)

    def pulse_reset(self):
        self.pulses += 1


@pytest.fixture
def q(tmp_path):
    conn = ops.open_queue(tmp_path / "db" / "operations.sqlite")
    yield conn
    conn.close()


def test_registry_names_every_constraint_enforcer_and_matches_the_watchdog_hold():
    for op_id, spec in ops.REGISTRY.items():
        assert spec["title"] and spec["effect"], op_id
        for c in spec["constraints"]:
            assert c["enforced_by"], (op_id, c)
    assert ops.UPLINK_RESET_HOLD_S == watchdog.HOTSPOT_RESET_HOLD_S


def test_validate_bounds_defaults_and_refuses_unknowns():
    assert ops.validate("indicator.identify", {}) == {"seconds": ops.IDENTIFY_DEFAULT_S}
    assert ops.validate("indicator.identify", {"seconds": 3})["seconds"] == 3.0
    assert ops.validate("uplink.reset", None) == {}
    with pytest.raises(ops.OperationError) as e:
        ops.validate("indicator.identify", {"seconds": 31})
    assert e.value.code == "bad_args" and "between 1 and 30" in e.value.detail
    with pytest.raises(ops.OperationError):
        ops.validate("indicator.identify", {"seconds": "nan"})
    with pytest.raises(ops.OperationError) as e:
        ops.validate("indicator.identify", {"colour": "red"})
    assert "not an argument" in e.value.detail
    with pytest.raises(ops.OperationError) as e:
        ops.validate("laser.power", {"watts": 9000})
    assert e.value.code == "unknown_operation" and e.value.status == 404
    with pytest.raises(ops.OperationError):
        ops.validate("uplink.reset", [1, 2])


def test_queue_roundtrip_claim_finish_recent(q):
    row = ops.enqueue(q, "indicator.identify", {"seconds": 5}, "test", 1000.0)
    assert row["status"] == "queued" and row["args"] == {"seconds": 5.0} and row["id"].startswith("op-")
    assert ops.get(q, row["id"])["requested_by"] == "test"
    claimed = ops.claim(q, 1001.0)
    assert claimed["id"] == row["id"] and claimed["status"] == "running" and claimed["ts_started"] == 1001.0
    assert ops.claim(q, 1001.5) is None, "one at a time"
    ops.finish(q, row["id"], "done", {"simulated": False}, 1002.0)
    done = ops.get(q, row["id"])
    assert done["status"] == "done" and done["result"] == {"simulated": False} and done["ts_finished"] == 1002.0
    assert [r["id"] for r in ops.recent(q)] == [row["id"]]
    with pytest.raises(ValueError):
        ops.finish(q, row["id"], "queued", {}, 1003.0)


def test_cooldown_counts_from_the_last_done_run(q):
    assert ops.cooldown_remaining(q, "uplink.reset", 0.0) == 0.0
    r = ops.enqueue(q, "uplink.reset", {}, "t", 100.0)
    ops.claim(q, 100.0)
    ops.finish(q, r["id"], "done", {}, 103.0)
    assert ops.cooldown_remaining(q, "uplink.reset", 200.0) == pytest.approx(ops.UPLINK_RESET_COOLDOWN_S - 97.0)
    assert ops.cooldown_remaining(q, "uplink.reset", 103.0 + ops.UPLINK_RESET_COOLDOWN_S) == 0.0
    # A rejected run does not start a cooldown.
    r2 = ops.enqueue(q, "indicator.identify", {}, "t", 100.0)
    ops.claim(q, 100.0)
    ops.finish(q, r2["id"], "rejected", {"error": "x"}, 101.0)
    assert ops.cooldown_remaining(q, "indicator.identify", 102.0) == 0.0


def test_unclaimed_requests_expire_and_interrupted_runs_become_unknown(q):
    old = ops.enqueue(q, "indicator.identify", {}, "t", 0.0)
    fresh = ops.enqueue(q, "indicator.identify", {}, "t", 50.0)
    claimed = ops.claim(q, 0.0 + ops.QUEUE_TTL_S + 1)
    assert claimed["id"] == fresh["id"], "the stale one was skipped"
    assert ops.get(q, old["id"])["status"] == "expired"
    # The executor dies mid-run; the next executor cannot say what happened.
    assert ops.recover(q, 70.0) == 1
    assert ops.get(q, fresh["id"])["status"] == "unknown"


def test_executor_identify_sets_a_window_and_reset_pulses_the_pins(q):
    clock = {"t": 1000.0}
    pins = FakePins(real=True)
    ex = ops.Executor(q, pins, gpio_available=True, now=lambda: clock["t"])
    r = ops.enqueue(q, "indicator.identify", {"seconds": 4}, "t", clock["t"])
    out = ex.tick()
    assert out["id"] == r["id"] and out["status"] == "done"
    assert out["result"] == {"simulated": False, "blinking_until": 1004.0}
    assert ex.identifying is True
    clock["t"] = 1004.5
    assert ex.identifying is False
    ops.enqueue(q, "uplink.reset", {}, "t", clock["t"])
    out2 = ex.tick()
    assert out2["status"] == "done" and pins.pulses == 1 and ex.last_reset_ts == 1004.5
    assert out2["result"]["held_s"] == ops.UPLINK_RESET_HOLD_S
    assert ex.tick() is None


def test_executor_enforces_the_cooldown_even_for_a_request_queued_earlier(q):
    clock = {"t": 0.0}
    pins = FakePins()
    ex = ops.Executor(q, pins, gpio_available=True, now=lambda: clock["t"])
    a = ops.enqueue(q, "uplink.reset", {}, "t", 0.0)
    b = ops.enqueue(q, "uplink.reset", {}, "t", 0.1)
    assert ex.tick()["id"] == a["id"]
    clock["t"] = 1.0
    out = ex.tick()
    assert out["id"] == b["id"] and out["status"] == "rejected"
    assert out["result"]["error"] == "cooldown" and out["result"]["retry_after_s"] > 0
    assert pins.pulses == 1, "the second request never reached the pins"


def test_executor_without_gpio_rejects_unless_simulating(q):
    pins = FakePins(real=False)
    ex = ops.Executor(q, pins, gpio_available=False, now=lambda: 10.0)
    ops.enqueue(q, "indicator.identify", {}, "t", 10.0)
    out = ex.tick()
    assert out["status"] == "rejected" and out["result"]["error"] == "unavailable"
    assert ex.identifying is False, "a rejected identify does not blink anything"
    ex2 = ops.Executor(q, pins, gpio_available=False, simulate=True, now=lambda: 20.0)
    ops.enqueue(q, "uplink.reset", {}, "t", 20.0)
    out2 = ex2.tick()
    assert out2["status"] == "done" and out2["result"]["simulated"] is True and pins.pulses == 0


def test_token_matches_is_strict_and_missing_file_is_false(tmp_path):
    path = tmp_path / "operator.token"
    assert ops.token_matches("anything", path) is False
    tok = ops.make_token()
    assert tok.startswith("cso-") and len(tok) > 20
    path.write_text(tok + "\n")
    assert ops.token_matches(tok, path) is True
    assert ops.token_matches(" " + tok + " ", path) is True
    assert ops.token_matches(tok[:-1], path) is False
    assert ops.token_matches("", path) is False
    assert ops.token_matches(None, path) is False


def test_watchdog_loop_blinks_all_three_while_identifying_and_restores_after(tmp_path, tmp_config, monkeypatch):
    from crowe import config
    cfg = config.load()
    monkeypatch.setattr(watchdog, "current_uplink", lambda: None)
    clock = {"t": 0.0}
    pins = FakePins(real=True)
    q = ops.open_queue(tmp_path / "ops.sqlite")
    ex = ops.Executor(q, pins, gpio_available=True, now=lambda: clock["t"])
    ops.enqueue(q, "indicator.identify", {"seconds": 2}, "t", 0.0)
    seen = []

    def fake_sleep(_s):
        seen.append(dict(pins.states))
        clock["t"] += 1.0

    status = tmp_path / "run" / "status.json"
    watchdog.run(cfg, pins, status, ex, max_ticks=4, sleep=fake_sleep, install_signals=False)
    # tick 1 (t=0): claimed, blinking until t=2: all three follow the heartbeat (True)
    assert seen[0] == {"green": True, "amber": True, "red": True}
    # tick 2 (t=1): still identifying, heartbeat flipped
    assert seen[1] == {"green": False, "amber": False, "red": False}
    # tick 3 (t=2): window over; amber released, red shows the real fault (no uplink)
    assert seen[2]["amber"] is False and seen[2]["red"] is True and seen[2]["green"] is True
    import json
    st = json.loads(status.read_text())
    assert st["gpio"] is True and st["operations"] is True and st["identifying"] is False
