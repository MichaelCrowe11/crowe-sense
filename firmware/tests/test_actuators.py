"""The exhaust fan design: exists only when declared, bounded, interlocked, fail-safe."""

from __future__ import annotations

import pytest

from crowe import config, descriptor
from crowe import operations as ops
from crowe.config import ActuatorConfig


class FakePins:
    def __init__(self):
        self._real = True
        self.actuator_calls: list[tuple[str, bool]] = []
        self.pulses = 0

    def set(self, color, on):
        pass

    def set_actuator(self, name, on):
        self.actuator_calls.append((name, bool(on)))

    def pulse_reset(self):
        self.pulses += 1


FAN = ActuatorConfig(name="exhaust_fan", kind="exhaust_fan", pin=24, max_on_s=900, min_off_s=120, min_co2_ppm=0)


@pytest.fixture
def q(tmp_path):
    conn = ops.open_queue(tmp_path / "ops.sqlite")
    yield conn
    conn.close()
    ops.configure_actuators({})


def _executor(q, clock, reading, fan=FAN, gpio=True):
    pins = FakePins()
    ex = ops.Executor(q, pins, gpio_available=gpio, now=lambda: clock["t"],
                      actuators={fan.name: fan}, reading=reading)
    return ex, pins


def test_fan_operation_exists_only_when_declared():
    ops.configure_actuators({})
    assert "ventilation.exhaust_fan" not in ops.active_registry()
    with pytest.raises(ops.OperationError):
        ops.validate("ventilation.exhaust_fan", {"state": "on"})
    ops.configure_actuators({"exhaust_fan": FAN})
    spec = ops.active_registry()["ventilation.exhaust_fan"]
    assert spec["actuator"] == {"name": "exhaust_fan", "kind": "exhaust_fan", "pin": 24}
    kinds = [c["kind"] for c in spec["constraints"]]
    assert kinds == ["enum", "bound", "max_on_s", "min_off_s", "interlock", "fail_safe"]
    assert all(c["enforced_by"] for c in spec["constraints"])
    assert ops.validate("ventilation.exhaust_fan", {"state": "ON"}) == {"state": "on", "seconds": 300.0}
    assert ops.validate("ventilation.exhaust_fan", {"state": "off"})["state"] == "off"
    with pytest.raises(ops.OperationError) as e:
        ops.validate("ventilation.exhaust_fan", {"state": "on", "seconds": 901})
    assert "between 30 and 900" in e.value.detail
    with pytest.raises(ops.OperationError):
        ops.validate("ventilation.exhaust_fan", {"state": "auto"})
    with pytest.raises(ops.OperationError):
        ops.validate("ventilation.exhaust_fan", {})
    ops.configure_actuators({})


def test_operator_limit_cannot_exceed_the_kinds_ceiling():
    loose = ActuatorConfig(name="exhaust_fan", kind="exhaust_fan", pin=24, max_on_s=99999)
    ops.configure_actuators({"exhaust_fan": loose})
    spec = ops.active_registry()["ventilation.exhaust_fan"]
    assert spec["args"]["seconds"]["maximum"] == ops.EXHAUST_FAN_MAX_ON_CEILING_S
    ops.configure_actuators({})


def test_safe_startup_turns_the_fan_off_and_applies_the_spacing(q):
    clock = {"t": 1000.0}
    ex, pins = _executor(q, clock, reading=lambda m: (1400.0, 5.0))
    assert pins.actuator_calls == [("exhaust_fan", False)], "off at start, whatever the pin was doing"
    ops.enqueue(q, "ventilation.exhaust_fan", {"state": "on", "seconds": 60}, "t", clock["t"])
    out = ex.tick()
    assert out["status"] == "rejected" and out["result"]["error"] == "cooldown", "just after a start counts as just after an off"
    clock["t"] = 1000.0 + FAN.min_off_s
    ops.enqueue(q, "ventilation.exhaust_fan", {"state": "on", "seconds": 60}, "t", clock["t"])
    out = ex.tick()
    assert out["status"] == "done" and out["result"]["state"] == "on"
    assert out["result"]["off_at"] == clock["t"] + 60 and out["result"]["co2_ppm"] == 1400.0
    assert pins.actuator_calls[-1] == ("exhaust_fan", True)


def test_auto_off_happens_on_the_tick_after_the_window_and_stop_turns_it_off(q):
    clock = {"t": 5000.0}
    ex, pins = _executor(q, clock, reading=lambda m: (1400.0, 5.0))
    clock["t"] = 5000.0 + FAN.min_off_s
    ops.enqueue(q, "ventilation.exhaust_fan", {"state": "on", "seconds": 30}, "t", clock["t"])
    assert ex.tick()["status"] == "done"
    assert ex.actuator_state["exhaust_fan"] is True
    t_on = clock["t"]
    clock["t"] = t_on + 29.0
    ex.tick()
    assert ex.actuator_state["exhaust_fan"] is True, "still inside the window"
    clock["t"] = t_on + 30.0
    ex.tick()
    assert ex.actuator_state["exhaust_fan"] is False and pins.actuator_calls[-1] == ("exhaust_fan", False)
    assert ex.actuator_off_ts["exhaust_fan"] == t_on + 30.0
    # on again, then the process ends: stop() leaves nothing running
    clock["t"] = t_on + 30.0 + FAN.min_off_s
    ops.enqueue(q, "ventilation.exhaust_fan", {"state": "on", "seconds": 600}, "t", clock["t"])
    assert ex.tick()["status"] == "done"
    ex.stop()
    assert ex.actuator_state["exhaust_fan"] is False and pins.actuator_calls[-1] == ("exhaust_fan", False)


