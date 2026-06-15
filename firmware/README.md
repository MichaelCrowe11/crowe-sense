# Firmware

Python services that run on the Pi 5 inside the Crowe Sensor. The
architectural shape is fixed in
[`../docs/04-firmware-architecture.md`](../docs/04-firmware-architecture.md);
this directory is the implementation.

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

- [x] All four sensor drivers with real I2C protocol (SCD41/SHT45 with
      Sensirion CRC, VEML7700 with documented lux scaling, BME688 with
      raw forced-mode reads).
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

- [ ] BME688 calibration polynomial — currently ships raw counts and
      delegates to the cloud receiver.
- [ ] BSEC IAQ algorithm (Bosch closed-source, optional).
- [ ] Camera capture + edge inference service.
- [ ] OTA agent that consumes `manifest_url`.
- [ ] Debian packaging (`.deb`) — install via pip for now.
