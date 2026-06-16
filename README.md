# crowe-sense

[![CI](https://github.com/MichaelCrowe11/crowe-sense/actions/workflows/ci.yml/badge.svg)](https://github.com/MichaelCrowe11/crowe-sense/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

> **Status:** Firmware implemented and tested (25 hardware-free unit tests, green CI: lint + tests + per-part STL renders). Enclosure is parametric OpenSCAD with a published BOM. Hardware bring-up validation is the remaining frontier.

Crowe Sensor — modular, 3D-printable environmental sensing node designed for
remote / off-grid deployment. Built around a Raspberry Pi 5 compute core with
dedicated, swappable bays for a **1 TB portable storage drive** and an
**AT&T cellular Wi-Fi hotspot** so the unit can log long horizons of telemetry
and ship data home without relying on site Wi-Fi.

## What's in this repo

```
crowe-sense/
├── docs/
│   ├── 01-system-architecture.md   System overview, block diagram, data flow
│   ├── 02-mechanical-design.md     Enclosure geometry, bays, tolerances
│   ├── 03-electronics-integration.md  Wiring, power, I2C bus, USB topology
│   ├── 04-firmware-architecture.md Pi-side services, storage, sync
│   └── 05-assembly-guide.md        Step-by-step build instructions
├── hardware/
│   ├── enclosure/
│   │   ├── crowe_sensor_enclosure.scad   Parametric OpenSCAD master
│   │   └── README.md                     Print settings & tolerances
│   ├── pinouts/sensor_pinout.md         GPIO/I2C/USB pin map
│   └── bom.csv                          Bill of materials
└── firmware/                             Pi-side Python services (implemented, 25 tests passing)
```

## System at a glance

| Subsystem        | Component                              | Interface          |
|------------------|----------------------------------------|--------------------|
| Compute          | Raspberry Pi 5 (8 GB)                  | —                  |
| Bulk storage     | 1 TB 2.5" portable USB drive           | USB 3.0 (Pi)       |
| Cellular backhaul| AT&T Nighthawk M6 / M6 Pro hotspot     | USB-C tether / Wi-Fi |
| CO2 + T + RH     | Sensirion SCD41                        | I2C @ 0x62         |
| Precision T + RH | Sensirion SHT45                        | I2C @ 0x44         |
| VOC + IAQ        | Bosch BME688                           | I2C @ 0x76         |
| Light            | VEML7700                               | I2C @ 0x10         |
| Optional vision  | Pi Camera Module 3                     | CSI                |
| Power            | 12 V DC in → buck to 5 V/5 A           | barrel jack        |

Full bill of materials: [`hardware/bom.csv`](hardware/bom.csv).

## Why this design

The two "found components" — a 1 TB portable drive and an AT&T Wi-Fi hotspot —
unlock two capabilities a typical IoT node lacks:

1. **Local persistence at scale.** The Pi can log raw sensor frames + camera
   stills + edge-inference results to the 1 TB drive for weeks to months
   without rotation. The drive lives in a dedicated, vibration-isolated bay
   that pops out for offload.
2. **Backhaul independence.** The Nighthawk lives in its own bay with antenna
   passthroughs and a USB-C tether to the Pi. The Pi treats it as primary
   uplink with automatic failover to site Wi-Fi if available.

Both bays are **parametric** — change three numbers at the top of
[`crowe_sensor_enclosure.scad`](hardware/enclosure/crowe_sensor_enclosure.scad)
and the slot resizes for a different drive or a different hotspot model.

## Quick start

1. Print the enclosure: [`hardware/enclosure/README.md`](hardware/enclosure/README.md)
2. Source the BOM: [`hardware/bom.csv`](hardware/bom.csv)
3. Wire it up: [`docs/03-electronics-integration.md`](docs/03-electronics-integration.md)
4. Flash + provision: [`docs/05-assembly-guide.md`](docs/05-assembly-guide.md)

## Open questions (please confirm)

- Exact 1 TB drive model and dimensions (we assume WD Elements 2.5" envelope).
- Exact AT&T hotspot model (we assume Nighthawk M6 / MR6500).
- Indoor lab or outdoor / weather-exposed deployment? Affects IP rating and
  the gland / vent specs in `02-mechanical-design.md`.
- Camera in v1 or v2? Affects the front-panel cutout pattern.
