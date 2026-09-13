"""The MCP server: its tools over a fake HTTP node, and one real stdio round trip."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from crowe import api, config, mcp
from crowe.db import open_db

ROOT = Path(__file__).resolve().parents[2]


class FakeNode:
    """Answers the contract paths the tools use; records every call."""

    def __init__(self):
        self.calls = []
        self.status_sequence = ["queued", "done"]
        self.post_status = 202

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append((method, url, dict(headers), body))
        path = url.split("://", 1)[1].split("/", 1)[1]
        if method == "GET" and path == "v1/describe":
            return 200, {"identity": {"node": "cs-a1b2c3"}, "annotations": {"summary": "A node."}}
        if method == "GET" and path == "v1/latest":
            return 200, [
                {"ts": 995.0, "zone": "tent-1", "sensor": "sht45", "metric": "temperature_c", "value": 21.4, "unit": "C", "quality": "ok"},
                {"ts": 995.0, "zone": "tent-1", "sensor": "scd41", "metric": "co2_ppm", "value": 812, "unit": "ppm", "quality": "ok"},
                {"ts": 900.0, "zone": "hood-1", "sensor": "sdp810", "metric": "prefilter_dp_pa", "value": 41, "unit": "Pa", "quality": "stale"},
            ]
        if method == "GET" and path.startswith("v1/history"):
            return 200, {"metric": "co2_ppm", "zone": "tent-1", "unit": "ppm", "points": [[1, 800.0], [2, 820.0], [3, None]]}
        if method == "GET" and path == "v1/operations":
            return 200, {"enabled": True, "operations": [], "recent": []}
        if method == "GET" and path.startswith("v1/operations/op-1"):
            st = self.status_sequence.pop(0) if self.status_sequence else "done"
            return 200, {"id": "op-1", "op": "indicator.identify", "status": st, "result": {"simulated": False} if st == "done" else {}}
        if method == "POST" and path.startswith("v1/operations/"):
            if self.post_status == 202:
                return 202, {"id": "op-1", "op": path.split("/")[-1], "status": "queued", "args": json.loads(body)["args"]}
            return self.post_status, {"error": "cooldown", "detail": "ran recently", "retry_after_s": 42}
        return 404, {"error": "not_found", "detail": path}


def _server(env, node=None):
    node = node or FakeNode()
    return mcp.Server(http=node, env=env, sleep=lambda s: None, now=lambda: 1000.0), node


def _text(reply):
    return reply["result"]["content"][0]["text"], bool(reply["result"].get("isError"))


def test_initialize_and_tools_list():
    srv, _ = _server({"CROWE_SENSE_URL": "http://node:8078"})
    init = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["protocolVersion"] == mcp.PROTOCOL_VERSION and init["result"]["serverInfo"]["name"] == "crowe-sense"
    tools = srv.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    assert [t["name"] for t in tools] == ["describe_device", "read_latest", "read_history", "list_operations", "request_operation"]
    assert srv.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert srv.handle({"jsonrpc": "2.0", "id": 3, "method": "nope"})["error"]["code"] == -32601


def test_reads_go_to_the_direct_node_without_a_bearer():
    srv, node = _server({"CROWE_SENSE_URL": "http://node:8078/"})
    text, err = _text(srv.handle({"id": 1, "method": "tools/call", "params": {"name": "describe_device", "arguments": {}}}))
    assert not err and text.startswith("A node.") and '"cs-a1b2c3"' in text
    assert node.calls[0][1] == "http://node:8078/v1/describe" and "authorization" not in node.calls[0][2]
    text, _ = _text(srv.handle({"id": 2, "method": "tools/call", "params": {"name": "read_latest", "arguments": {"zone": "tent-1"}}}))
    assert "tent-1: co2_ppm = 812 ppm (ok, 5 s ago, scd41)" in text and "hood-1" not in text
    text, _ = _text(srv.handle({"id": 3, "method": "tools/call", "params": {"name": "read_latest", "arguments": {"metric": "nothing"}}}))
    assert text.startswith("no readings match")
    text, _ = _text(srv.handle({"id": 4, "method": "tools/call", "params": {"name": "read_history", "arguments": {"metric": "co2_ppm", "hours": 2}}}))
    assert text.startswith("tent-1 co2_ppm (ppm): 2 buckets, min 800, mean 810, max 820")
    assert "hours=2" in node.calls[-1][1]


def test_cloud_source_reads_with_crowe_id_and_refuses_writes(tmp_path):
    cfgp = tmp_path / "sense.json"
    cfgp.write_text(json.dumps({"source": "cloud", "node": "cs-a1b2c3", "relay": "https://relay.test"}))
    env = {"CROWE_SENSE_CONFIG": str(cfgp)}
    srv, node = _server(env)
    text, err = _text(srv.handle({"id": 1, "method": "tools/call", "params": {"name": "read_latest", "arguments": {}}}))
    assert err and "CROWE_ID_TOKEN" in text
    srv, node = _server({**env, "CROWE_ID_TOKEN": "tok"})
    _text(srv.handle({"id": 1, "method": "tools/call", "params": {"name": "read_latest", "arguments": {}}}))
    assert node.calls[0][1] == "https://relay.test/v1/nodes/cs-a1b2c3/latest" and node.calls[0][2]["authorization"] == "Bearer tok"
    text, err = _text(srv.handle({"id": 2, "method": "tools/call", "params": {"name": "request_operation", "arguments": {"operation": "indicator.identify"}}}))
    assert err and "direct path only" in text and len(node.calls) == 1, "nothing was posted"


def test_request_operation_needs_the_operator_token_then_polls_to_done():
    srv, node = _server({"CROWE_SENSE_URL": "http://node:8078"})
    text, err = _text(srv.handle({"id": 1, "method": "tools/call", "params": {"name": "request_operation", "arguments": {"operation": "indicator.identify"}}}))
    assert err and "CROWE_SENSE_OPERATOR_TOKEN" in text and node.calls == []
    srv, node = _server({"CROWE_SENSE_URL": "http://node:8078", "CROWE_SENSE_OPERATOR_TOKEN": "cso-x", "CROWE_SENSE_OPERATOR": "desktop michael"})
    text, err = _text(srv.handle({"id": 2, "method": "tools/call", "params": {"name": "request_operation", "arguments": {"operation": "indicator.identify", "args": {"seconds": 5}}}}))
    assert not err and text.startswith("indicator.identify op-1: done.")
    post = node.calls[0]
    assert post[0] == "POST" and post[1] == "http://node:8078/v1/operations/indicator.identify"
    assert post[2]["authorization"] == "Bearer cso-x" and post[2]["x-crowe-operator"] == "desktop michael"
    assert json.loads(post[3]) == {"args": {"seconds": 5}}
    assert [c[1] for c in node.calls[1:]] == ["http://node:8078/v1/operations/op-1"] * 2


def test_request_operation_reports_the_nodes_refusal_verbatim():
    node = FakeNode()
    node.post_status = 429
    srv, _ = _server({"CROWE_SENSE_URL": "http://node:8078", "CROWE_SENSE_OPERATOR_TOKEN": "cso-x"}, node)
    text, err = _text(srv.handle({"id": 1, "method": "tools/call", "params": {"name": "request_operation", "arguments": {"operation": "uplink.reset"}}}))
    assert err and text.startswith("error: cooldown: ran recently retry after 42 s")


def test_unconfigured_server_says_how_to_point_it(tmp_path):
    srv, _ = _server({"CROWE_SENSE_CONFIG": str(tmp_path / "missing.json")})
    text, err = _text(srv.handle({"id": 1, "method": "tools/call", "params": {"name": "describe_device", "arguments": {}}}))
    assert err and "CROWE_SENSE_URL" in text


@pytest.fixture
def real_node(tmp_path, tmp_config):
    tmp_config.write_text(tmp_config.read_text() + '\nzone = "tent-1"\n')
    config.reset_cache()
    cfg = config.load()
    open_db(tmp_path / "db" / "samples.sqlite").close()
    srv = api.serve(cfg.db_path, cfg.node_id, cfg.zone, host="127.0.0.1", port=0, ops=api.OperationsService(cfg, status_path=None))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_stdio_round_trip_from_the_checkout_launcher(real_node):
    env = {**os.environ, "CROWE_SENSE_URL": real_node}
    env.pop("CROWE_SENSE_CONFIG", None)
    lines = [json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
             json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
             json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "describe_device", "arguments": {}}})]
    out = subprocess.run([sys.executable, str(ROOT / "mcp_server.py")], input="\n".join(lines) + "\n",
                         capture_output=True, text=True, env=env, timeout=20)
    replies = [json.loads(line) for line in out.stdout.splitlines() if line.strip()]
    assert [r["id"] for r in replies] == [1, 2], out.stderr
    text = replies[1]["result"]["content"][0]["text"]
    assert "Crowe Sense node cs-TEST00" in text and '"write_path": "direct-only"' in text
