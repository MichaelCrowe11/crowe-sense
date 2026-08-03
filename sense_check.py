#!/usr/bin/env python3
"""Judge Crowe Sense readings against the grower's own documented practice.

build_labeled.py correlates a 72-hour window against a harvest label. It can
tell you a batch was bad. It cannot tell you WHY, or WHEN it went wrong, and it
cites nothing.

This does the other half. It reads practice-envelope.json, which holds bands
parsed from 21 years of recorded practice with a video chunk id on every one,
and reports where a zone has been outside its own band, for how long, and which
video says so.

It predicts nothing. That restraint is deliberate and worth keeping: the corpus
grounds conditions richly (79 temperature, 19 humidity, 5 CO2 constants) and
grounds contamination DYNAMICS barely at all (8 timing records, 3 recovery, every
growth rate assumed). So this says "you were outside the band you described, here
is the receipt", and never "contamination risk is 34 percent". A number invented
in the one place the corpus is thin would poison the credibility of the parts
that are real.

Usage:
  python3 sense_check.py --stage=incubation
  python3 sense_check.py --stage=fruiting --species=shiitake --hours=72
  python3 sense_check.py --db=/path/to/sense.db --envelope=/path/to/practice-envelope.json
  python3 sense_check.py --since=2026-07-01 --zone=tent-1     # post-mortem replay
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
from pathlib import Path

import stagelog

DEFAULT_DB = os.path.expanduser("~/.crowe-logic/sense.db")
DEFAULT_ENVELOPE = os.path.expanduser("~/crowe-gamedev/practice-envelope.json")
METRICS = ("temperature_c", "humidity_pct", "co2_ppm")


def load_envelope(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        sys.exit(f"no envelope at {p}. Build it with: python3 build_envelope.py")
    return json.loads(p.read_text())


def bands_for(env: dict, metric: str, stage: str, species: str | None) -> list[dict]:
    """Bands that apply here. A band naming a species only applies to that
    species; a band naming none is general and applies to all.

    Stage is matched EXACTLY, and there is no fallback. "unspecified" does not
    mean "applies to every stage", it means extraction could not tell which
    stage the grower was talking about, and promoting that to universal is not
    a small liberty. Falling back to it gave incubation a 91 to 95 percent
    humidity floor built from "starting humidity for fresh blocks" and "maximum
    initial humidity", and reported 17.5 hours of breaches against a stage for
    which the corpus holds no humidity statement at all. "Not documented" is a
    true answer; borrowing another stage's number is not."""
    out = []
    for b in env["bands"]:
        if b["metric"] != metric:
            continue
        if b["stage"] != stage:
            continue
        if b["species"]:
            if not species:
                continue
            if not any(species.lower() in s.lower() or s.lower() in species.lower()
                       for s in b["species"]):
                continue
        out.append(b)
    return out


