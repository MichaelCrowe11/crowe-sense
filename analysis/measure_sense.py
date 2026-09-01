import sqlite3, os, csv

DB = "/home/sergikdropz/.crowe-logic/sense.db"
con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
cur = con.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("TABLES:", tables)
for t in tables:
    try:
        n = cur.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
        cols = [d[1] for d in cur.execute("PRAGMA table_info(%s)" % t)]
        print("\n== %s ==  rows=%d  cols=%s" % (t, n, cols))
        tcol = None
        for c in cols:
            if c.lower() in ("ts", "timestamp", "time", "created_at", "datetime", "recorded_at", "t"):
                tcol = c
                break
        if tcol and n:
            mn, mx = cur.execute("SELECT MIN(%s),MAX(%s) FROM %s" % (tcol, tcol, t)).fetchone()
            print("   span[%s]: %s -> %s" % (tcol, mn, mx))
        row = cur.execute("SELECT * FROM %s LIMIT 1" % t).fetchone()
        print("   sample:", row)
        # distinct sensor/device columns if present
        for c in cols:
            if c.lower() in ("sensor", "device", "metric", "channel", "location", "tent", "zone"):
                vals = [r[0] for r in cur.execute("SELECT DISTINCT %s FROM %s LIMIT 20" % (c, t))]
                print("   distinct %s:" % c, vals)
    except Exception as e:
        print("   err", t, e)

print("\n--- CSV datasets ---")
for p in ["/home/sergikdropz/crowe-sense/datasets/grow.csv",
          "/home/sergikdropz/crowe-sense/datasets/outcomes.csv"]:
    if os.path.exists(p):
        with open(p) as f:
            rows = list(csv.reader(f))
        print("\n%s  rows=%d (incl header)" % (p, len(rows)))
        if rows:
            print("  header:", rows[0])
        for r in rows[1:4]:
            print("  row:", r)