def test_off_is_immediate_never_refused_and_does_not_restart_the_clock(q):
    clock = {"t": 100.0}
    ex, pins = _executor(q, clock, reading=None)          # no window at all
    clock["t"] = 130.0
    ops.enqueue(q, "ventilation.exhaust_fan", {"state": "off"}, "t", clock["t"])
    out = ex.tick()
    assert out["status"] == "done" and out["result"]["state"] == "off"
    assert ex.actuator_off_ts["exhaust_fan"] == 100.0, "the start's off stamp stands; an off while off is not a new off"


def test_interlocks_refuse_blind_stale_and_below_the_floor(q):
    clock = {"t": 10_000.0}
    ex, _ = _executor(q, clock, reading=None)
    clock["t"] += FAN.min_off_s
    ops.enqueue(q, "ventilation.exhaust_fan", {"state": "on"}, "t", clock["t"])
    out = ex.tick()
    assert out["status"] == "rejected" and out["result"]["error"] == "interlock_unverifiable"

    ex2, _ = _executor(q, clock, reading=lambda m: (1400.0, 400.0))
    clock["t"] += FAN.min_off_s
    ops.enqueue(q, "ventilation.exhaust_fan", {"state": "on"}, "t", clock["t"])
    out = ex2.tick()
    assert out["status"] == "rejected" and out["result"]["error"] == "stale_reading" and "400 s old" in out["result"]["detail"]

    ex3, _ = _executor(q, clock, reading=lambda m: None)
    clock["t"] += FAN.min_off_s
    ops.enqueue(q, "ventilation.exhaust_fan", {"state": "on"}, "t", clock["t"])
    out = ex3.tick()
    assert out["status"] == "rejected" and out["result"]["detail"] == "no co2_ppm reading"

    floor = ActuatorConfig(name="exhaust_fan", kind="exhaust_fan", pin=24, min_co2_ppm=800)
    ex4, pins4 = _executor(q, clock, reading=lambda m: (650.0, 3.0), fan=floor)
    clock["t"] += FAN.min_off_s
    ops.enqueue(q, "ventilation.exhaust_fan", {"state": "on"}, "t", clock["t"])
    out = ex4.tick()
    assert out["status"] == "rejected" and out["result"]["interlock"] == "co2_floor"
    assert ("exhaust_fan", True) not in pins4.actuator_calls, "nothing reached the relay"
    spec = ops.active_registry()["ventilation.exhaust_fan"]
    assert any(c.get("name") == "co2_floor" and c["value"] == 800.0 for c in spec["constraints"])


def test_without_gpio_the_fan_is_never_reported_on(q):
    clock = {"t": 0.0}
    ex, pins = _executor(q, clock, reading=lambda m: (1400.0, 1.0), gpio=False)
    clock["t"] = FAN.min_off_s
    ops.enqueue(q, "ventilation.exhaust_fan", {"state": "on"}, "t", clock["t"])
    out = ex.tick()
    assert out["status"] == "rejected" and out["result"]["error"] == "unavailable"
    assert pins.actuator_calls == [], "a stub never touches a relay"


def test_reading_from_db_reads_the_newest_row_and_ages_it(tmp_path):
    import datetime

    from crowe.db import open_db
    from crowe.sampler import write_batch
    from crowe.sensors.base import Reading
    db = tmp_path / "samples.sqlite"
    conn = open_db(db)
    write_batch(conn, [Reading("2026-09-14T10:00:00.000Z", "scd41", "co2_ppm", 900.0, "ppm"),
                       Reading("2026-09-14T10:00:05.000Z", "scd41", "co2_ppm", 912.0, "ppm")])
    conn.close()
    t0 = datetime.datetime(2026, 9, 14, 10, 0, 35, tzinfo=datetime.UTC).timestamp()
    reading = ops.reading_from_db(db, now=lambda: t0)
    assert reading("co2_ppm") == (912.0, 30.0)
    assert reading("light_lux") is None
    assert ops.reading_from_db(tmp_path / "missing.sqlite", now=lambda: t0)("co2_ppm") is None


def test_config_parses_declared_actuators_and_refuses_unknown_kinds(tmp_config):
    tmp_config.write_text(tmp_config.read_text() + '\n[actuators.exhaust_fan]\npin = 24\nmax_on_s = 600\nmin_co2_ppm = 700\n')
    config.reset_cache()
    cfg = config.load()
    assert cfg.actuators["exhaust_fan"] == ActuatorConfig(name="exhaust_fan", kind="exhaust_fan", pin=24, max_on_s=600.0, min_co2_ppm=700.0)
    doc = descriptor.build(cfg, now=1.0)
    assert doc["actuators"][0]["operation"] == "ventilation.exhaust_fan" and doc["actuators"][0]["limits"]["max_on_s"] == 600.0
    assert any(o["id"] == "ventilation.exhaust_fan" for o in doc["operations"]["list"])
    assert "Actuators: exhaust_fan" in doc["annotations"]["summary"]
    tmp_config.write_text(tmp_config.read_text() + '\n[actuators.laser]\nkind = "laser"\npin = 25\n')
    config.reset_cache()
    with pytest.raises(ValueError, match="kind 'laser'"):
        config.load()
    ops.configure_actuators({})


def test_a_plain_node_describes_no_actuators(tmp_config):
    config.reset_cache()
    doc = descriptor.build(config.load(), now=1.0)
    assert doc["actuators"] == []
    assert "No actuators are wired" in doc["annotations"]["summary"]
    assert not any(o["id"].startswith("ventilation.") for o in doc["operations"]["list"])
