from __future__ import annotations

import gzip
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from crowe.db import open_db
from crowe.sampler import write_batch
from crowe.sensors.base import Reading
from crowe.uploader import build_batch, fetch_pending, mark_sent


def _seed(conn, n: int) -> None:
    write_batch(conn, [
        Reading(f"2026-06-14T21:00:{i:02d}.000Z", "scd41", "co2_ppm", 800.0 + i, "ppm")
        for i in range(n)
    ])


def test_fetch_pending_returns_only_unsent(tmp_path):
    conn = open_db(tmp_path / "db.sqlite")
    _seed(conn, 3)
    conn.execute("UPDATE raw_samples SET sent = 1 WHERE id = 1")

    pending = fetch_pending(conn, limit=100)
    assert [row[0] for row in pending] == [2, 3]


def test_build_batch_round_trips(tmp_path):
    conn = open_db(tmp_path / "db.sqlite")
    _seed(conn, 5)
    pending = fetch_pending(conn, limit=100)
    key = Ed25519PrivateKey.generate()

    batch = build_batch(pending, key)

    decompressed = gzip.decompress(batch.body).decode()
    lines = [json.loads(line) for line in decompressed.splitlines()]
    assert len(lines) == 5
    assert lines[0]["sensor"] == "scd41"
    assert lines[0]["value"] == 800.0
    key.public_key().verify(batch.signature, batch.body)


def test_mark_sent_updates_rows(tmp_path):
    conn = open_db(tmp_path / "db.sqlite")
    _seed(conn, 4)
    mark_sent(conn, [1, 3])
    rows = list(conn.execute("SELECT id, sent FROM raw_samples ORDER BY id"))
    assert rows == [(1, 1), (2, 0), (3, 1), (4, 0)]
