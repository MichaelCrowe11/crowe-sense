"""Sensirion SDP810-500Pa differential pressure over I2C @ 0x25.

Datasheet: Sensirion SDP8xx digital, section 6.3 (continuous measurement). We start
continuous differential-pressure measurement with averaging (0x3615) and read 9 bytes:
dp (2 + crc), temperature (2 + crc), scale factor (2 + crc). dp_pa = int16 / scale.

Used on the flow-hood node: the tap sits across the HEPA prefilter, so the reading is
prefilter loading in pascals. Optional; enabled by `sensors.enabled` in node.toml.
"""

from __future__ import annotations

import asyncio

from crowe.sensors.base import I2CBus, Reading, now_iso, sensirion_crc

ADDR = 0x25
CMD_START_CONT_DP_AVG = 0x3615
CMD_STOP = 0x3FF9


class SDP810:
    name = "sdp810"
    period_s = 2.0

    def __init__(self, bus: I2CBus, addr: int = ADDR):
        self._bus = bus
        self._addr = addr
        self._started = False

    def _start(self) -> None:
        self._bus.write_i2c_block_data(self._addr, CMD_START_CONT_DP_AVG >> 8, [CMD_START_CONT_DP_AVG & 0xFF])
        self._started = True

    @staticmethod
    def decode(raw: list[int]) -> tuple[float, float]:
        """9 bytes -> (dp_pa, temp_c). Raises ValueError on a CRC mismatch."""
        if len(raw) < 9:
            raise ValueError("short read from SDP810")
        for i in (0, 3, 6):
            if sensirion_crc(bytes(raw[i:i + 2])) != raw[i + 2]:
                raise ValueError(f"SDP810 crc mismatch at byte {i}")
        dp_raw = int.from_bytes(bytes(raw[0:2]), "big", signed=True)
        t_raw = int.from_bytes(bytes(raw[3:5]), "big", signed=True)
        scale = int.from_bytes(bytes(raw[6:8]), "big", signed=False) or 60
        return dp_raw / scale, t_raw / 200.0

    async def read(self) -> list[Reading]:
        if not self._started:
            self._start()
            await asyncio.sleep(0.05)
        raw = self._bus.read_i2c_block_data(self._addr, 0x00, 9)
        dp_pa, t_c = self.decode(raw)
        ts = now_iso()
        return [
            Reading(ts, self.name, "prefilter_dp_pa", round(dp_pa, 3), "Pa"),
            Reading(ts, self.name, "temperature_c", round(t_c, 2), "C"),
        ]
