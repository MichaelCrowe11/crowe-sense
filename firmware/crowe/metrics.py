"""The metric vocabulary of contracts/telemetry-v1.md, and which driver wins a metric
when several report it. Shared by the uploader (what leaves the node) and the local
API (what the apps see), so the two can never disagree."""

from __future__ import annotations

# Driver channel name -> contract metric name. Anything not listed passes through.
CHANNEL_TO_METRIC = {
    "gas_resistance_ohm": "gas_ohms",
}

# When more than one driver reports a metric, the first one present wins.
PREFERRED = {
    "temperature_c": ("sht45", "scd41", "bme688"),
    "humidity_pct": ("sht45", "scd41", "bme688"),
    "pressure_hpa": ("bme688",),
}

CHART_METRICS = ("temperature_c", "humidity_pct", "co2_ppm")

UNIT_NORMALISE = {"%RH": "%", "ohm": "ohm", "C": "C"}


def metric_for(channel: str) -> str:
    return CHANNEL_TO_METRIC.get(channel, channel)


def unit_for(unit: str) -> str:
    return UNIT_NORMALISE.get(unit, unit)


def rank(metric: str, sensor: str) -> int:
    """Lower is better. Unranked sensors sort after every ranked one."""
    order = PREFERRED.get(metric)
    if not order:
        return 0
    return order.index(sensor) if sensor in order else len(order)
