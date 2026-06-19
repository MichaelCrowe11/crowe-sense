"""Bosch BME688 — T / RH / pressure / gas resistance over I2C @ 0x76.

On boot we read the 41-byte factory calibration block and apply Bosch's
compensation polynomials at sample time. The cloud receives engineering
units (°C, hPa, %RH, Ω) rather than raw counts.

Bosch's BSEC IAQ algorithm is closed-source; we publish calibrated gas
resistance and let the cloud derive IAQ from the time series.

Reference: BME68x datasheet rev 1.7, §3.3 (compensation) and §5
(register map). Compensation formulas match the public Bosch reference
driver (bme68x_sensor_api).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

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

# Calibration register blocks (datasheet §5.4)
REG_CAL_1_START = 0x8A   # 23 bytes through 0xA0
REG_CAL_1_LEN = 23
REG_CAL_2_START = 0xE1   # 14 bytes through 0xEE
REG_CAL_2_LEN = 14
REG_RES_HEAT_RANGE = 0x02
REG_RES_HEAT_VAL = 0x00
REG_RANGE_SW_ERR = 0x04

CHIP_ID = 0x61


def _u16(lsb: int, msb: int) -> int:
    return (msb << 8) | lsb


def _s16(lsb: int, msb: int) -> int:
    v = _u16(lsb, msb)
    return v - 0x10000 if v & 0x8000 else v


def _s8(b: int) -> int:
    return b - 0x100 if b & 0x80 else b


@dataclass(frozen=True, slots=True)
class Calibration:
    par_t1: int
    par_t2: int
    par_t3: int
    par_p1: int
    par_p2: int
    par_p3: int
    par_p4: int
    par_p5: int
    par_p6: int
    par_p7: int
    par_p8: int
    par_p9: int
    par_p10: int
    par_h1: int
    par_h2: int
    par_h3: int
    par_h4: int
    par_h5: int
    par_h6: int
    par_h7: int
    par_g1: int
    par_g2: int
    par_g3: int
    res_heat_range: int
    res_heat_val: int
    range_sw_err: int

    @classmethod
    def from_blocks(cls, blk1: list[int], blk2: list[int], heat_range: int,
                    heat_val: int, range_sw_err: int) -> Calibration:
        # blk1: registers 0x8A-0xA0 (23 bytes)
        # blk2: registers 0xE1-0xEE (14 bytes)
        par_t2 = _s16(blk1[0x8A - REG_CAL_1_START], blk1[0x8B - REG_CAL_1_START])
        par_t3 = _s8(blk1[0x8C - REG_CAL_1_START])
        par_p1 = _u16(blk1[0x8E - REG_CAL_1_START], blk1[0x8F - REG_CAL_1_START])
        par_p2 = _s16(blk1[0x90 - REG_CAL_1_START], blk1[0x91 - REG_CAL_1_START])
        par_p3 = _s8(blk1[0x92 - REG_CAL_1_START])
        par_p4 = _s16(blk1[0x94 - REG_CAL_1_START], blk1[0x95 - REG_CAL_1_START])
        par_p5 = _s16(blk1[0x96 - REG_CAL_1_START], blk1[0x97 - REG_CAL_1_START])
        par_p7 = _s8(blk1[0x98 - REG_CAL_1_START])
        par_p6 = _s8(blk1[0x99 - REG_CAL_1_START])
        par_p8 = _s16(blk1[0x9C - REG_CAL_1_START], blk1[0x9D - REG_CAL_1_START])
        par_p9 = _s16(blk1[0x9E - REG_CAL_1_START], blk1[0x9F - REG_CAL_1_START])
        par_p10 = blk1[0xA0 - REG_CAL_1_START]

        par_t1 = _u16(blk2[0xE9 - REG_CAL_2_START], blk2[0xEA - REG_CAL_2_START])
        par_h2 = (blk2[0xE1 - REG_CAL_2_START] << 4) | (blk2[0xE2 - REG_CAL_2_START] >> 4)
        par_h1 = (blk2[0xE3 - REG_CAL_2_START] << 4) | (blk2[0xE2 - REG_CAL_2_START] & 0x0F)
        par_h3 = _s8(blk2[0xE4 - REG_CAL_2_START])
        par_h4 = _s8(blk2[0xE5 - REG_CAL_2_START])
        par_h5 = _s8(blk2[0xE6 - REG_CAL_2_START])
        par_h6 = blk2[0xE7 - REG_CAL_2_START]
        par_h7 = _s8(blk2[0xE8 - REG_CAL_2_START])
        par_g2 = _s16(blk2[0xEB - REG_CAL_2_START], blk2[0xEC - REG_CAL_2_START])
        par_g1 = _s8(blk2[0xED - REG_CAL_2_START])
        par_g3 = _s8(blk2[0xEE - REG_CAL_2_START])

        return cls(
            par_t1=par_t1, par_t2=par_t2, par_t3=par_t3,
            par_p1=par_p1, par_p2=par_p2, par_p3=par_p3, par_p4=par_p4,
            par_p5=par_p5, par_p6=par_p6, par_p7=par_p7, par_p8=par_p8,
            par_p9=par_p9, par_p10=par_p10,
            par_h1=par_h1, par_h2=par_h2, par_h3=par_h3, par_h4=par_h4,
            par_h5=par_h5, par_h6=par_h6, par_h7=par_h7,
            par_g1=par_g1, par_g2=par_g2, par_g3=par_g3,
            res_heat_range=(heat_range >> 4) & 0x03,
            res_heat_val=_s8(heat_val),
            range_sw_err=_s8(range_sw_err) >> 4,
        )


def compensate_temperature(cal: Calibration, raw: int) -> tuple[float, float]:
    """Returns (calc_temp_c, t_fine). t_fine is reused by pressure + humidity."""
    var1 = (raw / 16384.0 - cal.par_t1 / 1024.0) * cal.par_t2
    var2 = ((raw / 131072.0 - cal.par_t1 / 8192.0)
            * (raw / 131072.0 - cal.par_t1 / 8192.0)) * cal.par_t3 * 16
    t_fine = var1 + var2
    return t_fine / 5120.0, t_fine


def compensate_pressure(cal: Calibration, raw: int, t_fine: float) -> float:
    """Pressure in hPa."""
    var1 = (t_fine / 2.0) - 64000.0
    var2 = var1 * var1 * (cal.par_p6 / 131072.0)
    var2 = var2 + (var1 * cal.par_p5 * 2.0)
    var2 = (var2 / 4.0) + (cal.par_p4 * 65536.0)
    var1 = (((cal.par_p3 * var1 * var1) / 16384.0)
            + (cal.par_p2 * var1)) / 524288.0
    var1 = (1.0 + (var1 / 32768.0)) * cal.par_p1
    if var1 == 0:
        return 0.0
    calc = 1048576.0 - raw
    calc = ((calc - (var2 / 4096.0)) * 6250.0) / var1
    var1 = (cal.par_p9 * calc * calc) / 2147483648.0
    var2 = calc * (cal.par_p8 / 32768.0)
    var3 = ((calc / 256.0) ** 3) * (cal.par_p10 / 131072.0)
    calc = calc + (var1 + var2 + var3 + (cal.par_p7 * 128.0)) / 16.0
    return calc / 100.0  # Pa -> hPa


def compensate_humidity(cal: Calibration, raw: int, temp_c: float) -> float:
    var1 = raw - ((cal.par_h1 * 16.0) + ((cal.par_h3 / 2.0) * temp_c))
    var2 = var1 * ((cal.par_h2 / 262144.0)
                   * (1.0 + ((cal.par_h4 / 16384.0) * temp_c)
                          + ((cal.par_h5 / 1048576.0) * temp_c * temp_c)))
    var3 = cal.par_h6 / 16384.0
    var4 = cal.par_h7 / 2097152.0
    rh = var2 + ((var3 + (var4 * temp_c)) * var2 * var2)
    return max(0.0, min(100.0, rh))


# Constants from Bosch reference driver for BME688 gas range compensation.
_LOOKUP_K1 = [
    0.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0, -0.8, 0.0, 0.0,
    -0.2, -0.5, 0.0, -1.0, 0.0, 0.0,
]
_LOOKUP_K2 = [
    0.0, 0.0, 0.0, 0.0, 0.1, 0.7, 0.0, -0.8, -0.1, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
]


def compensate_gas_resistance(raw_gas: int, gas_range: int, range_sw_err: int) -> float:
    """BME688 high-range gas resistance in ohms (per datasheet §3.3.5)."""
    var1 = 262144 >> gas_range
    var2 = raw_gas - 512
    var2 *= 3
    var2 = 4096 + var2
    if var2 == 0:
        return 0.0
    calc = 1000000.0 * var1 / var2
    # Range error correction (lookup tables)
    k1 = _LOOKUP_K1[gas_range]
    k2 = _LOOKUP_K2[gas_range]
    calc *= (1.0 + k1 * range_sw_err) * (1.0 + k2 * range_sw_err)
    return calc


class BME688:
    name = "bme688"
    period_s = 3.0

    def __init__(self, bus: I2CBus, addr: int = ADDR):
        self._bus = bus
        self._addr = addr
        self._configured = False
        self._cal: Calibration | None = None

    def _read_calibration(self) -> Calibration:
        blk1 = self._bus.read_i2c_block_data(self._addr, REG_CAL_1_START, REG_CAL_1_LEN)
        blk2 = self._bus.read_i2c_block_data(self._addr, REG_CAL_2_START, REG_CAL_2_LEN)
        heat_range = self._bus.read_i2c_block_data(self._addr, REG_RES_HEAT_RANGE, 1)[0]
        heat_val = self._bus.read_i2c_block_data(self._addr, REG_RES_HEAT_VAL, 1)[0]
        range_sw_err = self._bus.read_i2c_block_data(self._addr, REG_RANGE_SW_ERR, 1)[0]
        return Calibration.from_blocks(blk1, blk2, heat_range, heat_val, range_sw_err)

    def _configure(self) -> None:
        chip_id = self._bus.read_i2c_block_data(self._addr, REG_CHIP_ID, 1)[0]
        if chip_id != CHIP_ID:
            raise OSError(f"BME688 chip id mismatch: 0x{chip_id:02X}")

        self._cal = self._read_calibration()

        # ctrl_hum: humidity oversampling x1
        self._bus.write_i2c_block_data(self._addr, REG_CTRL_HUM, [0x01])
        # ctrl_meas: temp x2, press x16, mode=sleep (forced is set in read())
        self._bus.write_i2c_block_data(self._addr, REG_CTRL_MEAS, [(2 << 5) | (5 << 2) | 0])
        # 25 ms heater pulse; res_heat target ~320 °C
        self._bus.write_i2c_block_data(self._addr, REG_GAS_WAIT_0, [0x59])
        self._bus.write_i2c_block_data(self._addr, REG_RES_HEAT_0, [0xC0])
        # ctrl_gas_1: run_gas=1, nb_conv=0
        self._bus.write_i2c_block_data(self._addr, REG_CTRL_GAS_1, [0x10])
        self._configured = True

    async def read(self) -> list[Reading]:
        if not self._configured:
            self._configure()
        assert self._cal is not None

        ctrl_meas = (2 << 5) | (5 << 2) | 1
        self._bus.write_i2c_block_data(self._addr, REG_CTRL_MEAS, [ctrl_meas])
        await asyncio.sleep(0.180)

        block = self._bus.read_i2c_block_data(self._addr, REG_DATA_START, 17)
        press_raw = (block[2] << 12) | (block[3] << 4) | (block[4] >> 4)
        temp_raw = (block[5] << 12) | (block[6] << 4) | (block[7] >> 4)
        hum_raw = (block[8] << 8) | block[9]
        gas_raw = (block[15] << 2) | (block[16] >> 6)
        gas_range = block[16] & 0x0F
        gas_valid = bool(block[16] & 0x20)
        heat_stab = bool(block[16] & 0x10)

        temp_c, t_fine = compensate_temperature(self._cal, temp_raw)
        press_hpa = compensate_pressure(self._cal, press_raw, t_fine)
        rh = compensate_humidity(self._cal, hum_raw, temp_c)
        gas_ohm = compensate_gas_resistance(gas_raw, gas_range, self._cal.range_sw_err)

        ts = now_iso()
        readings = [
            Reading(ts, self.name, "temperature_c", temp_c, "C"),
            Reading(ts, self.name, "pressure_hpa", press_hpa, "hPa"),
            Reading(ts, self.name, "humidity_pct", rh, "%RH"),
            Reading(ts, self.name, "gas_valid", float(gas_valid and heat_stab), "bool"),
        ]
        if gas_valid and heat_stab:
            readings.append(Reading(ts, self.name, "gas_resistance_ohm", gas_ohm, "ohm"))
        return readings
