# Firmware

Python services that run on the Pi 5 inside the Crowe Sensor. The
architectural shape is fixed in
[`../docs/04-firmware-architecture.md`](../docs/04-firmware-architecture.md);
this directory is the implementation.


## The descriptor and the operations door (2026-09-13)

| module | does |
|---|---|
| `crowe/descriptor.py` | builds the device descriptor from node.toml, the driver table and the operations registry; `GET /v1/describe` |
| `crowe/operations.py` | the registry (`indicator.identify`, `uplink.reset`), validation with hard bounds, the SQLite queue, cooldowns, the executor, the operator token check |
| `crowe/api.py` | `OperationsService`: `/v1/describe`, `/v1/operations`, `POST /v1/operations/{id}` (operator bearer, direct only) |
| `crowe/watchdog.py` | `build_executor()` + a tick in the loop; identify blinks all three LEDs; status.json gains `gpio`, `operations`, `identifying` |
| `crowe/uploader.py` | `publish_descriptor()` on start and daily, signed like a batch |
| `crowe/mcp.py` | the node as an MCP server (stdio, stdlib); `crowe-sense-mcp`, or `python3 ../mcp_server.py` from a checkout |

node.toml: `[device] tags = [...]` (descriptive), `[operations] enabled = false`,
`token_path = "/etc/crowe/operator.token"`, optional `simulate = true` on a bench.
`crowe-provision --operations --tag "..."` writes them and mints the token (mode 600).

Tests: `tests/test_operations.py`, `test_descriptor.py`, `test_api_operations.py`,
`test_mcp.py`, and the publish case in `test_relay_uploader.py`.

## Layout

```
firmware/
├── crowe/
│   ├── config.py        Loads /etc/crowe/node.toml
│   ├── db.py            SQLite WAL schema + helpers
│   ├── sensors/
│   │   ├── base.py      Protocol, Reading, Sensirion CRC
│   │   ├── scd41.py     CO2 / T / RH
│   │   ├── sht45.py     Precision T / RH
│   │   ├── bme688.py    T / RH / pressure / gas resistance
│   │   └── veml7700.py  Lux
│   ├── sampler.py       asyncio task per sensor → SQLite
│   ├── storage.py       1 TB drive mount detection
│   ├── routing.py       Cellular vs Wi-Fi route selection
│   ├── uploader.py      SQLite → gzip → ed25519 sign → S3 PUT
│   ├── watchdog.py      LEDs, hotspot reset, /run/crowe/status.json
│   ├── health.py        Hourly snapshot to fleet receiver
│   └── provision.py     First-boot setup CLI
├── systemd/             4 unit files + 1 timer
├── config/node.toml.example
├── tests/               pytest suite, no hardware required
└── pyproject.toml
```

## Install + run on a Pi

```bash
# As root
apt install -y python3-pip i2c-tools
adduser --system --group crowe
adduser crowe i2c
adduser crowe gpio

# As crowe (or via pipx as root)
pip install /opt/crowe-sense/firmware

# First-boot provisioning (writes /etc/crowe/node.toml + ed25519 keypair)
sudo crowe-provision --site mycology-lab-01 --s3-bucket crowe-sense-telemetry

# Install systemd units
cp firmware/systemd/*.service firmware/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now crowe-sampler crowe-uploader crowe-watchdog crowe-health.timer
```

The sampler will refuse to start if `/etc/crowe/node.toml` is missing
(via the systemd `ConditionPathExists`).

## Run the tests

```bash
cd firmware
pip install -e .[dev]
pytest -q
```

The suite uses fakes for I2C (`tests/conftest.py::FakeI2C`) and writes to
a temporary SQLite file. No hardware needed — CI passes on any Linux.

## What's done in this commit

- [x] All four sensor drivers with real I2C protocol: SCD41/SHT45 with
      Sensirion CRC, VEML7700 with documented lux scaling, BME688 with
      full on-device compensation (T/P/H/gas polynomials per Bosch
      reference, plus gas_valid + heat_stab gating).
- [x] Sampler with per-sensor asyncio tasks, exponential backoff,
      WAL-mode SQLite logging.
- [x] Uploader with batched gzipped jsonl, ed25519 signing, route-aware
      uplink selection.
- [x] Watchdog with LED heartbeat, fault indication, hotspot reset
      (uses `gpiozero` on hardware, no-op stub elsewhere for tests).
- [x] Health reporter on a 1 h systemd timer.
- [x] Provisioner CLI that generates the keypair and writes `node.toml`.
- [x] Test suite covering sensors (with CRC vector verification),
      database, routing, uploader, storage, and provisioning.
- [x] systemd units matching the user/group, mount, and capability
      constraints from `docs/05-assembly-guide.md`.

## What's not done yet

- [ ] BSEC IAQ algorithm (Bosch closed-source, optional). The driver
      ships calibrated gas resistance; cloud-side time-series IAQ is
      next.
- [ ] Camera capture + edge inference service.
- [ ] OTA agent that consumes `manifest_url`.
- [ ] Debian packaging (`.deb`) — install via pip for now.
