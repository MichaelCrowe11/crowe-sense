"""After run.py: upload every finished film to the PRIVATE crowe-archive bucket, write the
share Worker's TOKENS entries (Michael deploys), and stamp film_url into the outreach sheet.

  deliver.py upload      rclone copy out/films/*/<slug>-720p.mp4 -> swmr2:crowe-archive/crowe-sense-films/
  deliver.py tokens      write out/share-tokens.json (paste into ~/bod-build/share-worker/wrangler.jsonc TOKENS)
  deliver.py stamp       write film_url (https://crowe-share.yellow-block-3adc.workers.dev/v/<token>) into docs/outreach/recipients.csv
"""
import csv, json, os, secrets, subprocess, sys, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out")
BUCKET = "swmr2:crowe-archive/crowe-sense-films"; SHARE = "https://crowe-share.yellow-block-3adc.workers.dev/v/"
man = json.load(open(os.path.join(OUT, "manifest.json")))
films = [m for m in man if "web" in m]

def upload():
    for m in films:
        dst = f"{BUCKET}/{os.path.basename(m['web'])}"
        r = subprocess.run(["rclone", "copyto", m["web"], dst, "--s3-chunk-size", "32M"], capture_output=True, text=True)
        print(("ok  " if r.returncode == 0 else "FAIL") + f" {m['slug']} -> {dst} {r.stderr.strip()[:120]}", flush=True)

def tokens():
    path = os.path.join(OUT, "share-tokens.json")
    tok = json.load(open(path)) if os.path.exists(path) else {}
    expires = (datetime.date.today() + datetime.timedelta(days=60)).isoformat()
    for m in films:
        if not any(v["label"] == m["slug"] for v in tok.values()):
            tok[secrets.token_hex(4)] = {"key": f"crowe-sense-films/{os.path.basename(m['web'])}", "label": m["slug"], "expires": expires}
    json.dump(tok, open(path, "w"), indent=2)
    print(f"{len(tok)} tokens in {path}; paste into the share Worker's TOKENS and deploy:")
    print("  cd ~/bod-build/share-worker && env -u CLOUDFLARE_API_TOKEN npx wrangler deploy")

def stamp():
    tok = json.load(open(os.path.join(OUT, "share-tokens.json")))
    by_slug = {v["label"]: k for k, v in tok.items()}
    p = os.path.join(HERE, "..", "docs", "outreach", "recipients.csv")
    rows = list(csv.DictReader(open(p))); fields = list(rows[0].keys())
    if "film_url" not in fields: fields.append("film_url")
    n = 0
    for r in rows:
        slug = next((m["slug"] for m in films if m["slug"].startswith(f"{int(r['n']):02d}-")), None)
        if slug and slug in by_slug: r["film_url"] = SHARE + by_slug[slug]; n += 1
        else: r.setdefault("film_url", "")
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    print(f"stamped {n} film links into recipients.csv")

if __name__ == "__main__":
    {"upload": upload, "tokens": tokens, "stamp": stamp}[sys.argv[1]]()
