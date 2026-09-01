"""Local read API and kiosk dashboard, stdlib only, on 0.0.0.0:8078.

Serves the read half of contracts/telemetry-v1.md straight from the sampler's SQLite so
the Tauri app (direct mode), the kiosk display and `crowe sense` on the same network
work with no cloud at all. The relay serves the identical paths for everything else.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import sqlite3
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from crowe import config
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


def make_handler(db_path: Path, node_id: str, zone: str):
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
            self.send_header("Access-Control-Allow-Headers", "authorization, content-type")
            self.end_headers()

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            path = u.path.rstrip("/") or "/"
            now = time.time()
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
                    self._err(404, "not_found", "Paths: /health, /api/data, /v1/latest, /v1/history.")
            except ValueError as e:
                self._err(400, "bad_query", str(e))
            finally:
                conn.close()

    return Handler


def serve(db_path: Path, node_id: str, zone: str, host: str = "0.0.0.0", port: int = 8078) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer((host, port), make_handler(db_path, node_id, zone))
    return srv


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=None)
    args = p.parse_args()
    cfg = config.load()
    srv = serve(cfg.db_path, cfg.node_id, cfg.zone, args.host, args.port or cfg.api_port)
    log.info("api serving %s on %s:%d", cfg.db_path, args.host, srv.server_port)
    with contextlib.suppress(KeyboardInterrupt):
        srv.serve_forever()


if __name__ == "__main__":
    main()
