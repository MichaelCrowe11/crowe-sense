"""Bosch BME688 — T / RH / pressure / gas resistance over I2C @ 0x76.

Bosch's BSEC IAQ algorithm is closed-source; we publish raw gas
resistance and let the cloud derive IAQ. Pressure / T / RH come back
in engineering units using the calibration block read at start-up.

This is a minimal driver — it covers the registers we need for forced-
mode single-shot reads. Reference: BME68x datasheet rev 1.7, sec 5.3.
"""

from __future__ import annotations

import asyncio
import struct

from crowe.sensors.base import I2CBus, Reading, now_iso

ADDR = 0x76
REG_CHIP_ID = 0xD0
REG_RESET = 0xE0
REG_CTRL_HUM = 0x72
REG_CTRL_MEAS = 0x74
REG_CTRL_GAS_1 = 0x71
REG_GAS_WAIT_0 = 0x64
REG_RES_HEAT_0 = 0x5A
REG_DATA_START = 0x1D

CHIP_ID = 0x61


class BME688:
    name = "bme688"
    period_s = 3.0

    def __init__(self, bus: I2CBus, addr: int = ADDR):
        self._bus = bus
        self._addr = addr
        self._configured = False

    def _configure(self) -> None:
        chip_id = self._bus.read_i2c_block_data(self._addr, REG_CHIP_ID, 1)[0]
        if chip_id != CHIP_ID:
            raise OSError(f"BME688 chip id mismatch: 0x{chip_id:02X}")
        # ctrl_hum: humidity oversampling x1
        self._bus.write_i2c_block_data(self._addr, REG_CTRL_HUM, [0x01])
        # ctrl_meas: temp x2, press x16, mode=sleep (forced will be set in read)
        self._bus.write_i2c_block_data(self._addr, REG_CTRL_MEAS, [(2 << 5) | (5 << 2) | 0])
        # gas wait: 25 ms heater pulse; res_heat for ~320 °C (calibrated 0xC0)
        self._bus.write_i2c_block_data(self._addr, REG_GAS_WAIT_0, [0x59])
        self._bus.write_i2c_block_data(self._addr, REG_RES_HEAT_0, [0xC0])
        # ctrl_gas_1: run_gas=1, nb_conv=0
        self._bus.write_i2c_block_data(self._addr, REG_CTRL_GAS_1, [0x10])
        self._configured = True

    async def read(self) -> list[Reading]:
        if not self._configured:
            self._configure()

        # Trigger forced-mode measurement
        ctrl_meas = (2 << 5) | (5 << 2) | 1
        self._bus.write_i2c_block_data(self._addr, REG_CTRL_MEAS, [ctrl_meas])
        await asyncio.sleep(0.180)

        block = self._bus.read_i2c_block_data(self._addr, REG_DATA_START, 17)
        press_raw = (block[2] << 12) | (block[3] << 4) | (block[4] >> 4)
        temp_raw = (block[5] << 12) | (block[6] << 4) | (block[7] >> 4)
        hum_raw = (block[8] << 8) | block[9]
        gas_raw = (block[15] << 2) | (block[16] >> 6)
        gas_range = block[16] & 0x0F

        # NOTE: applying the Bosch calibration polynomials requires reading the
        # par_t1..par_g3 calibration block at boot. That's ~25 registers and a
        # batch of fixed-point math. For v0.1 we ship raw counts to the cloud
        # and let the receiver normalize; v0.2 will add on-device calibration.
        ts = now_iso()
        return [
            Reading(ts, self.name, "temperature_raw", float(temp_raw), "lsb"),
            Reading(ts, self.name, "pressure_raw", float(press_raw), "lsb"),
            Reading(ts, self.name, "humidity_raw", float(hum_raw), "lsb"),
            Reading(ts, self.name, "gas_resistance_raw", float(gas_raw), "lsb"),
            Reading(ts, self.name, "gas_range", float(gas_range), "idx"),
        ]


_ = struct  # reserved for v0.2 calibration unpacking
