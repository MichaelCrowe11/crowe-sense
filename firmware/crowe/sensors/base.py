"""Sensor protocol and shared types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Reading:
    ts: str          # ISO 8601 UTC, e.g. 2026-06-14T21:00:00.123Z
    sensor: str      # "scd41"
    channel: str     # "co2_ppm"
    value: float
    unit: str        # "ppm"


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class I2CBus(Protocol):
    """The slice of smbus2 we actually use. Lets us mock cleanly in tests."""

    def read_i2c_block_data(self, addr: int, register: int, length: int) -> list[int]: ...
    def write_i2c_block_data(self, addr: int, register: int, data: list[int]) -> None: ...
    def write_byte(self, addr: int, byte: int) -> None: ...
    def read_byte(self, addr: int) -> int: ...


class Sensor(Protocol):
    """Every driver implements `name`, `period_s`, and async `read`."""

    name: str
    period_s: float

    async def read(self) -> list[Reading]: ...


def sensirion_crc(data: bytes) -> int:
    """CRC-8 used by Sensirion devices (SCD41, SHT45). Polynomial 0x31."""
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc
