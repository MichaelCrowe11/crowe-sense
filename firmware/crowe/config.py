"""Node configuration loader.

Reads /etc/crowe/node.toml (or CROWE_CONFIG env var). The node is
provisioned once at first boot; this module exposes the parsed values
to every service.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
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

    @property
    def db_path(self) -> Path:
        return self.storage_mount / "db" / "samples.sqlite"

    @property
    def frames_dir(self) -> Path:
        return self.storage_mount / "frames"


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
    )


def reset_cache() -> None:
    load.cache_clear()
