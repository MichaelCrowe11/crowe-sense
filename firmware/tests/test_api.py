from __future__ import annotations

import json
import threading
import time
import urllib.request
from datetime import UTC, datetime

import pytest

from crowe import api
from crowe.db import open_db
from crowe.sampler import write_batch
from crowe.sensors.base import Reading


def _iso(unix: float) -> str:
    return datetime.fromtimestamp(unix, UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@pytest.fixture
def served(tmp_path):
    db = tmp_path / "samples.sqlite"
    conn = open_db(db)
    now = time.time()
    rows = []
    for i in range(120):                       # two hours, one minute apart
        ts = _iso(now - (119 - i) * 60)
        rows += [
            Reading(ts, "scd41", "co2_ppm", 800.0 + i, "ppm"),
            Reading(ts, "scd41", "temperature_c", 22.0, "C"),
            Reading(ts, "sht45", "temperature_c", 21.0 + i * 0.01, "C"),
            Reading(ts, "sht45", "humidity_pct", 85.0, "%RH"),
            Reading(ts, "bme688", "gas_resistance_ohm", 12000.0, "ohm"),
        ]
    write_batch(conn, rows)
    conn.close()
    srv = api.serve(db, "cs-a1b2c3", "tent-1", host="127.0.0.1", port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return r.status, json.loads(r.read())


def test_health_is_ok_and_counts(served):
    status, h = _get(served, "/health")
    assert status == 200
    assert h["ok"] is True and h["node"] == "cs-a1b2c3" and h["zone"] == "tent-1"
    assert h["readings"] == 600 and h["age_s"] < 5


def test_latest_prefers_sht45_and_derives_vpd(served):
    _, rows = _get(served, "/v1/latest")
    by = {r["metric"]: r for r in rows}
    assert by["temperature_c"]["sensor"] == "sht45"
    assert abs(by["temperature_c"]["value"] - 22.19) < 0.001
    assert by["gas_ohms"]["unit"] == "ohm"
    assert by["humidity_pct"]["unit"] == "%"
    assert by["vpd_kpa"]["sensor"] == "derived" and by["vpd_kpa"]["quality"] == "est"
    assert by["dew_point_c"]["value"] < 22.19
    assert all(r["node"] == "cs-a1b2c3" and r["zone"] == "tent-1" for r in rows)


def test_api_data_has_the_app_shape(served):
    _, d = _get(served, "/api/data?hours=6")
    assert d["node"] == "cs-a1b2c3" and d["count"] == 600
    snap = d["snapshot"]
    assert snap["tent-1"]["co2_ppm"]["value"] == 919.0
    assert "vpd_kpa" in snap["tent-1-derived"]
    assert set(d["series"]) == {"tent-1|temperature_c", "tent-1|humidity_pct", "tent-1|co2_ppm"}
    assert len(d["series"]["tent-1|co2_ppm"]) == 120
    assert d["series"]["tent-1|temperature_c"][0][1] == 21.0     # sht45, not scd41's 22.0


def test_history_buckets_and_requires_metric(served):
    _, h = _get(served, "/v1/history?metric=co2_ppm&hours=2&step=1800")
    assert h["unit"] == "ppm" and h["zone"] == "tent-1"
    assert 4 <= len(h["points"]) <= 5
    assert h["points"][-1][1] > h["points"][0][1]
    try:
        urllib.request.urlopen(served + "/v1/history", timeout=5)
    except urllib.error.HTTPError as e:
        assert e.code == 400 and json.loads(e.read())["error"] == "bad_metric"
    else:
        raise AssertionError("expected 400")


def test_dashboard_and_404_are_honest(served):
    with urllib.request.urlopen(served + "/", timeout=5) as r:
        assert r.status == 200 and b"Crowe Sense" in r.read()
    try:
        urllib.request.urlopen(served + "/nope", timeout=5)
    except urllib.error.HTTPError as e:
        assert e.code == 404 and "detail" in json.loads(e.read())
