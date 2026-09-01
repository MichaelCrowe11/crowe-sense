from __future__ import annotations

import base64
import gzip
import json

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from crowe import config
from crowe.db import open_db
from crowe.sampler import write_batch
from crowe.sensors.base import Reading
from crowe.uploader import (
    build_relay_batch,
    drain_once,
    fetch_pending,
    iso_to_unix,
    relay_upload,
    to_reading,
)


def _seed(conn, n: int) -> None:
    write_batch(conn, [
        Reading(f"2026-09-01T04:13:{i:02d}.250Z", "bme688", "gas_resistance_ohm", 12000.0 + i, "ohm") for i in range(n)
    ] + [Reading("2026-09-01T04:13:20.000Z", "sht45", "humidity_pct", 84.5, "%RH")])


def test_iso_to_unix_is_utc():
    assert iso_to_unix("2026-09-01T04:13:20.000Z") == 1788236000.0


def test_to_reading_is_the_contract_shape():
    r = to_reading((7, "2026-09-01T04:13:20.000Z", "sht45", "humidity_pct", 84.5, "%RH"), "cs-a1b2c3", "tent-1")
    assert r == {"ts": 1788236000.0, "node": "cs-a1b2c3", "zone": "tent-1", "sensor": "sht45",
                 "metric": "humidity_pct", "value": 84.5, "unit": "%", "quality": "ok"}


def test_build_relay_batch_signs_the_gzipped_ndjson(tmp_path):
    conn = open_db(tmp_path / "db.sqlite")
    _seed(conn, 3)
    key = Ed25519PrivateKey.generate()
    batch = build_relay_batch(fetch_pending(conn, 100), key, "cs-a1b2c3", "tent-1")
    key.public_key().verify(batch.signature, batch.body)
    lines = [json.loads(x) for x in gzip.decompress(batch.body).decode().splitlines()]
    assert len(lines) == 4
    assert lines[0]["metric"] == "gas_ohms"          # channel renamed to the contract metric
    assert lines[0]["node"] == "cs-a1b2c3"
    assert lines[-1]["unit"] == "%"


def test_relay_upload_posts_headers_and_marks_sent_only_on_2xx(tmp_path, tmp_config):
    cfg_path = tmp_config
    cfg_path.write_text(cfg_path.read_text().replace('[s3]', '[relay]\nurl = "https://relay.test"\n\n[s3]'))
    config.reset_cache()
    cfg = config.load()
    assert cfg.relay_url == "https://relay.test"

    conn = open_db(tmp_path / "db.sqlite")
    _seed(conn, 2)
    key = Ed25519PrivateKey.generate()
    seen = {}

    def app(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = request.content
        return httpx.Response(seen.pop("status", 202), json={"accepted": 3})

    client = httpx.Client(transport=httpx.MockTransport(app))
    seen["status"] = 401
    assert drain_once(conn, client, cfg, key) == 0
    assert conn.execute("SELECT COUNT(*) FROM raw_samples WHERE sent = 1").fetchone()[0] == 0

    assert drain_once(conn, client, cfg, key) == 3
    assert seen["url"] == "https://relay.test/v1/ingest"
    assert seen["headers"]["x-crowe-node"] == "cs-TEST00"
    assert seen["headers"]["content-encoding"] == "gzip"
    assert seen["headers"]["content-type"] == "application/x-ndjson"
    sig = base64.b64decode(seen["headers"]["x-crowe-signature"])
    key.public_key().verify(sig, seen["body"])
    assert conn.execute("SELECT COUNT(*) FROM raw_samples WHERE sent = 0").fetchone()[0] == 0


def test_relay_upload_network_error_is_false():
    def boom(request):
        raise httpx.ConnectError("down")
    client = httpx.Client(transport=httpx.MockTransport(boom))
    from crowe.uploader import Batch
    assert relay_upload(client, "https://relay.test", Batch([1], b"x", b"y"), "cs-a1b2c3") is False
