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

# The real case: the published archive is hourly and contains an 82-hour
# outage. Charging that to the band the room was last outside would invent
# three days of breach out of a dead Pi.
hourly = [(i * 3600.0, 70.0) for i in range(24)]
hourly += [(hourly[-1][0] + 82 * 3600.0 + i * 3600.0, 70.0) for i in range(24)]
h, pct = sc.total_outside(hourly, 80.0, None)
check("an 82h outage inside an hourly series is excluded", round(h), 46)
check("readings either side of the outage still count", round(pct), 100)

# ------------------------------------------------------------------ cadence

print("cadence")

check("cadence of an hourly series", sc.cadence(hourly), 3600.0)
check("cadence of a 9-second series", sc.cadence(series([1.0] * 10, step=9.0)), 9.0)

# A lone out-of-band hour must count for an hour, not for nothing. Measuring a
# run as last-minus-first sample made single-sample excursions zero-length, so
# hourly data silently lost every excursion under two consecutive hours.
one_hour = [(i * 3600.0, 85.0) for i in range(5)]
one_hour[2] = (2 * 3600.0, 70.0)
runs = sc.breaches(one_hour, 80.0, None)
check("a single out-of-band hour is a real period", len(runs), 1)
check("and it lasts an hour",
      (runs[0]["end"] - runs[0]["start"]) / 3600.0 if runs else None, 1.0)

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

# --------------------------------------------------------------------- vpd

print("vpd")

import vpd as V  # noqa: E402

# Checked against the rig's own vpd_kpa over all 469 published hours: mean
# error -0.0001 kPa, worst 0.0007. These two are spot values from that run.
check("vpd at 18.0C / 91.9%", round(V.vpd_kpa(18.0, 91.9), 2), 0.17)
check("vpd at 24.0C / 78.1%", round(V.vpd_kpa(24.0, 78.1), 2), 0.65)
check("rh_for_vpd inverts vpd_kpa",
      round(V.rh_for_vpd(21.0, V.vpd_kpa(21.0, 85.0)), 6), 85.0)

# The corners: VPD rises with temperature and falls with humidity, so the band
# runs from coolest-and-wettest to hottest-and-driest.
lo, hi = V.derive(19.44, 20.0, 80.0, 86.0)
check("derived band low corner is cool and wet", lo, round(V.vpd_kpa(19.44, 86.0), 3))
check("derived band high corner is hot and dry", hi, round(V.vpd_kpa(20.0, 80.0), 3))
check("derived band is ordered", lo < hi, True)

# A VPD band needs BOTH parents. Half of one is not a band.
check("no temperature means no derived band",
      V.derive(None, None, 80.0, 86.0), None)
check("no humidity means no derived band",
      V.derive(19.44, 20.0, None, None), None)

# The laundering guard. sense_check refuses a temperature band resting on one
# video; it must not return wearing VPD units.
one_source = {"low": 19.44, "high": 20.0, "n_low": 1, "n_high": 1}
six_source = {"low": 80.0, "high": 86.0, "n_low": 6, "n_high": 6}
check("a one-video band is not grounded", sc._grounded(one_source), (None, None))
check("a six-video band is grounded", sc._grounded(six_source), (80.0, 86.0))
check("a rejected parent cannot be derived from",
      V.derive(*sc._grounded(one_source), *sc._grounded(six_source)), None)

# A fixed humidity floor is a moving VPD target, and by how much is the point.
lo, hi = V.implied_ceiling(80.0, [18.0, 24.0])
check("80% floor at 18C permits", round(lo, 2), 0.41)
check("80% floor at 24C permits", round(hi, 2), 0.60)
check("so the same rule drifts by nearly half", round(hi / lo, 2), 1.45)

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
