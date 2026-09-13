"""Local API and kiosk dashboard, stdlib only, on 0.0.0.0:8078.

Serves the read half of contracts/telemetry-v1.md straight from the sampler's SQLite so
the Tauri app (direct mode), the kiosk display and `crowe sense` on the same network
work with no cloud at all. The relay serves the identical paths for everything else.

Also the node's one write door (contracts/device-descriptor-v0.md): GET /v1/describe
says what the node is and what it enforces; POST /v1/operations/{id} queues one of the
registry's operations for the watchdog, and only with the operator bearer. Reads stay
open on the LAN; a write needs the token even from localhost.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import re
import sqlite3
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from crowe import config, descriptor, operations
from crowe.derive import dew_point_c, vpd_kpa
from crowe.metrics import CHART_METRICS, metric_for, rank, unit_for

log = logging.getLogger("crowe.api")
VERSION = "0.2.0"
STALE_AFTER_S = 180.0
STARTED = time.time()


def _unix(ts: str) -> float:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def connect(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5, check_same_thread=False)


def _rows(conn: sqlite3.Connection, since_iso: str) -> list[tuple]:
    return conn.execute(
        "SELECT ts, sensor, channel, value, unit FROM raw_samples WHERE ts >= ? ORDER BY id",
        (since_iso,),
    ).fetchall()


def _iso(unix: float) -> str:
    return datetime.fromtimestamp(unix, UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def latest(conn: sqlite3.Connection, node_id: str, zone: str, now: float) -> list[dict]:
    """Newest reading per metric, the preferred driver winning when several report it."""
    best: dict[str, dict] = {}
    q = ("SELECT r.ts, r.sensor, r.channel, r.value, r.unit FROM raw_samples r "
         "JOIN (SELECT sensor, channel, MAX(id) AS mid FROM raw_samples GROUP BY sensor, channel) m "
         "ON r.id = m.mid")
    for ts, sensor, channel, value, unit in conn.execute(q):
        metric = metric_for(channel)
        cand = {"ts": round(_unix(ts), 3), "node": node_id, "zone": "pi" if sensor == "pi" else zone, "sensor": sensor,
                "metric": metric, "value": float(value), "unit": unit_for(unit), "quality": "ok"}
        if now - cand["ts"] > STALE_AFTER_S:
            cand["quality"] = "stale"
        cur = best.get(metric)
        if cur is None or rank(metric, sensor) < rank(metric, cur["sensor"]):
            best[metric] = cand
    out = list(best.values())
    t, rh = best.get("temperature_c"), best.get("humidity_pct")
    if t and rh:
        ts = max(t["ts"], rh["ts"])
        for metric, fn, unit in (("vpd_kpa", vpd_kpa, "kPa"), ("dew_point_c", dew_point_c, "C")):
            out.append({"ts": ts, "node": node_id, "zone": zone, "sensor": "derived", "metric": metric,
                        "value": fn(t["value"], rh["value"]), "unit": unit, "quality": "est"})
    return out


def snapshot(readings: list[dict], now: float) -> dict:
    out: dict[str, dict] = {}
    for r in readings:
        zone = f"{r['zone']}-derived" if r["sensor"] == "derived" else r["zone"]
        out.setdefault(zone, {})[r["metric"]] = {
            "value": r["value"], "unit": r["unit"], "quality": r["quality"], "age": round(now - r["ts"], 1),
        }
    return out


def series(conn: sqlite3.Connection, zone: str, hours: float, now: float, max_points: int = 200) -> dict:
    """Chart metrics over the window, preferred driver only, downsampled."""
    since = _iso(now - hours * 3600)
    by_metric: dict[str, dict[str, list]] = {}
    for ts, sensor, channel, value, _unit in _rows(conn, since):
        metric = metric_for(channel)
        if metric not in CHART_METRICS:
            continue
        by_metric.setdefault(metric, {}).setdefault(sensor, []).append([round(_unix(ts), 1), float(value)])
    out = {}
    for metric, per_sensor in by_metric.items():
        sensor = min(per_sensor, key=lambda s: rank(metric, s))
        pts = per_sensor[sensor]
        if len(pts) > max_points:
            step = len(pts) / max_points
            pts = [pts[int(i * step)] for i in range(max_points)]
        out[f"{zone}|{metric}"] = pts
    return out


def history(conn: sqlite3.Connection, metric: str, hours: float, step: float, now: float) -> dict:
    since = _iso(now - hours * 3600)
    per_sensor: dict[str, list[tuple[float, float]]] = {}
    unit = ""
    for ts, sensor, channel, value, u in _rows(conn, since):
        if metric_for(channel) != metric:
            continue
        per_sensor.setdefault(sensor, []).append((_unix(ts), float(value)))
        unit = unit_for(u)
    if not per_sensor:
        return {"metric": metric, "unit": unit, "step": step, "points": []}
    sensor = min(per_sensor, key=lambda s: rank(metric, s))
    buckets: dict[float, list[float]] = {}
    for ts, v in per_sensor[sensor]:
        buckets.setdefault((ts // step) * step, []).append(v)
    points = [[b, round(sum(vs) / len(vs), 3)] for b, vs in sorted(buckets.items())]
    return {"metric": metric, "unit": unit, "step": step, "points": points}


def health(conn: sqlite3.Connection, node_id: str, zone: str, now: float) -> dict:
    count = conn.execute("SELECT COUNT(*) FROM raw_samples").fetchone()[0]
    last = conn.execute("SELECT ts FROM raw_samples ORDER BY id DESC LIMIT 1").fetchone()
    last_ts = round(_unix(last[0]), 3) if last else None
    age = round(now - last_ts, 1) if last_ts else None
    return {"ok": age is not None and age <= STALE_AFTER_S, "node": node_id, "zone": zone,
            "readings": count, "last_ts": last_ts, "age_s": age,
            "uptime_s": int(now - STARTED), "version": VERSION}


def build_data(conn: sqlite3.Connection, node_id: str, zone: str, hours: float, now: float) -> dict:
    lat = latest(conn, node_id, zone, now)
    count = conn.execute("SELECT COUNT(*) FROM raw_samples").fetchone()[0]
    return {"generated": now, "node": node_id, "zone": zone, "count": count, "hours": hours,
            "snapshot": snapshot(lat, now), "series": series(conn, zone, hours, now)}


DASHBOARD = Path(__file__).with_name("dashboard.html")
MAX_OPERATION_BODY = 4096
OP_ID_RE = r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$"


class OperationsService:
    """The API's view of the writable half: the descriptor, the token check and the
    queue. The queue is opened lazily so a read-only node never creates it."""

    def __init__(self, cfg: config.NodeConfig, status_path: Path | None = Path("/run/crowe/status.json")):
        self.cfg = cfg
        self.status_path = status_path
        self._queue = None

    @property
    def enabled(self) -> bool:
        return bool(self.cfg.operations_enabled)

    def queue(self):
        if self._queue is None:
            self._queue = operations.open_queue(self.cfg.operations_db_path)
        return self._queue

    def describe(self, now: float) -> dict:
        return descriptor.build(self.cfg, status_path=self.status_path, now=now)

    def authorized(self, auth_header: str | None) -> bool:
        h = str(auth_header or "")
        if not h.lower().startswith("bearer "):
            return False
        return operations.token_matches(h[7:], self.cfg.operator_token_path)

    def listing(self, now: float) -> dict:
        recent = operations.recent(self.queue(), 20) if self.enabled else []
        return {"enabled": self.enabled, "operations": operations.public_registry(), "recent": recent,
                "cooldowns": {op: round(operations.cooldown_remaining(self.queue(), op, now), 1)
                              for op in operations.REGISTRY} if self.enabled else {}}

    def status(self, id_: str) -> dict | None:
        return operations.get(self.queue(), id_) if self.enabled else None

    def request(self, op_id: str, args: dict | None, requested_by: str, now: float) -> tuple[int, dict]:
        """Validate, check the cooldown, queue. Returns (http status, body)."""
        try:
            operations.validate(op_id, args)
        except operations.OperationError as e:
            return e.status, {"error": e.code, "detail": e.detail}
        remaining = operations.cooldown_remaining(self.queue(), op_id, now)
        if remaining > 0:
            return 429, {"error": "cooldown", "detail": f"{op_id} ran recently; try again in {remaining:.0f} s.",
                         "retry_after_s": round(remaining, 1)}
        row = operations.enqueue(self.queue(), op_id, args, requested_by, now)
        return 202, row


def make_handler(db_path: Path, node_id: str, zone: str, ops: OperationsService | None = None):
    class Handler(BaseHTTPRequestHandler):
        server_version = f"crowe-sense-api/{VERSION}"

        def log_message(self, fmt, *args):
            log.debug(fmt, *args)

        def _json(self, status: int, body) -> None:
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _err(self, status: int, error: str, detail: str) -> None:
            self._json(status, {"error": error, "detail": detail})

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "authorization, content-type, x-crowe-operator")
            self.end_headers()

        # The writable half and its descriptor. Answered before the samples DB is
        # opened, because neither needs it and a node whose sampler has not started
        # should still be able to say what it is.
        def _ops_get(self, path: str, now: float) -> bool:
            if path == "/v1/describe":
                if ops is None:
                    self._err(404, "not_configured", "This server was started without a node configuration.")
                else:
                    self._json(200, ops.describe(now))
                return True
            if path == "/v1/operations":
                if ops is None:
                    self._err(404, "not_configured", "This server was started without a node configuration.")
                else:
                    self._json(200, ops.listing(now))
                return True
            if path.startswith("/v1/operations/"):
                id_ = path[len("/v1/operations/"):]
                if ops is None or not ops.enabled:
                    self._err(403, "operations_disabled", "Operations are off on this node (node.toml [operations] enabled = false).")
                    return True
                row = ops.status(id_)
                if row is None:
                    self._err(404, "not_found", f"No operation {id_}.")
                else:
                    self._json(200, row)
                return True
            return False

        def do_POST(self):
            u = urlparse(self.path)
            path = u.path.rstrip("/")
            now = time.time()
            if not path.startswith("/v1/operations/"):
                return self._err(404, "not_found", "POST /v1/operations/{operation} is the only write.")
            if ops is None or not ops.enabled:
                return self._err(403, "operations_disabled", "Operations are off on this node (node.toml [operations] enabled = false).")
            # Authorization first, before the body is read or the operation named, so an
            # unauthorized caller learns nothing about what exists.
            if not ops.authorized(self.headers.get("Authorization")):
                return self._err(401, "unauthorized", "Operations need the node's operator token as a bearer.")
            op_id = path[len("/v1/operations/"):]
            if not re.match(OP_ID_RE, op_id):
                return self._err(404, "unknown_operation", "Operation ids look like indicator.identify.")
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_OPERATION_BODY:
                return self._err(413, "too_large", f"Operation bodies are capped at {MAX_OPERATION_BODY} bytes.")
            raw = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw) if raw.strip() else {}
            except ValueError:
                return self._err(400, "bad_body", "Send a JSON object of arguments, or an empty body.")
            args = body.get("args", body) if isinstance(body, dict) else body
            who = str(self.headers.get("X-Crowe-Operator") or "")[:40] or self.client_address[0]
            status, out = ops.request(op_id, args, who, now)
            self._json(status, out)

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            path = u.path.rstrip("/") or "/"
            now = time.time()
            if self._ops_get(path, now):
                return
            try:
                conn = connect(db_path)
            except sqlite3.Error as e:
                return self._err(503, "no_database", f"The sampler has not written a database yet: {e}")
            try:
                if path == "/":
                    html = DASHBOARD.read_bytes() if DASHBOARD.exists() else b"<p>Crowe Sense node. See /api/data</p>"
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(html)))
                    self.end_headers()
                    self.wfile.write(html)
                elif path == "/health":
                    self._json(200, health(conn, node_id, zone, now))
                elif path == "/api/data":
                    hours = min(max(float(q.get("hours", ["6"])[0]), 0.1), 24 * 14)
                    self._json(200, build_data(conn, node_id, zone, hours, now))
                elif path == "/v1/latest":
                    self._json(200, latest(conn, node_id, zone, now))
                elif path == "/v1/history":
                    metric = q.get("metric", [""])[0]
                    if not metric:
                        return self._err(400, "bad_metric", "metric is required.")
                    hours = min(max(float(q.get("hours", ["24"])[0]), 0.1), 24 * 90)
                    step = min(max(float(q.get("step", ["60"])[0]), 1), 86400)
                    body = history(conn, metric, hours, step, now)
                    body["zone"] = q.get("zone", [zone])[0]
                    self._json(200, body)
                else:
                    self._err(404, "not_found", "Paths: /health, /api/data, /v1/latest, /v1/history, /v1/describe, /v1/operations.")
            except ValueError as e:
                self._err(400, "bad_query", str(e))
            finally:
                conn.close()

    return Handler


def serve(db_path: Path, node_id: str, zone: str, host: str = "0.0.0.0", port: int = 8078,
          ops: OperationsService | None = None) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer((host, port), make_handler(db_path, node_id, zone, ops))
    return srv


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=None)
    args = p.parse_args()
    cfg = config.load()
    srv = serve(cfg.db_path, cfg.node_id, cfg.zone, args.host, args.port or cfg.api_port, ops=OperationsService(cfg))
    log.info("api serving %s on %s:%d", cfg.db_path, args.host, srv.server_port)
    with contextlib.suppress(KeyboardInterrupt):
        srv.serve_forever()


if __name__ == "__main__":
    main()
