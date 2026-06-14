# Firmware

The runtime that lives on the Pi 5. This directory is intentionally
empty in this commit — the architectural shape is fixed in
[`docs/04-firmware-architecture.md`](../docs/04-firmware-architecture.md)
and the Python implementation lands in follow-up commits so it can be
reviewed independently of the hardware design.

## What will go here

```
firmware/
├── crowe/
│   ├── __init__.py
│   ├── sampler.py        I2C sensor polling → SQLite
│   ├── uploader.py       SQLite → S3 batched ship
│   ├── watchdog.py       Liveness, hotspot reset, LEDs
│   ├── health.py         Hourly status snapshot
│   ├── sensors/
│   │   ├── scd41.py
│   │   ├── sht45.py
│   │   ├── bme688.py
│   │   └── veml7700.py
│   ├── storage.py        Mount detection, ring-buffer fallback
│   ├── routing.py        Cellular vs Wi-Fi route selection
│   └── config.py         /etc/crowe/node.toml loader
├── systemd/
│   ├── crowe-sampler.service
│   ├── crowe-uploader.service
│   ├── crowe-watchdog.service
│   └── crowe-health.timer
├── debian/               packaging
├── tests/
└── pyproject.toml
```

## Why not in this PR

Three reasons:

1. The hardware design needs to be reviewed and printed first — the
   firmware should be written against the real bus and the real
   storage mount.
2. The Python services are testable in isolation (mock I2C, mock S3)
   and deserve their own review with their own test plan.
3. The cloud receiver schema is a separate decision and will pin the
   uploader's wire format. Better to land it once, not twice.

## Next steps

Once the body has printed and the I2C bus is verified at
`i2cdetect -y 1`, the firmware work order is:

1. Stub each sensor driver against the Sensirion / Bosch reference
   datasheets.
2. Wire up SQLite WAL + the schema migration table.
3. Write the uploader against a local minio for testing.
4. Add the systemd units and the debian packaging.
5. Bench burn-in on a real Pi 5 with the real 1 TB drive.
