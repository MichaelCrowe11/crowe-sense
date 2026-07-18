from __future__ import annotations

import json

from crowe import cli
from crowe.db import open_db
from crowe.sampler import write_batch
from crowe.sensors.base import Reading


def _seed(cfg_path_dir, n: int) -> None:
    """Populate the samples DB the CLI will read from (via tmp_config)."""
    from crowe import config

    conn = open_db(config.load().db_path)
    write_batch(conn, [
        Reading(f"2026-06-14T21:00:{i:02d}.000Z", "scd41", "co2_ppm", 800.0 + i, "ppm")
        for i in range(n)
    ])


def test_read_newest_first(tmp_config, capsys):
    _seed(tmp_config, 5)
    rc = cli.main(["read", "--last", "3"])
    out = capsys.readouterr().out
    assert rc == 0
    lines = out.strip().splitlines()
    assert len(lines) == 3
    # newest sample (i=4 -> 804.0) is first
    assert "804.000" in lines[0]
    assert "802.000" in lines[2]


def test_read_sensor_filter_json(tmp_config, capsys):
    _seed(tmp_config, 3)
    rc = cli.main(["read", "--sensor", "scd41", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    rows = json.loads(out)
    assert len(rows) == 3
    assert all(r["sensor"] == "scd41" for r in rows)


def test_read_unknown_sensor_is_error(tmp_config, capsys):
    _seed(tmp_config, 2)
    rc = cli.main(["read", "--sensor", "nope"])
    assert rc == 1


def test_read_without_db_is_error(tmp_config, capsys):
    # no _seed() -> db file never created
    rc = cli.main(["read"])
    assert rc == 1
    assert "sampler" in capsys.readouterr().err


def test_queue_counts_unsent(tmp_config, capsys):
    _seed(tmp_config, 4)
    from crowe import config

    conn = open_db(config.load().db_path)
    conn.execute("UPDATE raw_samples SET sent = 1 WHERE id IN (1, 2)")

    rc = cli.main(["queue", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    assert json.loads(out)["queue_depth"] == 2


def test_storage_json_shape_and_exit_code(tmp_config, capsys):
    # Whether tmp_config's mount looks "mounted" depends on the host's
    # filesystem layout, so assert the invariant rather than a fixed state:
    # exit code is 0 iff the drive is reported mounted, and the payload has
    # the expected keys either way.
    rc = cli.main(["storage", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {"path", "mounted", "total_bytes", "free_bytes", "free_gb"}
    assert rc == (0 if payload["mounted"] else 1)


def test_missing_config_exits_2(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CROWE_CONFIG", str(tmp_path / "does-not-exist.toml"))
    from crowe import config

    config.reset_cache()
    rc = cli.main(["status"])
    assert rc == 2
    assert "node config" in capsys.readouterr().err
