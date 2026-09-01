#!/usr/bin/env python3
"""Record that a zone changed stage. This is what lets sense_check.py stop
guessing which band applies.

  log_stage.py --zone tent-1 --stage fruiting --species shiitake --batch B12
  log_stage.py --zone tent-2 --stage idle
  log_stage.py --zone tent-1 --stage pin_set --ts 2026-06-11T09:00:00Z
  log_stage.py --list

Time defaults to now, UTC. Backdate with --ts to record a change you made
before you got to a keyboard, which is most of them.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import sys

import stagelog


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zone")
    ap.add_argument("--stage", choices=stagelog.STAGES)
    ap.add_argument("--species", default="")
    ap.add_argument("--batch", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--ts", default=None, help="ISO8601 Z, defaults to now")
    ap.add_argument("--log", default=stagelog.DEFAULT_LOG)
    ap.add_argument("--list", action="store_true", help="show each zone's current stage")
    a = ap.parse_args()

    entries = stagelog.load(a.log)

    if a.list:
        if not entries:
            sys.exit(f"no stage log yet at {a.log}")
        for z in stagelog.zones(entries):
            e = stagelog.current(entries, z)
            when = dt.datetime.fromtimestamp(e["start"]).strftime("%Y-%m-%d %H:%M")
            extra = " ".join(x for x in [e["species"] or "", e["batch_id"] or ""] if x)
            print(f"  {z:<10} {e['stage']:<12} since {when}"
                  + (f"  ({extra})" if extra else ""))
        return

    if not a.zone or not a.stage:
        sys.exit("--zone and --stage are required (or use --list)")

    ts = a.ts or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        epoch = stagelog.parse_ts(ts)
    except ValueError as exc:
        sys.exit(str(exc))

    # Out-of-order entries are allowed, since backdating is the normal case, but
    # an exact duplicate start for a zone would make the interval ambiguous.
    prior = stagelog.current(entries, a.zone)
    if any(e["zone"] == a.zone and abs(e["start"] - epoch) < 1.0 for e in entries):
        sys.exit(f"{a.zone} already has an entry at {ts}")

    os.makedirs(os.path.dirname(a.log), exist_ok=True)
    fresh = (not os.path.exists(a.log)) or os.path.getsize(a.log) == 0
    with open(a.log, "a", newline="") as f:
        w = csv.writer(f)
        if fresh:
            w.writerow(stagelog.HEADER)
        w.writerow([a.zone, a.stage, a.species, a.batch, ts, a.note])

    was = f" (was {prior['stage']})" if prior and prior["stage"] != a.stage else ""
    print(f"logged: {a.zone} -> {a.stage}{was} at {ts}")
    if epoch > dt.datetime.now(dt.timezone.utc).timestamp() + 60:
        print("  note: that timestamp is in the future.")
    print(f"  {a.log}")


if __name__ == "__main__":
    main()
