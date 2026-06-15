"""Uploader — drains raw_samples into signed gzipped batches and PUTs to S3.

Marks rows sent=1 only after the PUT returns 2xx. Batches drain every
30 s or when 1000 rows are pending, whichever first.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import signal
import sqlite3
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from crowe import config
from crowe.db import open_db
from crowe.routing import current_uplink

log = logging.getLogger("crowe.uploader")

BATCH_ROWS = 1000
BATCH_INTERVAL_S = 30.0


@dataclass(frozen=True, slots=True)
class Batch:
    ids: list[int]
    body: bytes        # gzipped jsonl
    signature: bytes


def load_private_key(path: Path) -> Ed25519PrivateKey:
    raw = path.read_bytes()
    key = serialization.load_pem_private_key(raw, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("expected ed25519 private key")
    return key


def fetch_pending(conn: sqlite3.Connection, limit: int) -> list[tuple]:
    cur = conn.execute(
        "SELECT id, ts, sensor, channel, value, unit FROM raw_samples "
        "WHERE sent = 0 ORDER BY id ASC LIMIT ?",
        (limit,),
    )
    return cur.fetchall()


def build_batch(rows: Iterable[tuple], key: Ed25519PrivateKey) -> Batch:
    ids: list[int] = []
    lines: list[bytes] = []
    for row in rows:
        rid, ts, sensor, channel, value, unit = row
        ids.append(rid)
        lines.append(
            json.dumps({
                "id": rid, "ts": ts, "sensor": sensor,
                "channel": channel, "value": value, "unit": unit,
            }).encode("utf-8")
        )
    payload = b"\n".join(lines)
    gz = gzip.compress(payload, mtime=0)
    sig = key.sign(gz)
    return Batch(ids=ids, body=gz, signature=sig)


def mark_sent(conn: sqlite3.Connection, ids: list[int]) -> None:
    if not ids:
        return
    placeholders = ",".join("?" * len(ids))
    conn.execute(f"UPDATE raw_samples SET sent = 1 WHERE id IN ({placeholders})", ids)


def s3_url(cfg: config.NodeConfig, ts_unix: int, batch_id: int) -> str:
    base = cfg.s3.endpoint_url or f"https://{cfg.s3.bucket}.s3.{cfg.s3.region}.amazonaws.com"
    t = time.gmtime(ts_unix)
    key = (
        f"{cfg.s3.prefix.rstrip('/')}/{cfg.node_id}/"
        f"{t.tm_year:04d}/{t.tm_mon:02d}/{t.tm_mday:02d}/{t.tm_hour:02d}/"
        f"batch-{batch_id:010d}.jsonl.gz"
    )
    return f"{base.rstrip('/')}/{key.lstrip('/')}"


def upload(client: httpx.Client, url: str, batch: Batch, node_id: str) -> bool:
    try:
        resp = client.put(
            url,
            content=batch.body,
            headers={
                "Content-Type": "application/gzip",
                "X-Crowe-Node": node_id,
                "X-Crowe-Signature": batch.signature.hex(),
            },
            timeout=30.0,
        )
    except httpx.HTTPError:
        log.exception("upload failed (network)")
        return False
    if resp.status_code // 100 != 2:
        log.warning("upload rejected: %s %s", resp.status_code, resp.text[:200])
        return False
    return True


def drain_once(
    conn: sqlite3.Connection,
    client: httpx.Client,
    cfg: config.NodeConfig,
    key: Ed25519PrivateKey,
) -> int:
    rows = fetch_pending(conn, BATCH_ROWS)
    if not rows:
        return 0
    batch = build_batch(rows, key)
    url = s3_url(cfg, int(time.time()), rows[-1][0])
    if upload(client, url, batch, cfg.node_id):
        mark_sent(conn, batch.ids)
        return len(batch.ids)
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--interval", type=float, default=BATCH_INTERVAL_S)
    args = p.parse_args()

    cfg = config.load()
    conn = open_db(cfg.db_path)
    key = load_private_key(cfg.private_key_path)
    client = httpx.Client()
    stop = False

    def _stop(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    while not stop:
        uplink = current_uplink()
        if uplink is None:
            log.info("no default route; sleeping")
        else:
            sent = drain_once(conn, client, cfg, key)
            if sent:
                log.info("drained %d rows via %s (%s)", sent, uplink.interface, uplink.kind)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
