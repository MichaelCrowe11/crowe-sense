"""Bench proof of the cloud path for a pre-provisioned node, with no hardware.
Writes a handful of plausible readings into a temporary node database in the firmware's own
schema, then runs the real uploader once (signed, gzipped batch) against the deployed relay
using the kit's private key. A 2xx from /v1/ingest and rows in D1 prove the path end to end.
Usage: .venv/bin/python ../kits/bench_test.py ../kits/harrison-lf-01/etc-crowe/node.toml
"""
import os, sys, time, tempfile, sqlite3, re, pathlib, datetime
import httpx, socket
# BENCH_RESOLVE=host:ip pins one hostname to an IP at the Python level (SNI and the certificate stay
# correct) for a machine whose resolver has a stale negative cache for a freshly created record.
_pin = os.environ.get("BENCH_RESOLVE", "")
if _pin:
    _h, _ip = _pin.split(":", 1); _orig = socket.getaddrinfo
    def _gai(host, *a, **k):
        return _orig(_ip, *a, **k) if host == _h else _orig(host, *a, **k)
    socket.getaddrinfo = _gai
kit_toml = pathlib.Path(sys.argv[1]).resolve()
tmp = pathlib.Path(tempfile.mkdtemp(prefix="crowe-bench-"))
toml = kit_toml.read_text()
toml = re.sub(r'storage_mount = ".*"', f'storage_mount = "{tmp}"', toml)
cfg_path = tmp / "node.toml"; cfg_path.write_text(toml)
os.environ["CROWE_CONFIG"] = str(cfg_path)
from crowe import config, uploader
from crowe.db import open_db
cfg = config.load()
(cfg.storage_mount / "db").mkdir(parents=True, exist_ok=True)
conn = open_db(cfg.db_path)
now = time.time()
rows = []
for i in range(6):
    ts = datetime.datetime.fromtimestamp(now - 30 + i * 5, datetime.timezone.utc).isoformat()
    rows += [(ts, "sht45", "temperature_c", 18.6 + 0.05 * i, "C"),
             (ts, "sht45", "humidity_pct", 88.0 - 0.2 * i, "%"),
             (ts, "scd41", "co2_ppm", 940 + 6 * i, "ppm")]
conn.executemany("INSERT INTO raw_samples (ts, sensor, channel, value, unit) VALUES (?,?,?,?,?)", rows)
conn.commit()
key = uploader.load_private_key(cfg.private_key_path)
print(f"node {cfg.node_id} zone {cfg.zone} relay {cfg.relay_url}; {len(rows)} pending rows in {cfg.db_path}")
with httpx.Client(timeout=20) as client:
    sent = uploader.drain_once(conn, client, cfg, key)
left = conn.execute("SELECT count(*) FROM raw_samples WHERE sent=0").fetchone()[0]
print(f"drain_once sent={sent} pending_after={left}")
sys.exit(0 if sent == len(rows) and left == 0 else 2)