def _median(xs: list[float]) -> float:
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def consensus(bands: list[dict]) -> dict | None:
    """Reduce several overlapping claims to one floor and one ceiling, and say
    how much of the grower's own record stands behind each side.

    The first version took the widest span, and one outlier destroyed it: an
    incubation temperature band came out as 20.0 to 98.9C, which flags nothing
    and hid a real 24.6C excursion. It is the MEDIAN of the stated lows and
    highs now, so a single odd constant cannot swallow the band while genuine
    spread between the grower's own restatements is still respected.

    Sidedness is honoured. A ceiling-only constant ("maximum incubation
    temperature") sets a high with NO low, because reporting a reading for being
    under a maximum is nonsense, and that is exactly how CO2 at 1200ppm came to
    be flagged against an incubation range of 20000 to 30000.

    A POINT statement ("hold it at 80 percent") is evidence for the level the
    grower is aiming at, not for a ceiling at that number. Feeding its high into
    the ceiling median is how ten documented fruiting-humidity statements, the
    best-evidenced metric in the whole corpus, collapsed to a flat 80.0 to 80.0
    and got discarded as a target while real readings sat at 76.3 percent.

    Each side is counted separately because the sides are not equally
    documented. The fruiting humidity floor of 80 percent is restated in five
    videos; the ceiling above it appears in exactly one. Judging both alike
    lends the weight of the first to the second."""
    plain = [b for b in bands if b["kind"] != "threshold"]
    if not plain:
        return None

    def sided(b):
        bound = b.get("bound", "range")
        if bound == "range" and abs(b["high"] - b["low"]) < 1e-9:
            return "point"
        return bound

    points = [b for b in plain if sided(b) == "point"]
    ranges = [b for b in plain if sided(b) == "range"]
    lowers = [b for b in plain if sided(b) == "lower"]
    uppers = [b for b in plain if sided(b) == "upper"]

    low_from = ranges + lowers + points
    high_from = ranges + uppers
    low = _median([b["low"] for b in low_from]) if low_from else None
    high = _median([b["high"] for b in high_from]) if high_from else None
    n_low = len({s for b in low_from for s in b["sources"]})
    n_high = len({s for b in high_from for s in b["sources"]})

    # Point statements can push the floor above a ceiling drawn from a different
    # video. Neither side is wrong, they just disagree; keep the better-evidenced
    # one rather than inventing an inverted band that flags every reading.
    if low is not None and high is not None and low > high:
        if n_low >= n_high:
            high, n_high = None, 0
        else:
            low, n_low = None, 0

    return {"low": low, "high": high, "n_low": n_low, "n_high": n_high,
            "target": _median([b["low"] for b in points]) if points else None,
            "n_points": len({s for b in points for s in b["sources"]})}


def read_series(db: str, metric: str, zone: str | None,
                start: float, end: float) -> list[tuple[float, float]]:
    if not Path(db).exists():
        sys.exit(f"no sense.db at {db}. Pass --db=, or run this on the Pi.")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    cur = con.cursor()
    cols = {r[1] for r in cur.execute("PRAGMA table_info(readings)")}
    zone_col = "sensor" if "sensor" in cols else None
    q = "SELECT epoch, value FROM readings WHERE metric=? AND epoch BETWEEN ? AND ?"
    args: list = [metric, start, end]
    if zone and zone_col:
        q += f" AND {zone_col}=?"
        args.append(zone)
    q += " ORDER BY epoch"
    rows = [(float(a), float(b)) for a, b in cur.execute(q, args) if b is not None]
    con.close()
    return rows


def tolerance(low: float | None, high: float | None) -> float:
    """Slack, because the bands come from Fahrenheit converted to Celsius and
    70F is 21.11C. Readings sitting at 21.10 were being reported as below band:
    a breach of one hundredth of a degree, which is unit-conversion precision
    rather than anything a grower did."""
    span = (high - low) if (low is not None and high is not None) else None
    return max(0.05, (span or 0.0) * 0.02)


def breaches(series: list[tuple[float, float]], low: float | None, high: float | None,
             min_minutes: float = 20.0) -> list[dict]:
    """Contiguous runs outside the band, each lasting at least min_minutes.
    Short excursions are ignored here: opening a door drops humidity for a
    minute and that is not a period worth naming. What they add up to is not
    discarded though, see total_outside."""
    # Tolerance, because the bands come from Fahrenheit converted to Celsius and
    # 70F is 21.11C. Readings sitting at 21.10 were being reported as below band:
    # a breach of one hundredth of a degree, which is unit-conversion precision
    # rather than anything a grower did.
    tol = tolerance(low, high)
    out, run = [], None
    for epoch, value in series:
        outside = ((low is not None and value < low - tol)
                   or (high is not None and value > high + tol))
        if outside and run is None:
            run = {"start": epoch, "end": epoch, "worst": value,
                   "dir": "below" if (low is not None and value < low - tol) else "above"}
        elif outside and run is not None:
            run["end"] = epoch
            if (run["dir"] == "below" and value < run["worst"]) or \
               (run["dir"] == "above" and value > run["worst"]):
                run["worst"] = value
        elif not outside and run is not None:
            out.append(run)
            run = None
    if run is not None:
        out.append(run)
    return [r for r in out if (r["end"] - r["start"]) / 60.0 >= min_minutes]


