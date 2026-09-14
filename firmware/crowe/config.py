"""Node configuration loader.

Reads /etc/crowe/node.toml (or CROWE_CONFIG env var). The node is
provisioned once at first boot; this module exposes the parsed values
to every service.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("/etc/crowe/node.toml")


@dataclass(frozen=True, slots=True)
class S3Config:
    bucket: str
    prefix: str
    region: str
    endpoint_url: str | None = None


DEFAULT_SENSORS = ("scd41", "sht45", "bme688", "veml7700", "pi")
DEFAULT_RELAY = "https://sense.crowelogic.com"

ACTUATOR_KINDS = ("exhaust_fan",)


@dataclass(frozen=True, slots=True)
class ActuatorConfig:
    """One declared actuator. A node advertises an actuator only when node.toml
    declares it here; the code for a kind existing is not the same as the hardware
    being wired. Limits are the operator's, within the kind's own ceilings."""
    name: str
    kind: str
    pin: int
    max_on_s: float = 900.0
    min_off_s: float = 120.0
    min_co2_ppm: float = 0.0
    max_reading_age_s: float = 180.0


@dataclass(frozen=True, slots=True)
class NodeConfig:
    node_id: str
    site: str
    storage_mount: Path
    s3: S3Config | None
    sampler_period_overrides: dict[str, float]
    manifest_url: str
    private_key_path: Path
    zone: str = ""
    relay_url: str = ""
    sensors_enabled: tuple[str, ...] = DEFAULT_SENSORS
    api_port: int = 8078
    # The writable half of the node (crowe/operations.py). Off unless node.toml
    # turns it on, and then only with an operator token on the direct path.
    operations_enabled: bool = False
    operator_token_path: Path = Path("/etc/crowe/operator.token")
    operations_simulate: bool = False
    # Driver tags: what a person knows about this installation that the code
    # does not (where the head sits, what the room is for). Descriptive only;
    # nothing here changes what the node enforces.
    tags: tuple[str, ...] = ()
    actuators: dict[str, ActuatorConfig] = field(default_factory=dict)

    @property
    def db_path(self) -> Path:
        return self.storage_mount / "db" / "samples.sqlite"

    @property
    def frames_dir(self) -> Path:
        return self.storage_mount / "frames"

    @property
    def operations_db_path(self) -> Path:
        return self.storage_mount / "db" / "operations.sqlite"


def _config_path() -> Path:
    env = os.environ.get("CROWE_CONFIG")
    return Path(env) if env else DEFAULT_CONFIG_PATH


@lru_cache(maxsize=1)
def load() -> NodeConfig:
    path = _config_path()
    with path.open("rb") as f:
        data = tomllib.load(f)

    s3 = data.get("s3")
    relay = data.get("relay", {})
    sensors = data.get("sensors", {})
    ops = data.get("operations", {})
    device = data.get("device", {})
    actuators = _parse_actuators(data.get("actuators", {}))
    return NodeConfig(
        node_id=data["node_id"],
        site=data["site"],
        storage_mount=Path(data.get("storage_mount", "/mnt/crowe")),
        s3=S3Config(
            bucket=s3["bucket"],
            prefix=s3.get("prefix", ""),
            region=s3.get("region", "us-east-1"),
            endpoint_url=s3.get("endpoint_url"),
        ) if s3 and s3.get("bucket") else None,
        sampler_period_overrides=data.get("sampler", {}).get("periods", {}),
        manifest_url=data.get("manifest_url", ""),
        private_key_path=Path(data.get("private_key_path", "/etc/crowe/node.key")),
        zone=data.get("zone") or data["node_id"],
        relay_url=str(relay.get("url", "")).rstrip("/"),
        sensors_enabled=tuple(sensors.get("enabled", DEFAULT_SENSORS)),
        api_port=int(data.get("api", {}).get("port", 8078)),
        operations_enabled=bool(ops.get("enabled", False)),
        operator_token_path=Path(ops.get("token_path", "/etc/crowe/operator.token")),
        operations_simulate=bool(ops.get("simulate", False)),
        tags=tuple(str(t).strip() for t in device.get("tags", []) if str(t).strip()),
        actuators=actuators,
    )


def _parse_actuators(raw: dict) -> dict[str, ActuatorConfig]:
    """[actuators.<name>] tables. An unknown kind or a missing pin is refused at load,
    not skipped: a node that silently drops an actuator would advertise less than it
    has wired, and that is the dangerous direction."""
    out: dict[str, ActuatorConfig] = {}
    for name, spec in (raw or {}).items():
        if not isinstance(spec, dict):
            raise ValueError(f"[actuators.{name}] must be a table")
        kind = str(spec.get("kind", name))
        if kind not in ACTUATOR_KINDS:
            raise ValueError(f"[actuators.{name}] kind {kind!r} is not one of {ACTUATOR_KINDS}")
        if "pin" not in spec:
            raise ValueError(f"[actuators.{name}] needs a pin")
        out[str(name)] = ActuatorConfig(
            name=str(name), kind=kind, pin=int(spec["pin"]),
            max_on_s=float(spec.get("max_on_s", 900.0)), min_off_s=float(spec.get("min_off_s", 120.0)),
            min_co2_ppm=float(spec.get("min_co2_ppm", 0.0)), max_reading_age_s=float(spec.get("max_reading_age_s", 180.0)),
        )
    return out


def reset_cache() -> None:
    load.cache_clear()
