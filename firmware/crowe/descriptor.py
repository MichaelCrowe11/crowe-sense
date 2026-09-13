"""The device descriptor: what this node can measure, what it can do, and what it
enforces, as one document any agent or program can read before touching it.

This is what the public description of Anthropic's Model Hardware Standard calls
the reference file: compiled from the node's configuration, its driver registry and
its operations registry, with a person's tags alongside. The tags are descriptive.
They never add an operation, widen a bound or promise an interlock; every enforced
limit listed here names the code that enforces it and has a test that proves it.

Served at GET /v1/describe on the node, published to the relay by the uploader and
served there at GET /v1/nodes/{node}/describe. Contract: contracts/device-descriptor-v0.md.

Not a claim of conformance to the Model Hardware Standard, whose specification is
not public as of 2026-09. The schema id is Crowe's own so that an adapter can map it
to the published spec without renaming anything here.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from crowe import config, operations
from crowe.metrics import PREFERRED

SCHEMA_ID = "https://sense.crowelogic.com/contracts/device-descriptor.v0.json"
DESCRIPTOR_VERSION = 0
MODEL = "crowe-sense-v1"
FIRMWARE_VERSION = "0.2.0"
STALE_AFTER_S = 180.0
RELAY_DEFAULT = "https://sense.crowelogic.com"

# Every driver the sampler can build, with what it reports. Ranges are the maker's
# specified measurement range, given so a reader can tell a plausible value from a
# fault. They are not safety limits and nothing enforces them.
SENSORS: dict[str, dict[str, Any]] = {
    "scd41": {"model": "Sensirion SCD41 (NDIR)", "bus": "i2c 0x62", "period_s": 5.0, "channels": [
        ("co2_ppm", "ppm", [400, 5000]), ("temperature_c", "C", [-10, 60]), ("humidity_pct", "%", [0, 100])]},
    "sht45": {"model": "Sensirion SHT45", "bus": "i2c 0x44", "period_s": 1.0, "channels": [
        ("temperature_c", "C", [-40, 125]), ("humidity_pct", "%", [0, 100])]},
    "bme688": {"model": "Bosch BME688", "bus": "i2c 0x76", "period_s": 3.0, "channels": [
        ("gas_ohms", "ohm", None), ("pressure_hpa", "hPa", [300, 1100]),
        ("temperature_c", "C", [-40, 85]), ("humidity_pct", "%", [0, 100])]},
    "veml7700": {"model": "Vishay VEML7700", "bus": "i2c 0x10", "period_s": 1.0, "channels": [
        ("light_lux", "lux", [0, 120000])]},
    "sdp810": {"model": "Sensirion SDP810-500Pa", "bus": "i2c 0x25", "period_s": 2.0, "channels": [
        ("prefilter_dp_pa", "Pa", [-500, 500])]},
    "pi": {"model": "Raspberry Pi 5 controller", "bus": "sysfs, vcgencmd", "period_s": 30.0, "channels": [
        ("soc_temp_c", "C", None), ("arm_clock_mhz", "MHz", None), ("core_volts", "V", None),
        ("undervoltage_now", "", None), ("throttled_now", "", None)]},
}
CONTROLLER_SENSORS = {"pi"}

DERIVED = [
    {"metric": "vpd_kpa", "unit": "kPa", "depends_on": ["temperature_c", "humidity_pct"], "algorithm": "tetens-air-vpd"},
    {"metric": "dew_point_c", "unit": "C", "depends_on": ["temperature_c", "humidity_pct"], "algorithm": "tetens-dew-point"},
]

QUALITY_STATES = {
    "ok": "a fresh reading from a settled sensor",
    "warming": "the sensor is not yet stable after power-on",
    "stale": f"older than {STALE_AFTER_S:g} s",
    "est": "derived from other readings, not measured",
    "fault": "the driver reported a fault",
}


def measurements(sensors_enabled: tuple[str, ...], zone: str) -> list[dict[str, Any]]:
    by_metric: dict[str, dict[str, Any]] = {}
    for name in sensors_enabled:
        spec = SENSORS.get(name)
        if not spec:
            continue
        kind = "controller" if name in CONTROLLER_SENSORS else "measured"
        for metric, unit, rng in spec["channels"]:
            m = by_metric.setdefault(metric, {
                "metric": metric, "unit": unit, "kind": kind,
                "zone": "pi" if kind == "controller" else zone, "sources": [], "history": True,
            })
            m["sources"].append({"sensor": name, "model": spec["model"], "bus": spec["bus"],
                                 "period_s": spec["period_s"], "measurement_range": rng})
    out = []
    for metric, m in by_metric.items():
        order = PREFERRED.get(metric)
        present = [s["sensor"] for s in m["sources"]]
        m["preferred_source"] = next((s for s in order if s in present), present[0]) if order else present[0]
        out.append(m)
    have = {m["metric"] for m in out}
    for d in DERIVED:
        if all(dep in have for dep in d["depends_on"]):
            out.append({"metric": d["metric"], "unit": d["unit"], "kind": "derived", "zone": zone,
                        "sources": [], "preferred_source": "derived", "history": False,
                        "depends_on": d["depends_on"], "algorithm": d["algorithm"], "quality": "est"})
    return out


def executor_status(status_path: Path | None, now: float) -> dict[str, Any]:
    """What the watchdog last said about itself, read from its status file. The API
    process cannot see the pins, so it reports what the pin owner reported and how
    old that report is, rather than guessing."""
    if not status_path:
        return {"gpio": "unknown", "status_age_s": None}
    try:
        st = json.loads(Path(status_path).read_text())
    except (OSError, ValueError):
        return {"gpio": "unknown", "status_age_s": None}
    gpio = st.get("gpio", "unknown")
    ts = st.get("ts")
    return {"gpio": gpio if isinstance(gpio, bool) else "unknown",
            "status_age_s": round(now - float(ts), 1) if isinstance(ts, (int, float)) else None}


def summary(doc: dict[str, Any]) -> str:
    ident = doc["identity"]
    ms = doc["measurements"]
    measured = [m for m in ms if m["kind"] == "measured"]
    derived = [m for m in ms if m["kind"] == "derived"]
    ops = doc["operations"]
    lines = [
        f"Crowe Sense node {ident['node']} ({ident['model']}, firmware {ident['firmware']}) at site "
        f"{ident['site']}, sensor head in zone {ident['zone']}.",
        "Measures: " + ", ".join(f"{m['metric']} in {m['unit'] or 'unitless'} from {m['preferred_source']}" for m in measured) + ".",
    ]
    if derived:
        lines.append("Derives: " + ", ".join(m["metric"] for m in derived) + " (estimates, quality est).")
    if ops["enabled"]:
        lines.append("Operations (" + str(len(ops["list"])) + ", enabled): " +
                     "; ".join(f"{o['id']}: {o['effect']}" for o in ops["list"]) + ".")
    else:
        lines.append("Operations: disabled on this node; it is read-only until an operator enables them in node.toml.")
    lines.append("Writes are accepted only on the direct path with an operator token. The relay is read-only.")
    if doc["annotations"]["tags"]:
        lines.append("Operator notes: " + " ".join(t if t.endswith(".") else t + "." for t in doc["annotations"]["tags"]))
    return " ".join(lines)


def _revision(doc: dict[str, Any]) -> str:
    stable = {k: v for k, v in doc.items() if k not in ("revision", "generated_ts")}
    stable = json.loads(json.dumps(stable))
    stable["operations"] = {k: v for k, v in stable["operations"].items() if k != "executor"}
    return hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def build(cfg: config.NodeConfig, *, status_path: Path | None = None, now: float | None = None,
          relay_url: str | None = None, host: str = "<node>") -> dict[str, Any]:
    now = time.time() if now is None else now
    relay = (relay_url or cfg.relay_url or RELAY_DEFAULT).rstrip("/")
    doc: dict[str, Any] = {
        "schema": SCHEMA_ID,
        "descriptor_version": DESCRIPTOR_VERSION,
        "revision": "",
        "generated_ts": round(now, 3),
        "identity": {
            "node": cfg.node_id, "site": cfg.site, "zone": cfg.zone, "model": MODEL,
            "firmware": FIRMWARE_VERSION, "contract": "telemetry-v1",
        },
        "measurements": measurements(cfg.sensors_enabled, cfg.zone),
        "quality_states": QUALITY_STATES,
        "freshness": {"stale_after_s": STALE_AFTER_S},
        "operations": {
            "enabled": bool(cfg.operations_enabled),
            "simulate": bool(cfg.operations_simulate),
            "auth": "operator bearer token, direct path only",
            "executor": executor_status(status_path, now),
            "list": operations.public_registry(),
        },
        "access": {
            "direct": {
                "base": f"http://{host}:{cfg.api_port}",
                "reads": True,
                "writes": bool(cfg.operations_enabled),
                "auth": {"reads": "none; LAN or tailnet only", "writes": "operator bearer token"},
                "paths": {"describe": "/v1/describe", "latest": "/v1/latest", "history": "/v1/history",
                          "operations": "/v1/operations", "request": "POST /v1/operations/{id}"},
            },
            "relay": {
                "base": f"{relay}/v1/nodes/{cfg.node_id}",
                "reads": True,
                "writes": False,
                "auth": "Crowe ID bearer",
                "paths": {"describe": "/describe", "latest": "/latest", "history": "/history"},
            },
            "write_path": "direct-only",
        },
        "annotations": {
            "tags": list(cfg.tags),
            "summary": "",
            "provenance": "generated by crowe.descriptor from node.toml, the driver registry and the operations "
                          "registry; tags are a person's notes and change nothing the node enforces",
        },
        "standards": {
            "informed_by": [{"name": "Model Hardware Standard", "publisher": "Anthropic",
                             "status": "research preview announced 2026-08-27; specification not public"}],
            "conformance_claimed": [],
        },
    }
    doc["annotations"]["summary"] = summary(doc)
    doc["revision"] = _revision(doc)
    return doc


def for_node(status_path: Path | None = Path("/run/crowe/status.json"), **kw) -> dict[str, Any]:
    return build(config.load(), status_path=status_path, **kw)
