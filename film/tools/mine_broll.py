#!/usr/bin/env python3
"""Mine face-free B-roll windows from a 4K master.

  mine_broll.py MASTER.mp4 OUTDIR [--min 4] [--max 8] [--top 12]

1. scene-detect on a 640px downscale (fast), 2. sample each scene at 1 fps, 3. reject any
scene where Apple Vision sees a face (any size), 4. score sharpness x motion x exposure,
5. export the top windows as 1080p H.264 (from the 2160p master, 4 s to 8 s each),
6. write index.json and a contact sheet for curation.
"""
import json, os, subprocess, sys, tempfile, argparse
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); FACE = os.path.join(HERE, "facecheck")
ap = argparse.ArgumentParser(); ap.add_argument("master"); ap.add_argument("out"); ap.add_argument("--min", type=float, default=4); ap.add_argument("--max", type=float, default=8); ap.add_argument("--top", type=int, default=12)
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True); vid = os.path.splitext(os.path.basename(a.master))[0]
def sh(c): return subprocess.run(c, capture_output=True, text=True)
dur = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.master]).stdout.strip())
# 1. scene cuts on a downscale
r = sh(["ffmpeg", "-nostats", "-i", a.master, "-vf", "scale=640:-2,select='gt(scene,0.28)',showinfo", "-an", "-f", "null", "-"])
cuts = [0.0] + [float(l.split("pts_time:")[1].split()[0]) for l in r.stderr.splitlines() if "pts_time:" in l] + [dur]
scenes = [(s, e) for s, e in zip(cuts, cuts[1:]) if e - s >= a.min]
print(f"{vid}: {dur:.0f}s, {len(cuts)-2} cuts, {len(scenes)} scenes >= {a.min}s", flush=True)
# 2-4. sample, face-check, score
tmp = tempfile.mkdtemp(); keep = []
for i, (s, e) in enumerate(scenes):
    e = min(e, s + 30)  # long static scenes: judge the first 30 s
    pat = os.path.join(tmp, f"s{i:03d}_%03d.jpg")
    sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{s:.2f}", "-t", f"{e-s:.2f}", "-i", a.master, "-vf", "fps=1,scale=960:-2", "-q:v", "3", pat])
    frames = sorted(f for f in os.listdir(tmp) if f.startswith(f"s{i:03d}_"))
    if len(frames) < a.min: continue
    fr = sh([FACE] + [os.path.join(tmp, f) for f in frames]).stdout
    faces = [int(l.split("\t")[1]) for l in fr.splitlines() if "\t" in l and l.split("\t")[1].isdigit()]
    if any(n > 0 for n in faces): continue
    ims = [cv2.imread(os.path.join(tmp, f), cv2.IMREAD_GRAYSCALE) for f in frames]
    sharp = float(np.mean([cv2.Laplacian(im, cv2.CV_64F).var() for im in ims]))
    motion = float(np.mean([np.mean(cv2.absdiff(x, y)) for x, y in zip(ims, ims[1:])])) if len(ims) > 1 else 0.0
    bright = float(np.mean([im.mean() for im in ims]))
    expo = 1.0 - abs(bright - 110) / 110
    score = (sharp ** 0.5) * (0.5 + min(motion, 12) / 12) * max(expo, 0.2)
    keep.append(dict(scene=i, start=round(s, 2), end=round(e, 2), sharp=round(sharp), motion=round(motion, 2), bright=round(bright), score=round(score, 1)))
keep.sort(key=lambda k: -k["score"]); keep = keep[: a.top]
# 5. export windows
idx = []
for k in keep:
    length = min(a.max, k["end"] - k["start"]); start = k["start"] + max(0, (k["end"] - k["start"] - length) / 2)
    out = os.path.join(a.out, f"{vid}_{k['scene']:03d}.mp4")
    sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{length:.2f}", "-i", a.master, "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080", "-r", "30", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", out])
    sh(["ffmpeg", "-y", "-v", "error", "-ss", "0.5", "-i", out, "-frames:v", "1", "-vf", "scale=480:270", out.replace(".mp4", ".jpg")])
    idx.append(dict(clip=out, video=vid, start=round(start, 2), length=round(length, 2), **{x: k[x] for x in ("sharp", "motion", "bright", "score")}))
json.dump(idx, open(os.path.join(a.out, f"{vid}.json"), "w"), indent=1)
# 6. contact sheet
if idx:
    cols = 4; rows = (len(idx) + cols - 1) // cols
    sheet = Image.new("RGB", (480 * cols, 292 * rows), "#111"); d = ImageDraw.Draw(sheet); f = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 13)
    for i, c in enumerate(idx):
        try: sheet.paste(Image.open(c["clip"].replace(".mp4", ".jpg")), ((i % cols) * 480, (i // cols) * 292))
        except Exception: pass
        d.text(((i % cols) * 480 + 4, (i // cols) * 292 + 272), f"{os.path.basename(c['clip'])} {c['start']}s {c['length']}s sc{c['score']} mo{c['motion']}", font=f, fill="#C9A227")
    sheet.save(os.path.join(a.out, f"{vid}_sheet.png"))
print(f"{vid}: {len(idx)} face-free windows exported", flush=True)
