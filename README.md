# crowe-sense

Firmware and a printable enclosure for a Raspberry Pi 5 node that logs CO2, temperature, humidity, gas resistance and light to a local drive and uploads signed batches over cellular or Wi-Fi, for anyone monitoring a room or remote site.

The code and the design docs call the device the Crowe Sensor. The repo is crowe-sense. Same thing.

## Status

early stage. The firmware passes its unit tests against a fake I2C bus. We have not run it on a Pi with the sensors attached. The outdoor enclosure flag is a stub that changes no geometry. There is no camera code. Nothing reads `manifest_url`, so there is no over-the-air update agent. The uploader sends plain HTTP PUTs with a custom signature header and no AWS request signing, so it will only work against an endpoint that accepts unsigned writes. No receiver for those uploads lives in this repo.

## Install and first run

Run on 2026-09-10 on macOS with Python 3.13.14 in a fresh virtualenv. `pyproject.toml` requires Python 3.11 or newer.

```
$ cd firmware
$ python3 -m venv .venv && source .venv/bin/activate
$ pip install -q -e ".[dev]"
```

The install printed only a pip upgrade notice.

```
$ pytest -q
.........................                                                [100%]
25 passed in 0.88s
```

```
$ ruff check crowe/ tests/
All checks passed!
```

Each service installs as a console script. `--help` works for all five:

```
$ crowe-provision --help
usage: crowe-provision [-h] [--node-id NODE_ID] --site SITE
                       --s3-bucket S3_BUCKET [--storage-mount STORAGE_MOUNT]
                       [--config-dir CONFIG_DIR]
```

Provisioning does not need hardware. Pointed at a temp directory it writes a keypair and a node config:

```
$ crowe-provision --site demo-bench --s3-bucket example-bucket --config-dir /tmp/crowe-demo --storage-mount /tmp/crowe-demo/mnt
provisioned node cs-9D6DKS
config: /tmp/crowe-demo/node.toml
public key:
-----BEGIN PUBLIC KEY-----
<public key bytes>
-----END PUBLIC KEY-----

register this key with the fleet service, then reboot.

$ ls -l /tmp/crowe-demo
-rw-------  node.key
-rw-r--r--  node.pub
-rw-r--r--  node.toml
```

The health snapshot also runs without hardware. With no drive mounted and no default route in `/proc/net/route` it reports exactly that:

```
$ CROWE_CONFIG=/tmp/crowe-demo/node.toml crowe-health --print
{
  "node_id": "cs-9D6DKS",
  "site": "demo-bench",
  "ts": 1789097701.643672,
  "uptime_s": 52183,
  "drive": {
    "mounted": false,
    "free_gb": 0
  },
  "uplink": {
    "interface": null,
    "kind": null
  },
  "queue_depth": 0,
  "last_sample_ts": null,
  "load_avg": [
    6.74755859375,
    14.35888671875,
    12.81884765625
  ],
  "cpu_temp_c": null
}
```

Steps we did not run today: the Pi install in `firmware/README.md` (apt packages, the `crowe` user, the systemd units), `crowe-sampler`, `crowe-uploader` and `crowe-watchdog` against real sensors, and the OpenSCAD render (OpenSCAD is not installed on this machine). The GitHub Actions run for the current commit passed both jobs, lint plus tests and the five-part OpenSCAD render, on 2026-07-25.

## What runs today

Each item points at code and, where one exists, a test.

- Four I2C sensor drivers: SCD41 (CO2, temperature, humidity), SHT45 (temperature, humidity), BME688 (temperature, pressure, humidity, gas resistance with a `gas_valid` flag), VEML7700 (lux). `firmware/crowe/sensors/`, tested in `tests/test_sensors.py` against `FakeI2C`. The Sensirion CRC is checked against the datasheet vector.
- Sampler: one asyncio task per sensor with exponential backoff, writing rows to a SQLite database in WAL mode. `crowe/sampler.py`, `crowe/db.py`, `tests/test_db.py`.
- Uploader: gzips pending rows as JSON lines, signs the gzip with an ed25519 key, PUTs to an S3-style URL, and marks rows sent only after a 2xx. `crowe/uploader.py`, `tests/test_uploader.py`.
- Uplink selection: parses `/proc/net/route` and prefers a cellular interface, then Wi-Fi. `crowe/routing.py`, `tests/test_routing.py`.
- Drive check: reports whether the configured mount is a separate filesystem from root, plus free space. `crowe/storage.py`, `tests/test_storage.py`.
- Watchdog: heartbeat and fault LEDs through gpiozero, a hotspot power-cycle pulse after three consecutive backhaul failures with a one hour cooldown, and a status JSON file. Off hardware the pins are no-op stubs. `crowe/watchdog.py`. No unit test.
- Health snapshot: queue depth, mount state, uplink, load average, CPU temperature, printed or POSTed. `crowe/health.py`.
- Provisioning: generates the ed25519 keypair and writes `node.toml`. `crowe/provision.py`, `tests/test_provision.py`.
- systemd units for the four services and one hourly timer. `firmware/systemd/`.
- A parametric OpenSCAD enclosure that renders five printable parts (body, lid, sensor head, storage tray, hotspot bar) sized by editable drive and hotspot dimensions, with a print guide. `hardware/enclosure/`.
- A bill of materials with vendor and part numbers. `hardware/bom.csv`.
- Design docs for architecture, mechanical, electronics, firmware and assembly. `docs/`.

## Roadmap

None of this is built.

- Bring-up on a real Pi 5 with the four sensors on the I2C bus.
- A receiver that verifies the ed25519 signature and stores the batches.
- Bosch BSEC air quality index on top of the raw gas resistance.
- Camera capture service.
- An update agent that consumes `manifest_url`.
- Debian packaging.
- The outdoor enclosure variant (`outdoor = true` is a stub today).
- The tmpfs ring-buffer fallback and the Unix status socket that `docs/` describe. The code does not implement either.

## Limits

This has not run on hardware. The sensor drivers are verified against fake bus responses and datasheet constants, not against a reference instrument. The BME688 tests assert that outputs land in plausible ranges, nothing tighter.

There is no measurement data in this repo. Any Crowe Sense demo data shown elsewhere is synthetic.

This is not a safety device. Do not use its CO2 or gas readings for life safety, regulatory, or compliance decisions.

The upload path is unfinished. Requests carry a custom `X-Crowe-Signature` header and no AWS credentials. Nothing in this repo verifies that signature. The `--endpoint` for health and the "fleet service" the provisioner mentions do not exist here.

Placeholders: `outdoor = true` in the SCAD changes nothing. `manifest_url` is loaded and never read. The example config points at `manifests.crowe-sense.io`, which is a placeholder host. The docs describe a ring buffer fallback and a status socket that are not in the code.

The unit costs in `hardware/bom.csv` are the figures listed in that file. We did not check them against vendors today.

No security review has been done. The node's private key is written as an unencrypted PEM with mode 0600.

## License and contact

Apache License 2.0. See `LICENSE`.

michael@crowelogic.com
