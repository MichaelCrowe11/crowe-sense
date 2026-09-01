#!/usr/bin/env python3
"""Build shotlist.json from the mined windows: each scene gets an ordered list of clips.

Categories by source video (what the video is, from the contact sheet of 2026-09-01):
  macro  = mushroom close-ups: 9BaXvKDDRGY (lion's mane), asQtPL8d_to (maitake), gks_8ixmEW4 (oysters), dzNjDmP3Cgw (lion's mane block), 8nlgN5W9sZ4 (golden/pink oyster)
  room   = racks, tents, blocks: 8KUYup2W2f4, aP5qnadCPUs, e1DyNs9XQVQ, bgqt0q1I7J8, x7MKOW8xbJo, zb8TAU6Y-4s, z2fpfQGNbQA
  bench  = lab work: 7VMzqqBRJWA (liquid culture), TRH72KNFHGU (agar), Z8USXz3A1YE (bags), asQtPL8d_to (hands)
Motion clips made this session: assets/turntable.mp4 (the device), assets/dashboard.mp4 (the live page), assets/tests.mp4 (the console).
"""
import glob, json, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); C = os.path.join(HERE, "footage", "clips"); A = os.path.join(HERE, "assets")
CAT = {"macro": ["9BaXvKDDRGY", "asQtPL8d_to", "gks_8ixmEW4", "dzNjDmP3Cgw", "8nlgN5W9sZ4"],
       "room": ["8KUYup2W2f4", "aP5qnadCPUs", "e1DyNs9XQVQ", "bgqt0q1I7J8", "x7MKOW8xbJo", "zb8TAU6Y-4s", "z2fpfQGNbQA"],
       "bench": ["7VMzqqBRJWA", "TRH72KNFHGU", "Z8USXz3A1YE", "asQtPL8d_to"]}
idx = []
for j in glob.glob(os.path.join(C, "*.json")): idx += json.load(open(j))
idx = [c for c in idx if os.path.exists(c["clip"]) and c["length"] >= 4]
def pick(cat, n, used, min_motion=3.0):
    pool = sorted([c for c in idx if c["video"] in CAT[cat] and c["clip"] not in used and c["motion"] >= min_motion], key=lambda c: -c["score"])
    out = []
    seen_video = {}
    for c in pool:                       # spread across source videos so a scene is not one video
        if seen_video.get(c["video"], 0) >= 2: continue
        out.append(c["clip"]); used.add(c["clip"]); seen_video[c["video"]] = seen_video.get(c["video"], 0) + 1
        if len(out) >= n: break
    return out
used = set()
shots = {}
shots["open"]      = pick("room", 3, used)
shots["what"]      = [os.path.join(A, "turntable.mp4")] + pick("room", 2, used)
shots["path"]      = pick("room", 1, used) + [os.path.join(A, "dashboard.mp4")] + pick("bench", 1, used)
shots["dash"]      = [os.path.join(A, "dashboard.mp4")] + pick("room", 1, used)
shots["envelope"]  = pick("macro", 3, used)
shots["proven"]    = [os.path.join(A, "tests.mp4")] + pick("bench", 1, used)
shots["notproven"] = pick("room", 3, used, min_motion=0)
shots["founder"]   = pick("bench", 3, used)
shots["ask"]       = pick("macro", 2, used) + pick("room", 1, used)
missing = [k for k, v in shots.items() if not [x for x in v if "assets/" not in x]]
json.dump(shots, open(os.path.join(HERE, "shotlist.json"), "w"), indent=1)
print(f"{len(idx)} mined clips available; shotlist written;", "scenes short of footage:", missing or "none")
for k, v in shots.items(): print(f"  {k:10s} {[os.path.basename(x) for x in v]}")
