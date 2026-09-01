#!/usr/bin/env python3
"""Load a Crowe Sense long-format CSV export back into a sense.db, recovering
the zone column the export dropped.

Why this is not a straight import. The export is epoch,metric,value with NO
sensor column, and the rig writes two tents. So temperature_c arrives as 9,904
rows over 5,091 distinct epochs: pairs sharing a timestamp, one per tent,
flattened into one stream. Loading that as a single zone silently averages two
rooms together, and worse, interleaving them breaks run continuity, so a
sustained excursion gets chopped into sub-20-minute pieces and undercounted.
The 2026-06-11 humidity dip read as 2.6h merged and 3.6h once split.

The pairs ARE separable, and the evidence is CO2. Within a slot, consecutive
samples step 29.7ppm on average; between the two slots at the same instant they
differ by 235.9ppm. If row order inside an epoch were arbitrary, stepping along
one slot would jump the full 236. It steps 30, and the sign of (slot0 - slot1)
holds for 95% of consecutive samples. So row order within a timestamp is stable
and slot 0 is consistently one sensor.

Which slot is tent-1 and which is tent-2 is NOT recoverable, so they are named
zone-a and zone-b rather than guessed at.

Worth knowing before trusting any per-zone reading: on this export the two
tents differ in CO2 (236ppm apart, persistent) but NOT in temperature or
humidity, where the paired difference averages -0.00C and +0.01% and flips sign
50% of the time, i.e. pure sensor noise. Two tents in one climate-controlled
space, on separate FAE.

  python3 load_export.py sense_24h_preoutage_long.csv out.db
"""
from __future__ import annotations

import csv
import sqlite3
import sys
from collections import defaultdict

# Computed once per timestamp by the Pi rather than read per tent, so these
# have no zone to recover and are stored under 'derived'.
DERIVED = {"fruiting_score", "dew_point_c"}


def load(src: str, dest: str) -> None:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    order: list[tuple[str, str]] = []
    with open(src) as f:
        for r in csv.DictReader(f):
            key = (r["metric"], r["epoch"])
            if key not in grouped:
                order.append(key)
            grouped[key].append(float(r["value"]))

    con = sqlite3.connect(dest)
    con.execute("DROP TABLE IF EXISTS readings")
    con.execute("CREATE TABLE readings "
                "(epoch REAL, metric TEXT, value REAL, sensor TEXT)")
    written = skipped = 0
    for metric, epoch in order:
        vals = grouped[(metric, epoch)]
        if metric in DERIVED:
            con.execute("INSERT INTO readings VALUES (?,?,?,?)",
                        (float(epoch), metric, vals[0], "derived"))
            written += 1
            continue
        if len(vals) == 1:
            # One tent reported and the other did not. Nothing in the row says
            # which, and guessing would put a reading in the wrong room.
            skipped += 1
            continue
        for slot, v in enumerate(vals[:2]):
            con.execute("INSERT INTO readings VALUES (?,?,?,?)",
                        (float(epoch), metric, v, "zone-a" if slot == 0 else "zone-b"))
            written += 1
    con.execute("CREATE INDEX ix ON readings(sensor, metric, epoch)")
    con.commit()

    print(f"wrote {written} rows, skipped {skipped} unattributable single readings")
    for row in con.execute(
            "SELECT sensor, metric, COUNT(*), ROUND(MIN(value),1), "
            "ROUND(AVG(value),1), ROUND(MAX(value),1) FROM readings "
            "GROUP BY sensor, metric ORDER BY sensor, metric"):
        print("  %-8s %-15s n=%-5d min=%-7s mean=%-7s max=%s" % row)
    con.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    load(sys.argv[1], sys.argv[2])
