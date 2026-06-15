"""Sensor driver unit tests against the FakeI2C bus."""

from __future__ import annotations

import pytest

from crowe.sensors import SCD41, SHT45, VEML7700
from crowe.sensors.base import sensirion_crc


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
