# 04 — Firmware / Software Architecture

## OS baseline

- **Raspberry Pi OS Lite, 64-bit (Bookworm)** flashed to the microSD or
  NVMe boot.
- Read-only root (`overlayroot`) on the boot media. All mutable state
  lives on `/mnt/crowe`, the 1 TB drive.
- `systemd-timesyncd` against `time.cloudflare.com` over the cellular
  link; fallback to GPS PPS if a HAT is installed (future).

## Service layout

Three long-running systemd units, plus a one-shot health reporter:

```
systemd
 ├── crowe-sampler.service        Polls I2C sensors, writes to SQLite
 ├── crowe-uploader.service       Drains SQLite → S3 in batches
 ├── crowe-watchdog.service       Liveness, hotspot reset, LED state
 └── crowe-health.timer           Hourly health snapshot
```

Each service runs as the `crowe` user, with `CapabilityBoundingSet=`
limited to what it needs (sampler gets `CAP_SYS_NICE`, uploader gets
none, watchdog gets `CAP_SYS_RAWIO` for the GPIO reset line).

## Storage layout on the 1 TB drive

```
/mnt/crowe/
├── db/
│   ├── samples.sqlite      raw sensor samples (WAL mode)
│   ├── samples.sqlite-wal
│   └── samples.sqlite-shm
├── frames/
│   └── 2026/06/14/         camera stills, JPEG, hourly
├── inference/
│   └── 2026/06/14/         TFLite outputs, JSON-lines
├── logs/
│   └── journal/            persistent journald
└── tmp/                     uploader staging
```

The drive is mounted with `defaults,noatime,nofail,x-systemd.device-timeout=10`
in `/etc/fstab`. `nofail` is critical — the Pi must still boot if the
drive is missing (we degrade to NVMe ring buffer).

### Why SQLite, not Postgres/Timescale

- Single-writer, append-mostly workload. SQLite handles it fine.
- Zero ops: no server, no port, no auth surface.
- Backups are file-copies of three files.
- The uploader streams rows out and `VACUUM`s monthly. The DB stays small
  (~5 MB/day at 1 Hz across 4 sensors). 1 TB is for camera frames and
  inference outputs, not the relational data.

## Sampler

```python
# crowe/sampler.py (sketch — full impl follows in a later commit)
async def main():
    bus = SMBus(1)
    sensors = [SCD41(bus), SHT45(bus), BME688(bus), VEML7700(bus)]
    db = sqlite3.connect("/mnt/crowe/db/samples.sqlite", isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")

    async with asyncio.TaskGroup() as tg:
        for s in sensors:
            tg.create_task(s.run(period_s=s.period, sink=db))
```

Each sensor task has its own cadence (SCD41 at 5 s, SHT45 at 1 s,
BME688 at 3 s, VEML7700 at 1 s) and writes through a small `sink`
abstraction so the same code can target SQLite, a ring buffer, or stdout
for debugging.

## Uploader

- Drains rows in batches of 1000 or 30 seconds, whichever first.
- Gzips the batch, signs it with the node's ed25519 key, PUTs to
  `s3://crowe-sense/{node_id}/{yyyy}/{mm}/{dd}/{hh}/{batch_id}.jsonl.gz`.
- On success, marks rows `sent=1`. A nightly job deletes rows older than
  30 days with `sent=1`.
- Routing decision: prefers `wwan0` (Nighthawk tether) but uses
  `wlan0` if it has a default route and a recent successful upload.
  Implemented as a `Routing` class that reads `/proc/net/route` rather
  than fighting with NetworkManager.

## Watchdog

- Heartbeats to the green LED every 1 s.
- Tracks last successful upload time; after 3 consecutive 60 s failures,
  asserts GPIO 23 to power-cycle the hotspot.
- Tracks `/mnt/crowe` mount state; if it disappears, sets red LED and
  switches the sampler to its NVMe ring buffer.
- Exposes a Unix socket at `/run/crowe/status.sock` so the health
  reporter can query "are we OK?" without scraping logs.

## Health reporter

Every hour, posts a 1 KB JSON status blob to the cloud:

```json
{
  "node_id": "cs-7Q4F2A",
  "ts": "2026-06-14T21:00:00Z",
  "uptime_s": 88400,
  "drive": {"mounted": true, "free_gb": 924, "model": "WD Elements 1TB"},
  "cellular": {"rssi_dbm": -78, "rsrp_dbm": -102, "carrier": "AT&T", "tech": "5G NSA"},
  "sensors": {"scd41": "ok", "sht45": "ok", "bme688": "ok", "veml7700": "ok"},
  "queue_depth": 0,
  "last_upload_s_ago": 42
}
```

This is the single fleet-monitoring source-of-truth — if the cloud
hasn't seen a heartbeat from a node in 2 h, alert.

## OTA updates

- A small `crowe-agent` polls a manifest at
  `https://manifests.crowe-sense.io/{node_id}/current.json` over HTTPS.
- Manifest pins versions for sampler / uploader / watchdog.
- Updates download to `/mnt/crowe/tmp/`, verify signature, then atomic
  `systemctl reload-or-restart`.
- Rollback is just a previous manifest pointer; no state migration
  because the schema is migration-versioned and forward-compatible.

## Edge inference (optional)

If the Pi Camera Module 3 is fitted:

- `crowe-vision.service` runs a TFLite model on captured stills.
- Default model: a small classifier for mushroom-cultivation conditions
  (contamination indicators, fruiting body presence). Configurable per
  node via the manifest.
- Outputs go to `/mnt/crowe/inference/` and are sampled into the upload
  batches at 1/N rate (where N is fleet-tuned to keep cellular cost
  reasonable).

## What's NOT included in this doc

Actual Python implementation, the deb packaging, and the cloud receiver
are scoped for follow-up commits. This doc fixes the **shape** of the
system so the hardware design and the firmware can converge.
