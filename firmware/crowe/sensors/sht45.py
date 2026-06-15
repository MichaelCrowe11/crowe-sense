"""Sensirion SHT45 — temperature + humidity over I2C @ 0x44.

Datasheet: SHT4x v1.1. We use the high-precision measurement (0xFD)
which takes ~8.2 ms.
"""

from __future__ import annotations

import asyncio

from crowe.sensors.base import I2CBus, Reading, now_iso, sensirion_crc

ADDR = 0x44
CMD_HIGH_PRECISION = 0xFD


class SHT45:
    name = "sht45"
    period_s = 1.0

    def __init__(self, bus: I2CBus, addr: int = ADDR):
        self._bus = bus
        self._addr = addr

    async def read(self) -> list[Reading]:
        self._bus.write_byte(self._addr, CMD_HIGH_PRECISION)
        await asyncio.sleep(0.01)
        raw = self._bus.read_i2c_block_data(self._addr, 0x00, 6)

        t_raw = self._decode(raw[0:3])
        rh_raw = self._decode(raw[3:6])

        ts = now_iso()
        t_c = -45 + 175 * (t_raw / 65535)
        rh = max(0.0, min(100.0, -6 + 125 * (rh_raw / 65535)))
        return [
            Reading(ts, self.name, "temperature_c", t_c, "C"),
            Reading(ts, self.name, "humidity_pct", rh, "%RH"),
        ]

    @staticmethod
    def _decode(block: list[int]) -> int:
        if sensirion_crc(bytes(block[0:2])) != block[2]:
            raise OSError("SHT45 CRC mismatch")
        return (block[0] << 8) | block[1]
