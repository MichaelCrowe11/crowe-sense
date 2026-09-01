import sqlite3, csv, json, datetime, collections

db = "/home/sergikdropz/.crowe-logic/sense.db"
cur = sqlite3.connect("file:%s?mode=ro" % db, uri=True).cursor()

# totals
n, emin, emax = cur.execute("SELECT COUNT(*),MIN(epoch),MAX(epoch) FROM readings").fetchone()
metrics = [r[0] for r in cur.execute("SELECT DISTINCT metric FROM readings ORDER BY metric")]
sensors = [r[0] for r in cur.execute("SELECT DISTINCT sensor FROM readings ORDER BY sensor")]
totals = dict(readings=n, epoch_min=emin, epoch_max=emax,
              span_days=round((emax - emin) / 86400.0, 2),
              iso_start=datetime.datetime.utcfromtimestamp(emin).strftime("%Y-%m-%dT%H:%M:%SZ"),
              iso_end=datetime.datetime.utcfromtimestamp(emax).strftime("%Y-%m-%dT%H:%M:%SZ"),
              n_metrics=len(metrics), metrics=metrics, sensors=sensors)
json.dump(totals, open("/tmp/cs_totals.json", "w"), indent=2)

# per (sensor, metric) summary
with open("/tmp/cs_metric_summary.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["sensor", "metric", "unit", "n", "min", "mean", "max"])
    for sensor, metric, unit, c, mn, av, mx in cur.execute(
            "SELECT sensor,metric,MAX(unit),COUNT(*),MIN(value),AVG(value),MAX(value) "
            "FROM readings GROUP BY sensor,metric ORDER BY sensor,metric"):
        f3 = lambda x: round(x, 3) if x is not None else ""
        w.writerow([sensor, metric, unit, c, f3(mn), f3(av), f3(mx)])

# hourly-mean wide table for the key agronomic metrics
KEY = ["temperature_c", "humidity_pct", "co2_ppm", "vpd_kpa", "fruiting_score",
       "dew_point_c", "co2_trend_ppm_min", "light_lux"]
rows = cur.execute(
    "SELECT CAST(epoch/3600 AS INT) hr, sensor, metric, AVG(value) "
    "FROM readings WHERE metric IN (%s) GROUP BY hr, sensor, metric" % ",".join("?" * len(KEY)),
    KEY).fetchall()
data = collections.defaultdict(dict)
cols = set()
for hr, sensor, metric, v in rows:
    k = "%s.%s" % (sensor, metric)
    data[hr][k] = round(v, 3)
    cols.add(k)
cols = sorted(cols)
with open("/tmp/cs_hourly.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["hour_utc"] + cols)
    for hr in sorted(data):
        iso = datetime.datetime.utcfromtimestamp(hr * 3600).strftime("%Y-%m-%dT%H:00:00Z")
        w.writerow([iso] + [data[hr].get(c, "") for c in cols])

print("hourly rows:", len(data), "| feature cols:", len(cols), "| total readings:", n)
print("wrote: /tmp/cs_totals.json /tmp/cs_metric_summary.csv /tmp/cs_hourly.csv")
