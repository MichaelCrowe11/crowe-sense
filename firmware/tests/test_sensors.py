"""Sensor driver unit tests against the FakeI2C bus."""

from __future__ import annotations

import pytest

from crowe.sensors import BME688, SCD41, SHT45, VEML7700
from crowe.sensors.base import sensirion_crc
from crowe.sensors.bme688 import (
    Calibration,
    compensate_humidity,
    compensate_pressure,
    compensate_temperature,
)


def _sensirion_block(value: int) -> list[int]:
    msb, lsb = (value >> 8) & 0xFF, value & 0xFF
    return [msb, lsb, sensirion_crc(bytes([msb, lsb]))]


def test_sensirion_crc_known_vector():
    # Datasheet example: 0xBE 0xEF -> 0x92
    assert sensirion_crc(b"\xBE\xEF") == 0x92


async def test_scd41_decodes_co2_t_rh(fake_bus):
    co2_block = _sensirion_block(1234)
    t_block = _sensirion_block(int((25 + 45) / 175 * 65535))   # ~25 C
    rh_block = _sensirion_block(int(50 / 100 * 65535))         # ~50 %
    fake_bus.queue(0x62, 0xEC, co2_block + t_block + rh_block)

    sensor = SCD41(fake_bus)
    sensor._started = True  # skip the warm-up sleep
    readings = await sensor.read()

    assert {r.channel for r in readings} == {"co2_ppm", "temperature_c", "humidity_pct"}
    co2 = next(r for r in readings if r.channel == "co2_ppm")
    assert co2.value == 1234
    t = next(r for r in readings if r.channel == "temperature_c")
    assert abs(t.value - 25.0) < 0.05
    rh = next(r for r in readings if r.channel == "humidity_pct")
    assert abs(rh.value - 50.0) < 0.1


async def test_scd41_crc_mismatch_raises(fake_bus):
    bad = [0x04, 0xD2, 0x00] + _sensirion_block(0) + _sensirion_block(0)
    fake_bus.queue(0x62, 0xEC, bad)
    sensor = SCD41(fake_bus)
    sensor._started = True
    with pytest.raises(OSError, match="CRC mismatch"):
        await sensor.read()


async def test_sht45_decodes_t_rh(fake_bus):
    t_block = _sensirion_block(int((20 + 45) / 175 * 65535))
    rh_block = _sensirion_block(int((40 + 6) / 125 * 65535))
    fake_bus.queue(0x44, 0x00, t_block + rh_block)

    sensor = SHT45(fake_bus)
    readings = await sensor.read()
    by_channel = {r.channel: r.value for r in readings}
    assert abs(by_channel["temperature_c"] - 20.0) < 0.05
    assert abs(by_channel["humidity_pct"] - 40.0) < 0.1


async def test_veml7700_lux_scaling(fake_bus):
    counts = 10000
    fake_bus.queue(0x10, 0x04, [counts & 0xFF, (counts >> 8) & 0xFF])
    sensor = VEML7700(fake_bus)
    sensor._configured = True
    readings = await sensor.read()
    assert len(readings) == 1
    assert abs(readings[0].value - counts * 0.0576) < 0.001


# ----------------------- BME688 calibration -----------------------
#
# Calibration coefficients pulled from a real BME688 unit (Bosch dev kit).
# These are the values we use to verify the compensation polynomials
# produce physically sensible outputs.
_REFERENCE_CAL = Calibration(
    par_t1=26063, par_t2=26243, par_t3=3,
    par_p1=36325, par_p2=-10489, par_p3=88,
    par_p4=8237, par_p5=-129, par_p6=30,
    par_p7=46, par_p8=-3056, par_p9=-89, par_p10=30,
    par_h1=761, par_h2=996, par_h3=0,
    par_h4=45, par_h5=20, par_h6=120, par_h7=-100,
    par_g1=-43, par_g2=-12714, par_g3=18,
    res_heat_range=1, res_heat_val=51, range_sw_err=0,
)


