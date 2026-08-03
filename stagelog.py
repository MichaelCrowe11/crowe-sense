#!/usr/bin/env python3
"""What each zone was actually doing, and when.

sense_check.py judges readings against bands that are stage-specific, and the
stage was an argument the operator typed. That is the weakest link in the whole
chain: on the 2026-06-11 export the same humidity readings are 3.6 hours out
against the fruiting floor and 15.8 hours out against the pin-set band, and
nothing in sense.db says which was running. A number that swings 4x on an
unverified assumption is not evidence.

This is the record that settles it. It is a TRANSITION log, not an interval
log, because a transition is what a grower can actually report: "moved tent-1
to fruiting this morning". Each entry runs until the next entry for that zone.

Deliberately, a window with no entry covering it is reported as UNKNOWN rather
than being assigned a default. Defaulting is how the stage became an assumption
in the first place.

Stage `idle` means the zone was empty. An empty tent drifting to 60% humidity
is not a finding, and judging it would fill the report with noise that trains
the reader to ignore it.
"""
from __future__ import annotations

import csv
import datetime as dt
import os
from pathlib import Path

DEFAULT_LOG = os.path.expanduser("~/crowe-sense/datasets/stages.csv")
HEADER = ["zone", "stage", "species", "batch_id", "start_ts", "note"]
STAGES = ["incubation", "pin_set", "fruiting", "storage", "idle"]


def parse_ts(s: str) -> float:
    """ISO8601 with a trailing Z, as written by log_stage.py and log_harvest.py."""
    s = s.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%MZ", "%Y-%m-%d"):
        try:
            return (dt.datetime.strptime(s, fmt)
                    .replace(tzinfo=dt.timezone.utc).timestamp())
        except ValueError:
            continue
    raise ValueError(f"unparseable timestamp: {s!r}")


def load(path: str = DEFAULT_LOG) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    with p.open() as f:
        for r in csv.DictReader(f):
            if not r.get("zone") or not r.get("start_ts"):
                continue
            try:
                start = parse_ts(r["start_ts"])
            except ValueError:
                continue
            out.append({"zone": r["zone"].strip(),
                        "stage": (r.get("stage") or "").strip(),
                        "species": (r.get("species") or "").strip() or None,
                        "batch_id": (r.get("batch_id") or "").strip() or None,
                        "start": start})
    out.sort(key=lambda e: e["start"])
    return out


def segments(entries: list[dict], zone: str,
             start: float, end: float) -> list[dict]:
    """Split [start, end] into spans of constant stage for one zone.

    Spans shorter than the window are normal: a tent moved from pin set to
    fruiting mid-window must be judged against both bands, not whichever one
    happened to be typed on the command line."""
    mine = [e for e in entries if e["zone"] == zone]
    out: list[dict] = []
    for i, e in enumerate(mine):
        s = e["start"]
        nxt = mine[i + 1]["start"] if i + 1 < len(mine) else float("inf")
        lo, hi = max(s, start), min(nxt, end)
        if hi > lo:
            out.append({**e, "start": lo, "end": hi})
    # Time before the first entry, or the whole window if the zone is absent.
    first = mine[0]["start"] if mine else float("inf")
    if start < min(first, end):
        out.insert(0, {"zone": zone, "stage": None, "species": None,
                       "batch_id": None, "start": start,
                       "end": min(first, end)})
    return [s for s in out if s["end"] > s["start"]]


def current(entries: list[dict], zone: str) -> dict | None:
    mine = [e for e in entries if e["zone"] == zone]
    return mine[-1] if mine else None


def zones(entries: list[dict]) -> list[str]:
    return sorted({e["zone"] for e in entries})
