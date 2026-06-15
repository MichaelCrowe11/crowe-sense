from __future__ import annotations

from crowe.db import open_db
from crowe.sampler import write_batch
from crowe.sensors.base import Reading


def test_open_db_creates_schema(tmp_path):
    conn = open_db(tmp_path / "db" / "samples.sqlite")
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"raw_samples", "events", "schema_version"} <= tables

    journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert journal_mode == "wal"


def test_write_batch_persists_rows(tmp_path):
    conn = open_db(tmp_path / "db.sqlite")
    write_batch(conn, [
        Reading("2026-06-14T21:00:00.000Z", "scd41", "co2_ppm", 800.0, "ppm"),
        Reading("2026-06-14T21:00:00.001Z", "sht45", "temperature_c", 21.2, "C"),
    ])
    rows = list(conn.execute("SELECT sensor, channel, value, sent FROM raw_samples"))
    assert ("scd41", "co2_ppm", 800.0, 0) in rows
    assert ("sht45", "temperature_c", 21.2, 0) in rows