def test_bme688_temperature_compensation_room_temperature():
    # Raw value chosen so calc_temp lands in a physically plausible range.
    # The exact value depends on the per-unit calibration above; we only
    # assert the polynomial produces a sensible temperature.
    temp_c, t_fine = compensate_temperature(_REFERENCE_CAL, raw=520000)
    assert 0.0 < temp_c < 60.0
    assert t_fine > 0


def test_bme688_temperature_compensation_monotonic():
    a, _ = compensate_temperature(_REFERENCE_CAL, raw=510000)
    b, _ = compensate_temperature(_REFERENCE_CAL, raw=520000)
    c, _ = compensate_temperature(_REFERENCE_CAL, raw=530000)
    assert a < b < c


def test_bme688_pressure_in_sane_range():
    _, t_fine = compensate_temperature(_REFERENCE_CAL, raw=520000)
    # Raw pressure that corresponds to ~1013 hPa at sea level on this unit
    p_hpa = compensate_pressure(_REFERENCE_CAL, raw=400000, t_fine=t_fine)
    assert 800 < p_hpa < 1100


def test_bme688_humidity_clamps_to_0_100():
    temp_c, _ = compensate_temperature(_REFERENCE_CAL, raw=520000)
    rh_low = compensate_humidity(_REFERENCE_CAL, raw=0, temp_c=temp_c)
    rh_high = compensate_humidity(_REFERENCE_CAL, raw=65535, temp_c=temp_c)
    assert 0.0 <= rh_low <= 100.0
    assert 0.0 <= rh_high <= 100.0


def _u16_bytes(v: int) -> list[int]:
    return [v & 0xFF, (v >> 8) & 0xFF]


def _seed_bme688(fake_bus) -> None:
    """Pre-load FakeI2C with a calibration block + chip ID + a frame."""
    # Chip ID
    fake_bus.queue(0x76, 0xD0, [0x61])

    # Calibration block 1 (0x8A..0xA0, 23 bytes)
    blk1 = [0] * 23
    cal = _REFERENCE_CAL
    blk1[0x8A - 0x8A:0x8C - 0x8A] = _u16_bytes(cal.par_t2 & 0xFFFF)
    blk1[0x8C - 0x8A] = cal.par_t3 & 0xFF
    blk1[0x8E - 0x8A:0x90 - 0x8A] = _u16_bytes(cal.par_p1)
    blk1[0x90 - 0x8A:0x92 - 0x8A] = _u16_bytes(cal.par_p2 & 0xFFFF)
    blk1[0x92 - 0x8A] = cal.par_p3 & 0xFF
    blk1[0x94 - 0x8A:0x96 - 0x8A] = _u16_bytes(cal.par_p4 & 0xFFFF)
    blk1[0x96 - 0x8A:0x98 - 0x8A] = _u16_bytes(cal.par_p5 & 0xFFFF)
    blk1[0x98 - 0x8A] = cal.par_p7 & 0xFF
    blk1[0x99 - 0x8A] = cal.par_p6 & 0xFF
    blk1[0x9C - 0x8A:0x9E - 0x8A] = _u16_bytes(cal.par_p8 & 0xFFFF)
    blk1[0x9E - 0x8A:0xA0 - 0x8A] = _u16_bytes(cal.par_p9 & 0xFFFF)
    blk1[0xA0 - 0x8A] = cal.par_p10
    fake_bus.queue(0x76, 0x8A, blk1)

    # Calibration block 2 (0xE1..0xEE, 14 bytes)
    blk2 = [0] * 14
    blk2[0xE1 - 0xE1] = (cal.par_h2 >> 4) & 0xFF
    blk2[0xE2 - 0xE1] = ((cal.par_h2 & 0x0F) << 4) | (cal.par_h1 & 0x0F)
    blk2[0xE3 - 0xE1] = (cal.par_h1 >> 4) & 0xFF
    blk2[0xE4 - 0xE1] = cal.par_h3 & 0xFF
    blk2[0xE5 - 0xE1] = cal.par_h4 & 0xFF
    blk2[0xE6 - 0xE1] = cal.par_h5 & 0xFF
    blk2[0xE7 - 0xE1] = cal.par_h6 & 0xFF
    blk2[0xE8 - 0xE1] = cal.par_h7 & 0xFF
    blk2[0xE9 - 0xE1:0xEB - 0xE1] = _u16_bytes(cal.par_t1)
    blk2[0xEB - 0xE1:0xED - 0xE1] = _u16_bytes(cal.par_g2 & 0xFFFF)
    blk2[0xED - 0xE1] = cal.par_g1 & 0xFF
    blk2[0xEE - 0xE1] = cal.par_g3 & 0xFF
    fake_bus.queue(0x76, 0xE1, blk2)

    fake_bus.queue(0x76, 0x02, [cal.res_heat_range << 4])
    fake_bus.queue(0x76, 0x00, [cal.res_heat_val & 0xFF])
    fake_bus.queue(0x76, 0x04, [(cal.range_sw_err & 0x0F) << 4])

    # Sample frame: encode raw temp ~520000, pressure ~400000, hum ~25000,
    # gas_valid + heat_stab set, gas_range = 4
    frame = [0] * 17
    press_raw = 400000
    temp_raw = 520000
    hum_raw = 25000
    gas_raw = 600
    gas_range = 4
    frame[2] = (press_raw >> 12) & 0xFF
    frame[3] = (press_raw >> 4) & 0xFF
    frame[4] = (press_raw & 0x0F) << 4
    frame[5] = (temp_raw >> 12) & 0xFF
    frame[6] = (temp_raw >> 4) & 0xFF
    frame[7] = (temp_raw & 0x0F) << 4
    frame[8] = (hum_raw >> 8) & 0xFF
    frame[9] = hum_raw & 0xFF
    frame[15] = (gas_raw >> 2) & 0xFF
    frame[16] = ((gas_raw & 0x03) << 6) | 0x20 | 0x10 | gas_range
    fake_bus.queue(0x76, 0x1D, frame)


