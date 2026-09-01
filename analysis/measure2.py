import sqlite3
db = "/home/sergikdropz/.crowe-logic/sense.db"
cur = sqlite3.connect("file:%s?mode=ro" % db, uri=True).cursor()

n, emin, emax = cur.execute("SELECT COUNT(*), MIN(epoch), MAX(epoch) FROM readings").fetchone()
span = (emax - emin) / 86400.0
print("readings: %d" % n)
print("span: %.2f days  (%.0f readings/day)" % (span, n / span))
days = cur.execute("SELECT COUNT(DISTINCT CAST(epoch/86400 AS INT)) FROM readings").fetchone()[0]
print("distinct calendar days with data: %d" % days)
nm = cur.execute("SELECT COUNT(DISTINCT metric) FROM readings").fetchone()[0]
print("distinct metrics: %d" % nm)

print("\nlargest sampling gap on tent-1 temperature (continuity check):")
g = cur.execute("""SELECT MAX(d) FROM (
    SELECT epoch - LAG(epoch) OVER (ORDER BY epoch) AS d
    FROM readings WHERE sensor='tent-1' AND metric='temperature_c')""").fetchone()[0]
print("  max gap: %.1f minutes" % ((g or 0) / 60.0))

print("\nper-zone agronomic ranges (min / avg / max):")
for metric in ["temperature_c", "humidity_pct", "co2_ppm", "vpd_kpa", "fruiting_score", "dew_point_c"]:
    for sensor in ["tent-1", "tent-2", "tent-1-derived"]:
        r = cur.execute("""SELECT COUNT(*), ROUND(MIN(value),2), ROUND(AVG(value),2), ROUND(MAX(value),2)
                           FROM readings WHERE metric=? AND sensor=?""", (metric, sensor)).fetchone()
        if r[0]:
            print("  %-14s %-16s n=%-7d %s / %s / %s" % (sensor, metric, r[0], r[1], r[2], r[3]))
