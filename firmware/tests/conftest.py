"""Shared test fixtures."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest


@dataclass
class FakeI2C:
    """Minimal I2C bus stub. Tests pre-seed responses keyed by (addr, register)."""
    responses: dict[tuple[int, int], list[int]] = field(default_factory=dict)
    writes: list[tuple[int, int, list[int]]] = field(default_factory=list)
    write_bytes: list[tuple[int, int]] = field(default_factory=list)
    on_write: Callable[[int, int, list[int]], None] | None = None

    def read_i2c_block_data(self, addr: int, register: int, length: int) -> list[int]:
        data = self.responses.get((addr, register))
        if data is None:
            raise OSError(f"no fake response for addr=0x{addr:02X} reg=0x{register:02X}")
        return data[:length]

    def write_i2c_block_data(self, addr: int, register: int, data: list[int]) -> None:
        self.writes.append((addr, register, list(data)))
        if self.on_write:
            self.on_write(addr, register, list(data))

    def write_byte(self, addr: int, byte: int) -> None:
        self.write_bytes.append((addr, byte))

    def read_byte(self, addr: int) -> int:
        return 0

    def queue(self, addr: int, register: int, data: list[int]) -> None:
        self.responses[(addr, register)] = data


@pytest.fixture
def fake_bus() -> FakeI2C:
    return FakeI2C()


@pytest.fixture
def tmp_config(tmp_path: Path, monkeypatch) -> Path:
    """Write a node.toml into tmp_path and point CROWE_CONFIG at it."""
    cfg_path = tmp_path / "node.toml"
    cfg_path.write_text(f"""
node_id = "cs-TEST00"
site = "test-site"
storage_mount = "{tmp_path}"
manifest_url = ""
private_key_path = "{tmp_path}/node.key"

[s3]
bucket = "test-bucket"
prefix = "raw"
region = "us-east-1"
endpoint_url = "http://localhost:9000"

[sampler.periods]
""")
    monkeypatch.setenv("CROWE_CONFIG", str(cfg_path))
    from crowe import config as _cfg
    _cfg.reset_cache()
    return cfg_path


@pytest.fixture
def stubs() -> dict:
    """Catch-all for ad-hoc state stashing in tests."""
    return defaultdict(list)
