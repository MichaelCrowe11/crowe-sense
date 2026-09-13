"""GET /v1/describe and the write door, against a served node with a real queue."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from crowe import api, config, operations
from crowe.db import open_db


@pytest.fixture
def node(tmp_path, tmp_config):
    tmp_config.write_text(tmp_config.read_text() + '\nzone = "tent-1"\n[operations]\nenabled = true\ntoken_path = "' + str(tmp_path / "operator.token") + '"\n')
    config.reset_cache()
    cfg = config.load()
    (tmp_path / "operator.token").write_text("cso-secret\n")
    open_db(tmp_path / "db" / "samples.sqlite").close()
    ops = api.OperationsService(cfg, status_path=tmp_path / "status.json")
    srv = api.serve(cfg.db_path, cfg.node_id, cfg.zone, host="127.0.0.1", port=0, ops=ops)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield {"url": f"http://127.0.0.1:{srv.server_port}", "cfg": cfg, "ops": ops}
    srv.shutdown()


def _call(url, method="GET", body=None, token=None):
    headers = {"accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["content-type"] = "application/json"
    if token:
        headers["authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_describe_and_operations_are_open_reads(node):
    st, d = _call(node["url"] + "/v1/describe")
    assert st == 200 and d["identity"]["node"] == "cs-TEST00" and d["operations"]["enabled"] is True
    st, listing = _call(node["url"] + "/v1/operations")
    assert st == 200 and listing["enabled"] is True and listing["recent"] == []
    assert {o["id"] for o in listing["operations"]} == set(operations.REGISTRY)
    assert listing["cooldowns"] == {"indicator.identify": 0.0, "uplink.reset": 0.0}


def test_write_needs_the_token_before_anything_else(node):
    st, e = _call(node["url"] + "/v1/operations/indicator.identify", "POST", {"args": {"seconds": 5}})
    assert st == 401 and e["error"] == "unauthorized"
    st, e = _call(node["url"] + "/v1/operations/nope.nope", "POST", {}, token="wrong")
    assert st == 401, "a bad token learns nothing about which operations exist"
    st, e = _call(node["url"] + "/v1/operations/nope.nope", "POST", {}, token="cso-secret")
    assert st == 404 and e["error"] == "unknown_operation"
    st, e = _call(node["url"] + "/v1/operations/indicator.identify", "POST", {"args": {"seconds": 99}}, token="cso-secret")
    assert st == 400 and e["error"] == "bad_args"
    assert node["ops"].listing(time.time())["recent"] == [], "nothing refused reached the queue"


def test_accepted_write_is_queued_then_visible_and_cooldown_answers_429(node):
    st, row = _call(node["url"] + "/v1/operations/indicator.identify", "POST", {"args": {"seconds": 5}}, token="cso-secret")
    assert st == 202 and row["status"] == "queued" and row["args"] == {"seconds": 5.0}
    st, got = _call(node["url"] + "/v1/operations/" + row["id"])
    assert st == 200 and got["id"] == row["id"]
    # The watchdog runs it (here: directly), and the cooldown holds the next one.
    q = node["ops"].queue()
    ex = operations.Executor(q, type("P", (), {"set": lambda *a: None, "pulse_reset": lambda self: None})(), gpio_available=True)
    assert ex.tick()["status"] == "done"
    st, e = _call(node["url"] + "/v1/operations/indicator.identify", "POST", {}, token="cso-secret")
    assert st == 429 and e["error"] == "cooldown" and e["retry_after_s"] > 0
    st, listing = _call(node["url"] + "/v1/operations")
    assert listing["recent"][0]["status"] == "done"


def test_disabled_node_refuses_writes_but_still_describes(tmp_path, tmp_config):
    config.reset_cache()
    cfg = config.load()
    assert cfg.operations_enabled is False
    open_db(tmp_path / "db" / "samples.sqlite").close()
    srv = api.serve(cfg.db_path, cfg.node_id, cfg.zone, host="127.0.0.1", port=0, ops=api.OperationsService(cfg, status_path=None))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_port}"
        st, d = _call(url + "/v1/describe")
        assert st == 200 and d["access"]["direct"]["writes"] is False
        st, e = _call(url + "/v1/operations/indicator.identify", "POST", {}, token="anything")
        assert st == 403 and e["error"] == "operations_disabled"
        st, listing = _call(url + "/v1/operations")
        assert st == 200 and listing["enabled"] is False and listing["cooldowns"] == {}
    finally:
        srv.shutdown()
    assert not (tmp_path / "db" / "operations.sqlite").exists(), "a read-only node never opens a queue"
