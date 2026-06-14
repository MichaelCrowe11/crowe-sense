# 01 — System Architecture

## Goals

The Crowe Sensor is an environmental monitoring node that must:

1. Sample air-quality and light data on a sub-minute cadence, indefinitely.
2. Store raw + derived data locally so a site that loses backhaul for
   weeks loses **zero** measurement history.
3. Ship data to a central store over cellular, transparently, without
   requiring site Wi-Fi.
4. Be field-serviceable — a tech with a screwdriver can swap the storage
   drive, the hotspot, or the sensor stack independently.

## Block diagram

```
                ┌──────────────────────────────────────────────┐
                │              CROWE SENSOR NODE               │
                │                                              │
   12V DC ──────┼─► [Buck 5V/5A] ─┬─► Pi 5 USB-C PD           │
                │                  ├─► Sensor 3V3 rail        │
                │                  └─► Hotspot USB-C (5V/3A)  │
                │                                              │
                │   ┌──────────────┐    ┌────────────────┐    │
                │   │ Raspberry Pi │◄──►│ Sensor I2C bus │    │
                │   │     5 (8GB)  │    │ (0x10/44/62/76)│    │
                │   └──┬───────┬───┘    └────────────────┘    │
                │      │       │                              │
                │   USB 3.0  USB 2.0                          │
                │      │       │                              │
                │   ┌──▼───┐ ┌─▼──────────────────┐           │
                │   │ 1 TB │ │ AT&T Nighthawk M6  │           │
                │   │ HDD  │ │   (USB tether)     │───── 📶  │
                │   └──────┘ └────────────────────┘  TS-9     │
                │                                    antennas │
                └──────────────────────────────────────────────┘
                         │
                         ▼
                  ☁ Cloud (S3 + Postgres via Tailscale)
```

## Data flow

```
Sensors ──► sampler.py (asyncio, 0.5 Hz – 1 Hz)
              │
              ├──► SQLite WAL on /mnt/crowe/                    ← 1 TB drive
              │     (raw_samples, derived_metrics, events)
              │
              ├──► ring buffer in tmpfs (last 60 s)             ← memory
              │
              └──► uploader.py (batched, exponential backoff)
                         │
                         ▼
              wwan0 (Nighthawk tether) ─► s3://crowe-sense/{node_id}/
                         │
                         └─ fallback: wlan0 (site Wi-Fi) or wlan1 (Pi Wi-Fi)
```

## Subsystem boundaries

| Bay         | Owns                         | Replaceable without affecting     |
|-------------|------------------------------|------------------------------------|
| Compute     | Pi 5 + cooler + SD/NVMe boot | Storage, hotspot, sensors          |
| Storage     | 1 TB drive + foam pad        | Compute, hotspot, sensors          |
| Hotspot     | Nighthawk + antenna pigtails | Compute, storage, sensors          |
| Sensor      | I2C stack + camera           | Compute, storage, hotspot          |
| Power       | 12 V jack + buck + fuse      | All above (with brownout handling) |

This split is why the enclosure is a **bay-and-deck** design rather than a
monolithic cavity — each subsystem can be lifted out for service in under
60 seconds.

## Failure modes & responses

| Failure                          | Response                                    |
|----------------------------------|---------------------------------------------|
| 1 TB drive unmounts mid-flight   | Pi falls back to onboard NVMe ring buffer; flags `STORAGE_DEGRADED`; surfaces in next telemetry |
| Hotspot drops cellular           | Uploader switches to wlan0 if SSID present; otherwise queues and retries with backoff |
| Hotspot fully offline (no power) | Pi keeps logging locally; flags `BACKHAUL_OFFLINE`; surfaces on next sync |
| One I2C sensor NACKs             | Sampler marks that channel `STALE`; other channels continue |
| Brownout during write            | SQLite WAL mode + `synchronous=NORMAL` survives; uploader replays from last ack |

## Identity & provisioning

Each node has a 6-character `node_id` (e.g. `cs-7Q4F2A`) baked into
`/etc/crowe/node.toml` at first boot. The hotspot's IMEI is recorded
alongside so a swap can be reconciled in the fleet database.
