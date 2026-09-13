"""The node as an MCP server: describe, read, and request an operation, over the
same HTTP contract every other surface uses.

Stdio, newline-delimited JSON-RPC, the dialect the Crowe Logic desktop's MCP client
speaks (initialize, tools/list, tools/call). Stdlib only, so it runs from a checkout
on any machine with Python 3.11: `python3 ~/crowe-sense/mcp_server.py`.

Where it points:
  CROWE_SENSE_URL             direct: the node's own API, http://host:8078. Reads and writes.
  CROWE_SENSE_CONFIG          else the file `crowe sense use` writes (~/.crowe-logic/sense.json)
  CROWE_ID_TOKEN              cloud reads through the relay need a Crowe ID bearer
  CROWE_SENSE_OPERATOR_TOKEN  the node's operator token; without it request_operation refuses
  CROWE_SENSE_OPERATOR        a label for the audit row, e.g. "desktop michael"

Writes are direct-only by design (contracts/device-descriptor-v0.md). On a cloud
source request_operation says so instead of trying. The server enforces nothing the
node does not: the node checks the token, the bounds and the cooldown itself, and this
process is one more caller.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "crowe-sense", "version": "0.1.0"}
DEFAULT_RELAY = "https://sense.crowelogic.com"
TIMEOUT_S = 10.0
POLL_S = 6.0
POLL_STEP_S = 0.5

TOOLS: list[dict[str, Any]] = [
    {"name": "describe_device",
     "description": "The node's device descriptor: what it measures, what it can do, which limits it enforces, and how it may be reached. Read this before requesting an operation.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "read_latest",
     "description": "The newest reading of every metric, optionally one zone or one metric. Values carry a unit and a quality (ok, warming, stale, est, fault).",
     "inputSchema": {"type": "object", "properties": {
         "zone": {"type": "string", "description": "e.g. tent-1"},
         "metric": {"type": "string", "description": "e.g. co2_ppm"}}, "additionalProperties": False}},
    {"name": "read_history",
     "description": "One metric over a window as [timestamp, mean] buckets.",
     "inputSchema": {"type": "object", "properties": {
         "metric": {"type": "string"}, "zone": {"type": "string"},
         "hours": {"type": "number", "default": 24}, "step": {"type": "number", "default": 300, "description": "bucket seconds"}},
         "required": ["metric"], "additionalProperties": False}},
    {"name": "list_operations",
     "description": "The operations this node accepts, their arguments, their enforced constraints, whether operations are enabled, and the recent requests with their outcomes.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "request_operation",
     "description": "Ask the node to perform one operation from list_operations, e.g. indicator.identify. This changes something in the physical world: the node checks the operator token, the argument bounds and the cooldown itself, queues the request, and the watchdog runs it. Returns the request's final status (done, rejected, unknown) or queued if it is still waiting. Direct path only.",
     "inputSchema": {"type": "object", "properties": {
         "operation": {"type": "string", "description": "e.g. indicator.identify"},
         "args": {"type": "object", "description": "arguments as listed for the operation"}},
         "required": ["operation"], "additionalProperties": False}},
]


class ToolError(Exception):
    pass


def load_source(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Resolve where the node is. Env first, then the CLI's sense.json."""
    env = os.environ if env is None else env
    url = (env.get("CROWE_SENSE_URL") or "").strip().rstrip("/")
    if url:
        return {"source": "direct", "url": url}
    path = env.get("CROWE_SENSE_CONFIG") or os.path.expanduser("~/.crowe-logic/sense.json")
    try:
        with open(path) as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        return {"source": "off"}
    if cfg.get("source") == "direct" and cfg.get("url"):
        return {"source": "direct", "url": str(cfg["url"]).rstrip("/")}
    if cfg.get("source") == "cloud" and cfg.get("node"):
        return {"source": "cloud", "node": cfg["node"], "relay": str(cfg.get("relay") or DEFAULT_RELAY).rstrip("/")}
    return {"source": "off"}


