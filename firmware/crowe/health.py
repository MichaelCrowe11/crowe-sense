"""Health reporter — emits a 1 KB JSON snapshot on a systemd timer.

Hits a /events POST endpoint rather than the bulk S3 path so the cloud
can keep heartbeats in a hot table separate from telemetry.
"""

from __future__ import annotations

import argparse
import json
import logging
import time

import httpx
import psutil

from crowe import config
from crowe.db import open_db
from crowe.routing import current_uplink
from crowe.storage import status as storage_status

log = logging.getLogger("crowe.health")


def snapshot(cfg: config.NodeConfig) -> dict:
    ms = storage_status(cfg.storage_mount)
    uplink = current_uplink()

    conn = open_db(cfg.db_path)
    queue_depth = conn.execute(
        "SELECT COUNT(*) FROM raw_samples WHERE sent = 0"
    ).fetchone()[0]
    last_row = conn.execute(
        "SELECT ts FROM raw_samples ORDER BY id DESC LIMIT 1"
    ).fetchone()

    return {
        "node_id": cfg.node_id,
        "site": cfg.site,
        "ts": time.time(),
        "uptime_s": int(time.time() - psutil.boot_time()),
        "drive": {"mounted": ms.mounted, "free_gb": ms.free_gb},
        "uplink": {
            "interface": uplink.interface if uplink else None,
            "kind": uplink.kind if uplink else None,
        },
        "queue_depth": queue_depth,
        "last_sample_ts": last_row[0] if last_row else None,
        "load_avg": psutil.getloadavg(),
        "cpu_temp_c": _cpu_temp(),
    }


def _cpu_temp() -> float | None:
    try:
        temps = psutil.sensors_temperatures()
    except Exception:
        return None
    for entries in temps.values():
        if entries:
            return entries[0].current
    return None


def post(endpoint: str, body: dict) -> bool:
    try:
        resp = httpx.post(endpoint, json=body, timeout=15.0)
    except httpx.HTTPError:
        log.exception("health post failed")
        return False
    return resp.status_code // 100 == 2


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--endpoint", default="")
    p.add_argument("--print", action="store_true", help="print snapshot instead of POSTing")
    args = p.parse_args()

    cfg = config.load()
    snap = snapshot(cfg)
    if args.print or not args.endpoint:
        print(json.dumps(snap, indent=2))
        return
    if post(args.endpoint, snap):
        log.info("health posted (queue=%d)", snap["queue_depth"])
    else:
        log.warning("health post failed")


if __name__ == "__main__":
    main()
