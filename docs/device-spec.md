# Crowe Sense v1 node: device specification

Crowe Sense is a sensing node for a growing room. It reads the air, keeps every reading on
the node, serves them on the local network, and pushes signed batches to the Crowe Sense
relay so the same numbers appear in the desktop app, the web app, the phone, Cortex, the
terminal and any display that mounts the panel. Firmware, enclosure and apps are in this
repository; the contract they all share is `contracts/telemetry-v1.md`.

## Two builds from one design

| | Indoor pilot (this raise) | Field variant (already designed) |
|---|---|---|
| Enclosure | `site/model/crowe-sense-enclosure.scad`: louvered radiation-shield head over the sensor stack, Pi 5 on standoffs over a vented floor | `hardware/enclosure/crowe_sensor_enclosure.scad`: adds a 1 TB drive bay and a cellular hotspot bay, six printed parts |
| Power | official 27 W USB-C supply | 12 V barrel jack, 5 V/5 A buck, polyfuse |
| Backhaul | site Wi-Fi or Ethernet | hotspot in its bay, failover to Wi-Fi (`crowe/routing.py`) |
| Storage | 64 GB microSD, SQLite in WAL mode | plus the 1 TB drive at `/mnt/crowe` for camera frames |
| Node cost | about $278 (4 GB Pi) | about $600 with the hotspot and drive |

Both run the same firmware; the difference is `node.toml` and which STL you print.

## Sensing

| Quantity | Sensor | Bus | Cadence | Metric(s) |
|---|---|---|---|---|
| CO2, T, RH | Sensirion SCD41 (true NDIR) | I2C 0x62 | 5 s | `co2_ppm`, `temperature_c`, `humidity_pct` |
| Reference T, RH | Sensirion SHT45 | I2C 0x44 | 1 s | `temperature_c`, `humidity_pct` (wins over the others) |
| VOC, pressure | Bosch BME688 | I2C 0x76 | 3 s | `gas_ohms`, `pressure_hpa`, plus its own T and RH |
| Light | Vishay VEML7700 | I2C 0x10 | 1 s | `light_lux` |
| Prefilter loading (hood node) | Sensirion SDP810-500Pa | I2C 0x25 | 2 s | `prefilter_dp_pa` |
| Controller | sysfs + vcgencmd | | 30 s | `soc_temp_c`, `arm_clock_mhz`, `core_volts`, `undervoltage_now`, `throttled_now` |
| Derived on read | | | | `vpd_kpa`, `dew_point_c` (Tetens; `sensor: derived`, `quality: est`) |

The head is a radiation shield: louvers pass air and block radiant heat from lights, so
the reading is the room and not the box. The SHT45 sits highest in the stack, the SCD41
below it with its vent facing the louvers, the BME688 and VEML7700 on the outer face.

## Compute and software on the node

Raspberry Pi 5 (4 GB), Raspberry Pi OS Lite 64-bit, Python 3.11+. Four services, all
in `firmware/systemd/`:

| Service | Does |
|---|---|
| `crowe-sampler` | one asyncio task per sensor, independent cadence and failure domain, writes `raw_samples` |
| `crowe-api` | the read contract on :8078 and the kiosk page at `/` |
| `crowe-uploader` | drains unsent rows every 30 s or 1000 rows into a gzipped NDJSON batch, signs it with the node's Ed25519 key, POSTs to the relay, marks rows sent only on 2xx |
| `crowe-watchdog` and `crowe-health.timer` | restarts a stalled sampler, reports queue depth and drive state |

Nothing leaves the node unsigned, and nothing is deleted from the node when it is sent.

## Cloud

One Cloudflare Worker (`relay/`) on `sense.crowelogic.com`: D1 for the last 30 days of
readings, R2 for every raw batch forever, Crowe ID for every read. It runs on the
Cloudflare credit the company already holds ($99,657 to June 2027, under 1% used), so
the cloud line of this device is zero for the life of the pilot.

## Surfaces

| Surface | Where | State (2026-09-01) |
|---|---|---|
| Node display (House, kiosk) | `integrations/house/` | web component + kiosk autostart, built |
| Desktop (Electron) | `integrations/desktop/` | writes measured rows into the Cultivation Environment lane; 14 tests, branch `feat/crowe-sense` |
| Web (crowelogic.com) | `integrations/web/` | edge forwards `/app/sense/*` to the relay with the user's Crowe ID; patch ready, Michael deploys |
| Mobile and macOS (Tauri) | `app/` | 0.2.0, direct or cloud source, compiles; iOS signing recipe in `integrations/mobile/` |
| Terminal | `integrations/cli/` | `crowe sense status|latest|history|check|pair|nodes|use`; 25 tests, branch `feat/crowe-sense` |
| Cortex | `integrations/cortex/` | Sense panel in the workbench; 8 tests, branch `feat/crowe-sense` |

## What is proven and what is not

Proven: the firmware's drivers, sampler, uploader and API pass 51 hardware-free tests;
the relay passes 7 end-to-end tests including signature verification; every surface
renders the contract from a scripted node. In May and June 2026 an earlier daemon ran
the full path (daemon, SQLite, API, apps) for 23 days and 3.6 million rows.

Not proven: no Crowe Sense node has yet run with physical sensors in a growing room.
The 2026 stream's tent channels were found on 2026-08-04 not to be sensor measurements
(see `archive/PROVENANCE-CORRECTION.md`), and the test that found it,
`analysis/provenance_check.py`, now gates every dataset this company publishes. The
pilot in `docs/investor-report.md` exists to put real sensors in real rooms and pass
that test on the first week of data.