def total_outside(series: list[tuple[float, float]], low: float | None,
                  high: float | None, max_gap: float = 300.0) -> tuple[float, float]:
    """Every moment outside the band, including excursions too short to be
    reported as periods. Returns (hours, percent of readings).

    The 20-minute minimum on a period is a noise filter, and it is the right
    filter, but on real readings it also hides flapping: fruiting humidity
    crossed 80 percent repeatedly and 3 of the 5.6 hours it spent below the
    floor sat in dips shorter than 20 minutes each. Reporting only the sustained
    periods called that 2.6h, which understates what the room actually did.
    Gaps longer than max_gap are not counted, since the sensor being offline is
    not the same as the room being out of band."""
    if not series:
        return 0.0, 0.0
    def out(v: float) -> bool:
        return (low is not None and v < low) or (high is not None and v > high)
    secs = 0.0
    for i in range(1, len(series)):
        (t0, v0), (t1, _) = series[i - 1], series[i]
        gap = t1 - t0
        if gap <= max_gap and out(v0):
            secs += gap
    n_out = sum(1 for _, v in series if out(v))
    return secs / 3600.0, 100.0 * n_out / len(series)


def fmt(epoch: float) -> str:
    return dt.datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")


def data_extent(db: str, zone: str | None,
                start: float, end: float) -> tuple[float, float, int] | None:
    """When the readings inside a span actually begin and end.

    An open stage entry runs to now, so a log saying "fruiting since June 11"
    produced a 1252.5h span against 24h of readings. The span is what the log
    claims and is not wrong, but printing it alone invites reading a one-day
    excursion as a fifty-day one."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    cols = {r[1] for r in con.execute("PRAGMA table_info(readings)")}
    q = ("SELECT MIN(epoch), MAX(epoch), COUNT(*) FROM readings "
         "WHERE metric IN (%s) AND epoch BETWEEN ? AND ?" % ",".join("?" * len(METRICS)))
    args: list = [*METRICS, start, end]
    if zone and "sensor" in cols:
        q += " AND sensor=?"
        args.append(zone)
    lo, hi, n = con.execute(q, args).fetchone()
    con.close()
    return (lo, hi, n) if n else None


def judge(env: dict, db: str, stage: str, species: str | None, zone: str | None,
          start: float, end: float) -> bool:
    """Report every metric for one zone over one span of constant stage.
    Returns whether anything was found."""
    any_finding = False
    for metric in METRICS:
        bands = bands_for(env, metric, stage, species)
        if not bands:
            near = [b for b in env["bands"] if b["metric"] == metric
                    and b["stage"] != stage]
            note = ""
            if near:
                stages = sorted({b["stage"] for b in near})
                note = (f" You document it for {', '.join(stages)}, "
                        f"which is a different claim and is not borrowed.")
            print(f"{metric}: nothing documented for {stage}. Not judged.{note}\n")
            continue
        series = read_series(db, metric, zone, start, end)
        if not series:
            print(f"{metric}: no readings in this window.\n")
            continue

        vals = [v for _, v in series]
        print(f"{metric}: {len(series)} readings, "
              f"min {min(vals):.1f} mean {sum(vals)/len(vals):.1f} max {max(vals):.1f}")

        con = consensus(bands)
        if con:
            cites = sorted({s for b in bands if b["kind"] != "threshold"
                            for s in b["sources"]})[:3]
            low, high = con["low"], con["high"]
            shown = (f"{low:.1f} to {high:.1f}" if low is not None and high is not None
                     else f"at most {high:.1f}" if low is None
                     else f"at least {low:.1f}" if high is None else "none")
            print(f"  your documented band: {shown}  "
                  f"[{', '.join(cites) if cites else 'n/a'}]")

            # A side backed by ONE video is a remark, not an envelope. Fruiting
            # temperature rests on a single "19.4 to 20.0" and judging against it
            # called 20.4h of a real 24h window a breach, which is noise wearing
            # the clothes of a finding. Incubation earns its band from five
            # separate restatements, and that one is worth acting on.
            MIN_SOURCES = 2
            if low is not None and con["n_low"] < MIN_SOURCES:
                low = None
            if high is not None and con["n_high"] < MIN_SOURCES:
                high = None

            if low is None and high is None:
                src = max(con["n_low"], con["n_high"])
                print(f"  rests on {src} documented statement"
                      f"{'' if src == 1 else 's'}, not a consensus. Not judged.")
                if con["target"] is not None:
                    t = con["target"]
                    near = sum(1 for v in vals if abs(v - t) <= max(1.0, abs(t) * 0.03))
                    print(f"  you state a target of {t:.1f}; "
                          f"{100.0 * near / len(vals):.0f}% of readings within 3%.")
            else:
                if (low is None) != (con["low"] is None) or \
                   (high is None) != (con["high"] is None):
                    dropped = "ceiling" if high is None else "floor"
                    n = con["n_high"] if high is None else con["n_low"]
                    print(f"  {dropped} rests on {n} statement"
                          f"{'' if n == 1 else 's'} only, so it is not judged.")
                tol = tolerance(low, high)
                all_h, all_pct = total_outside(
                    series,
                    None if low is None else low - tol,
                    None if high is None else high + tol)
                runs = breaches(series, low, high)
                if runs:
                    any_finding = True
                    total_h = sum(r["end"] - r["start"] for r in runs) / 3600.0
                    print(f"  OUTSIDE for {total_h:.1f}h across "
                          f"{len(runs)} sustained period(s):")
                    for r in runs[:6]:
                        hrs = (r["end"] - r["start"]) / 3600.0
                        print(f"    {fmt(r['start'])} to {fmt(r['end'])}  {hrs:.1f}h  "
                              f"{r['dir']} band, worst {r['worst']:.1f}")
                    if all_h > total_h * 1.15:
                        print(f"  counting short dips too: {all_h:.1f}h outside, "
                              f"{all_pct:.0f}% of readings.")
                elif all_pct >= 5.0:
                    # No run lasted 20 minutes, yet the room kept crossing the
                    # line. Saying "inside your own band for the whole window"
                    # here would be flatly untrue.
                    any_finding = True
                    print(f"  no sustained period, but {all_pct:.0f}% of readings "
                          f"are outside, {all_h:.1f}h in dips shorter than 20 min.")
                else:
                    print("  inside your own band for the whole window.")
        else:
            print("  documented only as a threshold, with no band.")

        # Thresholds are a different claim from a band: the grower naming a point
        # beyond which things go wrong is worth quoting directly. This used to sit
        # inside the breach branch, so a threshold crossing was invisible whenever
        # the band itself held, or whenever the metric had no band to breach.
        for b in [x for x in bands if x["kind"] == "threshold"]:
            crossed = [v for v in vals if v > b["high"]]
            if crossed:
                any_finding = True
                pct = 100.0 * len(crossed) / len(vals)
                print(f"  THRESHOLD: {pct:.0f}% of readings above {b['high']:.1f} "
                      f"({b['context']}) [{b['sources'][0] if b['sources'] else 'n/a'}]")
        print()
    return any_finding


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--envelope", default=DEFAULT_ENVELOPE)
    ap.add_argument("--stage", default=None,
                    help="override the stage log; without it the log decides")
    ap.add_argument("--species", default=None)
    ap.add_argument("--zone", default=None)
    ap.add_argument("--hours", type=float, default=72.0)
    ap.add_argument("--since", default=None, help="YYYY-MM-DD, for a post-mortem")
    ap.add_argument("--stages", default=stagelog.DEFAULT_LOG)
    a = ap.parse_args()

    env = load_envelope(a.envelope)
    end = dt.datetime.now().timestamp()
    start = (dt.datetime.strptime(a.since, "%Y-%m-%d").timestamp()
             if a.since else end - a.hours * 3600.0)

    print("CROWE SENSE against documented practice")
    print(f"  window {fmt(start)} to {fmt(end)}"
          + (f", zone {a.zone}" if a.zone else ""))

    # The stage used to be whatever was typed, and the same readings are 3.6h
    # out against the fruiting floor or 15.8h out against the pin-set band. So
    # the log decides unless explicitly overridden, and a span the log does not
    # cover is reported as unknown rather than defaulted.
    if a.stage:
        print(f"  stage {a.stage} (given on the command line, not from the log)"
              + (f", species {a.species}" if a.species else ""))
        print()
        found = judge(env, a.db, a.stage, a.species, a.zone, start, end)
    elif not a.zone:
        sys.exit("pass --zone so the stage log can be read, or --stage to override it.")
    else:
        entries = stagelog.load(a.stages)
        if not entries:
            sys.exit(
                f"no stage log at {a.stages}, and no --stage given.\n"
                "  Which stage a zone was running changes the answer several-fold,\n"
                "  so it is not guessed. Record it with:\n"
                f"    python3 log_stage.py --zone {a.zone} --stage fruiting\n"
                "  or override for one run with --stage=fruiting.")
        spans = stagelog.segments(entries, a.zone, start, end)
        known = [s for s in spans if s["stage"] and s["stage"] != "idle"]
        print(f"  stage from {a.stages}: "
              f"{len(spans)} span(s), {len(known)} judgeable")
        print()
        if not known:
            for s in spans:
                hrs = (s["end"] - s["start"]) / 3600.0
                what = "zone idle" if s["stage"] == "idle" else "stage UNKNOWN"
                print(f"[{fmt(s['start'])} to {fmt(s['end'])}, {hrs:.1f}h] "
                      f"{what}, not judged.")
            # "No findings" would read as an all-clear on a window that was
            # never examined.
            sys.exit("\nNothing was judged. No span in this window has a stage "
                     "to judge it against.")
        found = False
        for s in spans:
            hrs = (s["end"] - s["start"]) / 3600.0
            head = f"[{fmt(s['start'])} to {fmt(s['end'])}, {hrs:.1f}h]"
            if not s["stage"]:
                print(f"{head} stage UNKNOWN, not judged. The log has no entry "
                      f"covering this span.\n")
                continue
            if s["stage"] == "idle":
                print(f"{head} zone idle, not judged.\n")
                continue
            label = s["stage"] + (f", {s['species']}" if s["species"] else "")
            if s["batch_id"]:
                label += f", batch {s['batch_id']}"
            ext = data_extent(a.db, a.zone, s["start"], s["end"])
            if ext and (ext[1] - ext[0]) < (s["end"] - s["start"]) * 0.9:
                head = (f"[{fmt(ext[0])} to {fmt(ext[1])}, "
                        f"{(ext[1] - ext[0]) / 3600.0:.1f}h of readings "
                        f"inside a {hrs:.1f}h span]")
            print(f"{head} {label}")
            found |= judge(env, a.db, s["stage"], a.species or s["species"],
                           a.zone, s["start"], s["end"])

    if not found:
        print("No findings. Conditions matched your documented practice.")
    print("\nConditions only. Contamination outcomes are NOT predicted: the corpus\n"
          "grounds conditions richly and contamination dynamics barely, so this\n"
          "reports what happened against what you documented, and nothing more.")


if __name__ == "__main__":
    main()