def endpoint(src: dict[str, Any], path: str) -> str:
    if src.get("source") == "direct":
        return src["url"] + path
    if src.get("source") == "cloud":
        tail = path[3:] if path.startswith("/v1/") else path
        return f"{src['relay']}/v1/nodes/{src['node']}{tail}"
    raise ToolError("No node configured. Set CROWE_SENSE_URL to the node's API (http://host:8078), or run `crowe sense use`.")


def default_http(method: str, url: str, headers: dict[str, str], body: bytes | None, timeout: float) -> tuple[int, Any]:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"error": str(e.code), "detail": e.reason}
    except urllib.error.URLError as e:
        raise ToolError(f"unreachable: {e.reason} ({url})") from None
    except TimeoutError:
        raise ToolError(f"unreachable: timed out after {timeout:g} s ({url})") from None


class Server:
    def __init__(self, http: Callable[..., tuple[int, Any]] = default_http, env: dict[str, str] | None = None,
                 sleep: Callable[[float], None] = time.sleep, now: Callable[[], float] = time.time):
        self.http = http
        self.env = os.environ if env is None else env
        self.sleep = sleep
        self.now = now

    # ── http ──
    def _get(self, path: str) -> Any:
        src = load_source(self.env)
        url = endpoint(src, path)
        headers = {"accept": "application/json"}
        if src["source"] == "cloud":
            tok = (self.env.get("CROWE_ID_TOKEN") or "").strip()
            if not tok:
                raise ToolError("Cloud reads need CROWE_ID_TOKEN (a Crowe ID access token). Or set CROWE_SENSE_URL for the direct path.")
            headers["authorization"] = f"Bearer {tok}"
        status, body = self.http("GET", url, headers, None, TIMEOUT_S)
        if status // 100 != 2:
            raise ToolError(_err_text(status, body, url))
        return body

    def _post_operation(self, op: str, args: dict) -> tuple[int, Any]:
        src = load_source(self.env)
        if src["source"] != "direct":
            raise ToolError("Operations run on the direct path only; the relay is read-only. Set CROWE_SENSE_URL to the node's own API.")
        tok = (self.env.get("CROWE_SENSE_OPERATOR_TOKEN") or "").strip()
        if not tok:
            raise ToolError("request_operation needs CROWE_SENSE_OPERATOR_TOKEN, the node's operator token. Without it the node refuses, and so does this server.")
        headers = {"accept": "application/json", "content-type": "application/json", "authorization": f"Bearer {tok}",
                   "x-crowe-operator": (self.env.get("CROWE_SENSE_OPERATOR") or "mcp")[:40]}
        body = json.dumps({"args": args or {}}).encode()
        return self.http("POST", endpoint(src, f"/v1/operations/{urllib.parse.quote(op, safe='.')}"), headers, body, TIMEOUT_S)

    # ── tools ──
    def describe_device(self, _args: dict) -> str:
        d = self._get("/v1/describe")
        head = d.get("annotations", {}).get("summary", "")
        return (head + "\n\n" if head else "") + json.dumps(d, indent=1)

    def read_latest(self, args: dict) -> str:
        rows = self._get("/v1/latest")
        zone, metric = args.get("zone"), args.get("metric")
        rows = [r for r in rows if (not zone or r.get("zone") == zone) and (not metric or r.get("metric") == metric)]
        if not rows:
            return "no readings match" + (f" zone={zone}" if zone else "") + (f" metric={metric}" if metric else "")
        now = self.now()
        lines = []
        for r in sorted(rows, key=lambda x: (str(x.get("zone")), str(x.get("metric")))):
            age = now - float(r.get("ts", now))
            lines.append(f"{r.get('zone')}: {r.get('metric')} = {r.get('value')} {r.get('unit', '')} "
                         f"({r.get('quality', 'ok')}, {age:.0f} s ago, {r.get('sensor')})")
        return "\n".join(lines)

    def read_history(self, args: dict) -> str:
        q = {"metric": args["metric"], "hours": args.get("hours", 24), "step": args.get("step", 300)}
        if args.get("zone"):
            q["zone"] = args["zone"]
        h = self._get("/v1/history?" + urllib.parse.urlencode(q))
        pts = [p for p in h.get("points", []) if p and p[1] is not None]
        if not pts:
            return f"{h.get('zone', '')} {h.get('metric')}: no points in the window"
        vals = [float(p[1]) for p in pts]
        head = (f"{h.get('zone', '')} {h.get('metric')} ({h.get('unit', '')}): {len(pts)} buckets, "
                f"min {min(vals):g}, mean {sum(vals) / len(vals):.3g}, max {max(vals):g}")
        return head + "\n" + json.dumps(pts)

    def list_operations(self, _args: dict) -> str:
        return json.dumps(self._get("/v1/operations"), indent=1)

    def request_operation(self, args: dict) -> str:
        op = str(args.get("operation") or "")
        if not op:
            raise ToolError("operation is required, e.g. indicator.identify")
        status, body = self._post_operation(op, args.get("args") or {})
        if status != 202:
            raise ToolError(_err_text(status, body, op))
        row = body
        deadline = self.now() + POLL_S
        while row.get("status") in ("queued", "running") and self.now() < deadline:
            self.sleep(POLL_STEP_S)
            try:
                row = self._get(f"/v1/operations/{row['id']}")
            except ToolError as e:
                # A hotspot reset can take the route with it. That is not a failure
                # of the request; it is the one outcome the descriptor warned about.
                return f"{op} {row['id']}: status unknown from here ({e}). The node keeps the record; read it with list_operations when the path is back."
        res = row.get("result") or {}
        st = row.get("status")
        note = " (simulated: no GPIO on that host)" if res.get("simulated") else ""
        if st == "done":
            return f"{op} {row['id']}: done{note}. {json.dumps(res)}"
        if st in ("queued", "running"):
            return f"{op} {row['id']}: still {st} after {POLL_S:g} s; the watchdog may be busy. Check list_operations."
        return f"{op} {row['id']}: {st}. {res.get('detail') or json.dumps(res)}"

    # ── json-rpc ──
    def call_tool(self, name: str, args: dict) -> str:
        fn = {"describe_device": self.describe_device, "read_latest": self.read_latest,
              "read_history": self.read_history, "list_operations": self.list_operations,
              "request_operation": self.request_operation}.get(name)
        if fn is None:
            raise ToolError(f"unknown tool: {name}")
        return fn(args or {})

    def handle(self, msg: dict) -> dict | None:
        method = msg.get("method")
        id_ = msg.get("id")
        if method == "initialize":
            return {"jsonrpc": "2.0", "id": id_, "result": {"protocolVersion": PROTOCOL_VERSION,
                                                            "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO}}
        if method == "ping":
            return {"jsonrpc": "2.0", "id": id_, "result": {}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": id_, "result": {"tools": TOOLS}}
        if method == "tools/call":
            params = msg.get("params") or {}
            try:
                text = self.call_tool(str(params.get("name") or ""), params.get("arguments") or {})
                return {"jsonrpc": "2.0", "id": id_, "result": {"content": [{"type": "text", "text": text}]}}
            except ToolError as e:
                return {"jsonrpc": "2.0", "id": id_, "result": {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True}}
            except Exception as e:  # a bug here must not kill the client's session
                return {"jsonrpc": "2.0", "id": id_, "result": {"content": [{"type": "text", "text": f"error: {type(e).__name__}: {e}"}], "isError": True}}
        if id_ is None:
            return None  # a notification
        return {"jsonrpc": "2.0", "id": id_, "error": {"code": -32601, "message": f"method not found: {method}"}}


def _err_text(status: int, body: Any, where: str) -> str:
    if isinstance(body, dict) and body.get("error"):
        extra = f" retry after {body['retry_after_s']} s" if body.get("retry_after_s") else ""
        return f"{body['error']}: {body.get('detail', '')}{extra} ({where})".strip()
    return f"HTTP {status} ({where})"


def serve(stdin=None, stdout=None, server: Server | None = None) -> None:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    server = server or Server()
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        reply = server.handle(msg)
        if reply is not None:
            stdout.write(json.dumps(reply) + "\n")
            stdout.flush()


def main() -> None:
    serve()


if __name__ == "__main__":
    main()
