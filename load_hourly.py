#!/usr/bin/env python3
"""Load the published Crowe Sense hourly aggregate (cs_hourly.csv) into a
sense.db the checker can read.

This is the widest real window available while the Pi is offline: 469 hours
spanning 2026-05-24 to 2026-06-16, aggregated from 3,596,420 raw readings.
Unlike the long-format export it keeps the zone names, so tent-1 and tent-2 are
known rather than inferred from row order.

What it costs. These are hourly MEANS, so an excursion is attenuated: a dip to
76.3% lasting forty minutes inside an hour reads as a milder hour. Durations
survive, extremes do not. Treat a "worst" value from this database as a floor
on how far the room actually went, never as the real extreme, and go to the raw
stream on the Pi for that.

The file also contains an 82-hour hole. sense_check.py excludes gaps far larger
than the observed cadence, so that outage is not charged to whichever band the
room was last outside.

  python3 load_hourly.py ~/zenodo-deposits/crowe-sense/cs_hourly.csv out.db
"""
from __future__ import annotations

import csv
import datetime as dt
import sqlite3
import sys

# Only what a grow zone's air can be judged on. The file also carries flow-hood
# and controller-health channels (soc_temp_c, core_volts, prefilter_load_pct);
# those describe equipment, not a room, and a temperature band must never meet
# the Pi's own die temperature.
KEEP = {"temperature_c", "humidity_pct", "co2_ppm", "vpd_kpa",
        "dew_point_c", "fruiting_score", "light_lux"}


def load(src: str, dest: str) -> None:
    con = sqlite3.connect(dest)
    con.execute("DROP TABLE IF EXISTS readings")
    con.execute("CREATE TABLE readings "
                "(epoch REAL, metric TEXT, value REAL, sensor TEXT)")

    written = 0
    dropped: set[str] = set()
    with open(src) as f:
        for row in csv.DictReader(f):
            stamp = row.get("hour_utc")
            if not stamp:
                continue
            epoch = (dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
                     .replace(tzinfo=dt.timezone.utc).timestamp())
            for col, raw in row.items():
                if col == "hour_utc" or raw in (None, ""):
                    continue
                zone, _, metric = col.partition(".")
                if not metric:
                    continue
                if metric not in KEEP:
                    dropped.add(metric)
                    continue
                con.execute("INSERT INTO readings VALUES (?,?,?,?)",
                            (epoch, metric, float(raw), zone))
                written += 1

    con.execute("CREATE INDEX ix ON readings(sensor, metric, epoch)")
    con.commit()

    print(f"wrote {written} hourly means from {src}")
    if dropped:
        print(f"  not a zone condition, skipped: {', '.join(sorted(dropped))}")
    for row in con.execute(
            "SELECT sensor, metric, COUNT(*), ROUND(MIN(value),1), "
            "ROUND(AVG(value),1), ROUND(MAX(value),1) FROM readings "
            "GROUP BY sensor, metric ORDER BY sensor, metric"):
        print("  %-16s %-15s n=%-5d min=%-8s mean=%-8s max=%s" % row)
    lo, hi = con.execute("SELECT MIN(epoch), MAX(epoch) FROM readings").fetchone()
    print(f"  span {dt.datetime.fromtimestamp(lo):%Y-%m-%d %H:%M} to "
          f"{dt.datetime.fromtimestamp(hi):%Y-%m-%d %H:%M}")
    con.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    load(sys.argv[1], sys.argv[2])
