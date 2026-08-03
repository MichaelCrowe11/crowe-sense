#!/usr/bin/env python3
"""Log a REAL mushroom harvest -> outcomes.csv. Closes the Crowe Sense loop by recording the
yield/quality label that pairs with the environmental sensor window for that batch.

  log_harvest.py --batch B12 --strain "Lions Mane" --kind bag --flush 1 --weight 2.3 --quality A
  (harvest time defaults to now UTC; override with --ts 2026-06-15T12:00:00Z)
"""
import csv, os, argparse, datetime

OUT = os.path.expanduser("~/crowe-sense/datasets/outcomes.csv")
HEADER = ["batch_id", "harvest_ts", "strain", "kind", "flush_num", "y_weight_kg", "y_quality"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True)
    ap.add_argument("--strain", required=True)
    ap.add_argument("--kind", default="")
    ap.add_argument("--flush", type=int, default=1)
    ap.add_argument("--weight", type=float, required=True)
    ap.add_argument("--quality", default="", choices=["A", "B", "C", "cull", ""])
    ap.add_argument("--ts", default=None)
    a = ap.parse_args()
    ts = a.ts or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (not os.path.exists(OUT)) or os.path.getsize(OUT) == 0
    with open(OUT, "a", newline="") as f:
        w = csv.writer(f)
        if fresh:
            w.writerow(HEADER)
        w.writerow([a.batch, ts, a.strain, a.kind, a.flush, a.weight, a.quality])
    n = sum(1 for _ in open(OUT)) - 1
    print(f"logged: batch={a.batch} {a.weight}kg quality={a.quality or '-'} flush={a.flush} at {ts}")
    print(f"outcomes.csv now has {n} labeled harvest(s) -> {OUT}")


if __name__ == "__main__":
    main()