async def test_bme688_end_to_end_produces_engineering_units(fake_bus):
    _seed_bme688(fake_bus)
    sensor = BME688(fake_bus)
    readings = await sensor.read()

    by_channel = {r.channel: r for r in readings}
    assert "temperature_c" in by_channel
    assert "pressure_hpa" in by_channel
    assert "humidity_pct" in by_channel
    assert "gas_valid" in by_channel
    assert "gas_resistance_ohm" in by_channel

    assert by_channel["temperature_c"].unit == "C"
    assert by_channel["pressure_hpa"].unit == "hPa"
    assert by_channel["humidity_pct"].unit == "%RH"
    assert by_channel["gas_resistance_ohm"].unit == "ohm"

    # Sanity bounds — values should be in physical ranges
    assert 0 < by_channel["temperature_c"].value < 60
    assert 800 < by_channel["pressure_hpa"].value < 1100
    assert 0 <= by_channel["humidity_pct"].value <= 100
    assert 100 < by_channel["gas_resistance_ohm"].value < 1e8
    assert by_channel["gas_valid"].value == 1.0


async def test_bme688_gas_invalid_omits_resistance(fake_bus):
    _seed_bme688(fake_bus)
    # Re-seed the frame with gas_valid=0
    frame = [0] * 17
    frame[2] = (400000 >> 12) & 0xFF
    frame[3] = (400000 >> 4) & 0xFF
    frame[4] = (400000 & 0x0F) << 4
    frame[5] = (520000 >> 12) & 0xFF
    frame[6] = (520000 >> 4) & 0xFF
    frame[7] = (520000 & 0x0F) << 4
    frame[8] = (25000 >> 8) & 0xFF
    frame[9] = 25000 & 0xFF
    frame[16] = 0x04  # gas_range=4, gas_valid=0, heat_stab=0
    fake_bus.queue(0x76, 0x1D, frame)

    sensor = BME688(fake_bus)
    readings = await sensor.read()
    channels = {r.channel for r in readings}
    assert "gas_resistance_ohm" not in channels
    gas_valid = next(r for r in readings if r.channel == "gas_valid")
    assert gas_valid.value == 0.0
