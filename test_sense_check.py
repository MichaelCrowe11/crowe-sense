#!/usr/bin/env python3
"""Regression tests for sense_check.py.

Every case here is a mistake this file actually made. It reported a 20.0 to
98.9C incubation band, judged incubation against pin-set humidity, flagged
tent air against sealed-bag CO2, called a hundredth of a degree a breach,
treated a repeated "80 percent" target as a ceiling, and called a window with
24 percent of readings below the floor "inside your own band". Each one is
now a test.

  python3 test_sense_check.py
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

import sense_check as sc

FAILURES: list[str] = []


def check(name: str, got, want) -> None:
    if got == want:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}: got {got!r}, want {want!r}")
        FAILURES.append(name)


def band(metric, stage, low, high, sources, species=None, kind="band", bound="range"):
    return {"metric": metric, "stage": stage, "species": species or [],
            "low": low, "high": high, "sources": sources, "kind": kind,
            "bound": bound, "context": "test"}


def series(values, step=60.0, t0=1_000_000.0):
    return [(t0 + i * step, v) for i, v in enumerate(values)]


# ---------------------------------------------------------------- consensus

print("consensus")

# One outlier must not swallow the band. The widest span gave 20.0 to 98.9.
c = sc.consensus([
    band("temperature_c", "incubation", 21.11, 22.78, ["a"]),
    band("temperature_c", "incubation", 21.11, 22.22, ["b"]),
    band("temperature_c", "incubation", 20.00, 98.90, ["c"]),
])
check("median resists an outlier high", (c["low"], c["high"]), (21.11, 22.78))

# A point statement is evidence for the level aimed at, not for a ceiling.
c = sc.consensus([
    band("humidity_pct", "fruiting", 82.0, 86.0, ["a"]),
    band("humidity_pct", "fruiting", 80.0, 80.0, ["b"]),
    band("humidity_pct", "fruiting", 80.0, 80.0, ["c"]),
    band("humidity_pct", "fruiting", 80.0, 80.0, ["d"]),
])
check("point statements do not drag the ceiling down", c["high"], 86.0)
check("point statements do support the floor", c["low"], 80.0)
check("ceiling evidence counted separately", c["n_high"], 1)
check("floor evidence counted separately", c["n_low"], 4)

# A ceiling-only claim must not invent a floor. This is how tent CO2 got
# judged against the inside of a sealed bag.
c = sc.consensus([band("co2_ppm", "incubation", 20000.0, 20000.0,
                       ["a"], bound="upper")])
check("upper-bound claim leaves the floor open", (c["low"], c["high"]),
      (None, 20000.0))

# Disagreeing sides must not produce an inverted band that flags everything.
c = sc.consensus([
    band("humidity_pct", "fruiting", 95.0, 95.0, ["a"]),
    band("humidity_pct", "fruiting", 95.0, 95.0, ["b"]),
    band("humidity_pct", "fruiting", 70.0, 80.0, ["c"]),
])
check("inverted band is resolved, not emitted",
      c["low"] is None or c["high"] is None or c["low"] <= c["high"], True)

# --------------------------------------------------------------- bands_for

print("stage matching")

env = {"bands": [
    band("humidity_pct", "pin_set", 90.0, 95.0, ["a"]),
    band("humidity_pct", "unspecified", 92.0, 92.0, ["b"]),
    band("temperature_c", "incubation", 21.11, 22.78, ["c"]),
]}
check("incubation does not borrow pin-set or unspecified humidity",
      sc.bands_for(env, "humidity_pct", "incubation", None), [])
check("a stage with its own band still matches",
      len(sc.bands_for(env, "temperature_c", "incubation", None)), 1)

env_sp = {"bands": [band("co2_ppm", "fruiting", 500.0, 500.0, ["a"],
                         species=["shiitake, reishi"])]}
check("species band is not applied when no species is given",
      sc.bands_for(env_sp, "co2_ppm", "fruiting", None), [])
check("species band applies to its own species",
      len(sc.bands_for(env_sp, "co2_ppm", "fruiting", "shiitake")), 1)

# ---------------------------------------------------------------- breaches

print("breach detection")

# 70F is 21.11C. A reading of 21.10 is unit-conversion precision.
check("a hundredth of a degree is not a breach",
      sc.breaches(series([21.10] * 200), 21.11, 22.78), [])

# A real sustained excursion must survive.
runs = sc.breaches(series([22.0] * 100 + [25.1] * 100 + [22.0] * 100), 21.11, 22.78)
check("a sustained excursion is caught", len(runs), 1)
check("worst value is reported", runs[0]["worst"] if runs else None, 25.1)
check("direction is reported", runs[0]["dir"] if runs else None, "above")

# A brief door-opening dip is not a period.
check("a 5-minute dip is not a period",
      sc.breaches(series([85.0] * 100 + [70.0] * 5 + [85.0] * 100), 80.0, None), [])

# ------------------------------------------------------------ total_outside

print("flapping")

# Alternating across the line: no run reaches 20 minutes, but the room spent a
# quarter of the window below the floor. Reporting only sustained periods
# called this "inside your own band".
flap = series([79.0, 81.0] * 400, step=60.0)
h, pct = sc.total_outside(flap, 80.0, None)
check("short dips are still counted in the total", round(pct), 50)
check("flapping accumulates real hours", h > 6.0, True)

# A sensor gap is not the room being out of band.
gappy = [(0.0, 70.0), (86400.0, 70.0)]
h, _ = sc.total_outside(gappy, 80.0, None)
check("a 24h sensor gap is not counted as 24h outside", h, 0.0)

# ------------------------------------------------------- end to end on sqlite

print("end to end")

tmp = Path(tempfile.mkdtemp())
db = tmp / "sense.db"
con = sqlite3.connect(db)
con.execute("CREATE TABLE readings (epoch REAL, metric TEXT, value REAL, sensor TEXT)")
t0 = 1_700_000_000.0
rows = []
for i in range(1440):                      # a day at one sample a minute
    v = 25.1 if 600 <= i < 900 else 22.0   # a planted 5h excursion
    rows.append((t0 + i * 60, "temperature_c", v, "tent-1"))
    rows.append((t0 + i * 60, "humidity_pct", 85.0, "tent-1"))
con.executemany("INSERT INTO readings VALUES (?,?,?,?)", rows)
con.commit()
con.close()

s = sc.read_series(str(db), "temperature_c", "tent-1", t0 - 1, t0 + 90000)
check("readings load from sqlite", len(s), 1440)
runs = sc.breaches(s, 21.11, 22.78)
check("the planted excursion is found", len(runs), 1)
check("its duration is right", round((runs[0]["end"] - runs[0]["start"]) / 3600.0, 1)
      if runs else None, 5.0)

s2 = sc.read_series(str(db), "temperature_c", "no-such-zone", t0 - 1, t0 + 90000)
check("zone filter excludes other zones", s2, [])

# ---------------------------------------------------------------- stage log

print("stage log")

import stagelog  # noqa: E402

T = stagelog.parse_ts
check("date-only timestamps parse", T("2026-06-11") > 0, True)
check("full timestamps parse",
      T("2026-06-11T12:00:00Z") - T("2026-06-11") , 43200.0)

log = [
    {"zone": "tent-1", "stage": "pin_set", "species": "shiitake",
     "batch_id": "B12", "start": T("2026-06-11T00:00:00Z")},
    {"zone": "tent-1", "stage": "fruiting", "species": None,
     "batch_id": "B12", "start": T("2026-06-12T00:00:00Z")},
    {"zone": "tent-2", "stage": "idle", "species": None,
     "batch_id": None, "start": T("2026-06-11T00:00:00Z")},
]

# A window spanning a transition must be judged against BOTH bands. This is the
# whole point: the same readings are 3.6h out against fruiting and 15.8h out
# against pin set.
segs = stagelog.segments(log, "tent-1", T("2026-06-11T00:00:00Z"),
                         T("2026-06-13T00:00:00Z"))
check("a transition splits the window", [s["stage"] for s in segs],
      ["pin_set", "fruiting"])
check("the split lands on the transition",
      segs[0]["end"], T("2026-06-12T00:00:00Z"))
check("species rides along with the span", segs[0]["species"], "shiitake")

# Time before the log begins is unknown, NOT the earliest known stage.
segs = stagelog.segments(log, "tent-1", T("2026-06-10T00:00:00Z"),
                         T("2026-06-11T12:00:00Z"))
check("time before the first entry is unknown",
      [s["stage"] for s in segs], [None, "pin_set"])

# A zone with no entries at all is entirely unknown, never defaulted.
segs = stagelog.segments(log, "tent-9", T("2026-06-11T00:00:00Z"),
                         T("2026-06-12T00:00:00Z"))
check("an unlogged zone is one unknown span",
      [s["stage"] for s in segs], [None])

# idle must survive to the caller so an empty tent is skipped, not judged.
segs = stagelog.segments(log, "tent-2", T("2026-06-11T00:00:00Z"),
                         T("2026-06-12T00:00:00Z"))
check("idle is preserved", [s["stage"] for s in segs], ["idle"])

# Backdated entries are the normal case, so order in the file must not matter.
shuffled = [log[1], log[2], log[0]]
segs = stagelog.segments(sorted(shuffled, key=lambda e: e["start"]), "tent-1",
                         T("2026-06-11T00:00:00Z"), T("2026-06-13T00:00:00Z"))
check("out-of-order entries still segment correctly",
      [s["stage"] for s in segs], ["pin_set", "fruiting"])

check("current stage is the latest entry",
      stagelog.current(log, "tent-1")["stage"], "fruiting")

# A span outside the window entirely must not be emitted.
segs = stagelog.segments(log, "tent-1", T("2026-06-12T06:00:00Z"),
                         T("2026-06-12T12:00:00Z"))
check("only overlapping spans are returned",
      [s["stage"] for s in segs], ["fruiting"])

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {', '.join(FAILURES)}")
    sys.exit(1)
print("all passed")
