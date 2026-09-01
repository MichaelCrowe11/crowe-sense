#!/usr/bin/env python3
"""Build the supervised training table: for each harvest in outcomes.csv, summarize the
environment over the WINDOW hours BEFORE harvest_ts from sense.db and attach the yield/quality
labels. This is the closed loop: sensor inputs -> harvest outcomes -> ML-ready rows.

  build_labeled.py            # writes datasets/labeled.csv, prints summary
"""
import csv, os, sqlite3, datetime

OUT = os.path.expanduser("~/crowe-sense/datasets/outcomes.csv")
DB = os.path.expanduser("~/.crowe-logic/sense.db")
LABELED = os.path.expanduser("~/crowe-sense/datasets/labeled.csv")
WINDOW_H = 72
ZONES = ["tent-1", "tent-2"]
METRICS = ["temperature_c", "humidity_pct", "co2_ppm", "vpd_kpa", "fruiting_score"]


def features(cur, end_epoch):
    start = end_epoch - WINDOW_H * 3600
    out = {}
    for z in ZONES:
        for m in METRICS:
            r = cur.execute(
                "SELECT AVG(value), MIN(value), MAX(value), COUNT(*) FROM readings "
                "WHERE sensor=? AND metric=? AND epoch BETWEEN ? AND ?",
                (z, m, start, end_epoch)).fetchone()
            out[f"{z}.{m}.mean"] = round(r[0], 3) if r[0] is not None else ""
            out[f"{z}.{m}.n"] = r[3]
    return out


def main():
    if not os.path.exists(OUT):
        print("no outcomes.csv yet"); return
    rows = [r for r in csv.DictReader(open(OUT)) if r.get("harvest_ts")]
    if not rows:
        print("outcomes.csv has 0 harvests. Log real harvests with log_harvest.py to close the loop.")
        return
    cur = sqlite3.connect("file:%s?mode=ro" % DB, uri=True).cursor()
    built = []
    for r in rows:
        try:
            end = datetime.datetime.strptime(r["harvest_ts"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=datetime.timezone.utc).timestamp()
        except Exception:
            continue
        feat = features(cur, end)
        feat = {"batch_id": r["batch_id"], "harvest_ts": r["harvest_ts"], **feat,
                "y_weight_kg": r["y_weight_kg"], "y_quality": r["y_quality"]}
        built.append(feat)
    if built:
        cols = list(built[0].keys())
        with open(LABELED, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(built)
    print(f"built {len(built)} labeled row(s) -> {LABELED}")
    for b in built[:3]:
        nz = b.get("tent-1.temperature_c.n", 0)
        print(f"  batch {b['batch_id']}: y_weight={b['y_weight_kg']}kg q={b['y_quality']} | "
              f"window readings(tent-1.temp)={nz} | tent-1 temp mean={b.get('tent-1.temperature_c.mean')} "
              f"co2 mean={b.get('tent-1.co2_ppm.mean')} vpd mean={b.get('tent-1.vpd_kpa.mean')}")


if __name__ == "__main__":
    main()
