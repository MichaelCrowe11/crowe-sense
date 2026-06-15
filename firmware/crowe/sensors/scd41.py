"""Sensirion SCD41 — CO2 / temperature / humidity over I2C @ 0x62.

Datasheet: Sensirion SCD4x v1.3, section 3.5 ("Single Shot") and 3.6
("Periodic Measurement"). We use periodic at 5 s.
"""

from __future__ import annotations

import asyncio

from crowe.sensors.base import I2CBus, Reading, now_iso, sensirion_crc

ADDR = 0x62
CMD_START_PERIODIC = 0x21B1
CMD_READ_MEASUREMENT = 0xEC05
CMD_STOP_PERIODIC = 0x3F86


def _u16(cmd: int) -> list[int]:
    return [(cmd >> 8) & 0xFF, cmd & 0xFF]


class SCD41:
    name = "scd41"
    period_s = 5.0

    def __init__(self, bus: I2CBus, addr: int = ADDR):
        self._bus = bus
        self._addr = addr
        self._started = False

    def _send_command(self, cmd: int) -> None:
        msb, lsb = _u16(cmd)
        self._bus.write_i2c_block_data(self._addr, msb, [lsb])

    def _start(self) -> None:
        self._send_command(CMD_START_PERIODIC)
        self._started = True

    async def read(self) -> list[Reading]:
        if not self._started:
            self._start()
            await asyncio.sleep(5.0)

        self._send_command(CMD_READ_MEASUREMENT)
        await asyncio.sleep(0.001)
        msb, lsb = _u16(CMD_READ_MEASUREMENT)
        raw = self._bus.read_i2c_block_data(self._addr, msb, 9)

        co2 = self._decode(raw[0:3])
        t_raw = self._decode(raw[3:6])
        rh_raw = self._decode(raw[6:9])

        ts = now_iso()
        t_c = -45 + 175 * (t_raw / 65535)
        rh = 100 * (rh_raw / 65535)
        return [
            Reading(ts, self.name, "co2_ppm", float(co2), "ppm"),
            Reading(ts, self.name, "temperature_c", t_c, "C"),
            Reading(ts, self.name, "humidity_pct", rh, "%RH"),
        ]

    @staticmethod
    def _decode(block: list[int]) -> int:
        if sensirion_crc(bytes(block[0:2])) != block[2]:
            raise OSError("SCD41 CRC mismatch")
        return (block[0] << 8) | block[1]
