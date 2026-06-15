"""Vishay VEML7700 — ambient light over I2C @ 0x10.

Datasheet: VEML7700 Rev 1.7. Default config: gain 1x, integration 100 ms,
which gives 0.0576 lux/count.
"""

from __future__ import annotations

import asyncio

from crowe.sensors.base import I2CBus, Reading, now_iso

ADDR = 0x10
REG_CONFIG = 0x00
REG_ALS = 0x04
LUX_PER_COUNT = 0.0576


class VEML7700:
    name = "veml7700"
    period_s = 1.0

    def __init__(self, bus: I2CBus, addr: int = ADDR):
        self._bus = bus
        self._addr = addr
        self._configured = False

    def _configure(self) -> None:
        # ALS_SD = 0 (power on), gain = 1x, integration = 100 ms
        self._bus.write_i2c_block_data(self._addr, REG_CONFIG, [0x00, 0x00])
        self._configured = True

    async def read(self) -> list[Reading]:
        if not self._configured:
            self._configure()
            await asyncio.sleep(0.5)

        raw = self._bus.read_i2c_block_data(self._addr, REG_ALS, 2)
        counts = raw[0] | (raw[1] << 8)
        lux = counts * LUX_PER_COUNT
        return [Reading(now_iso(), self.name, "illuminance_lux", lux, "lx")]
