"""Sampler service — polls every sensor on its own cadence, writes to SQLite."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sqlite3
from collections.abc import Iterable

from crowe import config
from crowe.db import open_db
from crowe.sensors import BME688, SCD41, SHT45, VEML7700, Reading, Sensor
from crowe.sensors.base import I2CBus

log = logging.getLogger("crowe.sampler")

INSERT_SQL = (
    "INSERT INTO raw_samples (ts, sensor, channel, value, unit) "
    "VALUES (?, ?, ?, ?, ?)"
)


def write_batch(conn: sqlite3.Connection, readings: Iterable[Reading]) -> None:
    rows = [(r.ts, r.sensor, r.channel, r.value, r.unit) for r in readings]
    conn.executemany(INSERT_SQL, rows)


async def _run_sensor(s: Sensor, conn: sqlite3.Connection) -> None:
    """One task per sensor — independent cadence, independent failure domain."""
    backoff = 1.0
    while True:
        try:
            readings = await s.read()
            write_batch(conn, readings)
            backoff = 1.0
        except Exception:
            log.exception("sensor %s failed; backing off %.1fs", s.name, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)
            continue
        await asyncio.sleep(s.period_s)


def _open_bus(bus_no: int) -> I2CBus:
    from smbus2 import SMBus  # imported lazily so tests don't need the dep
    return SMBus(bus_no)  # type: ignore[return-value]


def _build_sensors(bus: I2CBus, overrides: dict[str, float]) -> list[Sensor]:
    sensors: list[Sensor] = [SCD41(bus), SHT45(bus), BME688(bus), VEML7700(bus)]
    for s in sensors:
        if s.name in overrides:
            s.period_s = overrides[s.name]  # type: ignore[misc]
    return sensors


async def run(conn: sqlite3.Connection, sensors: list[Sensor]) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    async with asyncio.TaskGroup() as tg:
        for s in sensors:
            tg.create_task(_run_sensor(s, conn))
        await stop.wait()
        raise asyncio.CancelledError


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--bus", type=int, default=1)
    args = p.parse_args()

    cfg = config.load()
    conn = open_db(cfg.db_path)
    bus = _open_bus(args.bus)
    sensors = _build_sensors(bus, cfg.sampler_period_overrides)

    log.info("sampler started: %d sensors on bus %d", len(sensors), args.bus)
    try:
        asyncio.run(run(conn, sensors))
    except asyncio.CancelledError:
        log.info("sampler shutting down cleanly")


if __name__ == "__main__":
    main()
