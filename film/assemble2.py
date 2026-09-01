"""Footage cut: every scene's picture is real footage (mined face-free windows, the device turntable,
the live dashboard, the test console), with typographic INSERTS only (title, lower-thirds, the close).
Voice + Talon score as before; grade + grain + sidechain duck on the master.

shotlist.json maps scene id -> ordered list of clip paths (curated). Per-target scenes (open/close)
use the same footage with a different lower-third. Spine picture is rendered once and reused.
"""
import hashlib, json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out2"); VOICE = os.path.join(HERE, os.environ.get("VOICE_DIR", "out/voice")); A = os.path.join(HERE, "assets")
sys.path.insert(0, HERE)
import cards
os.makedirs(OUT, exist_ok=True)
SCORE = os.path.join(A, "score", "crowe-sense.wav")
PAD, XF, FPS = 0.8, 0.5, 30
def sha(t): return hashlib.sha1(t.encode()).hexdigest()[:16]
def run(cmd): subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
def dur(p): return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True).stdout.strip() or 0)

# ---- inserts: transparent PNG overlays rendered once -------------------------------------
def lower_third(text, sub, path):
    im = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    w = max(d.textlength(text, font=cards.fraunces(44)), d.textlength(sub, font=cards.inter(22))) + 64
    d.rectangle((90, 880, 90 + w, 1000), fill=(26, 20, 16, 200)); d.rectangle((90, 880, 96, 1000), fill=(201, 162, 39, 255))
    d.text((122, 894), text, font=cards.fraunces(44), fill=(245, 242, 235, 255)); d.text((124, 954), sub.upper(), font=cards.inter(20, True), fill=(201, 162, 39, 255))
    im.save(path); return path
def number_insert(big, label, path):
    im = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle((1180, 120, 1830, 330), fill=(26, 20, 16, 205)); d.rectangle((1180, 120, 1186, 330), fill=(201, 162, 39, 255))
    d.text((1214, 140), big, font=cards.mono(84), fill=(245, 242, 235, 255)); d.text((1216, 262), label.upper(), font=cards.inter(20, True), fill=(201, 162, 39, 255))
    im.save(path); return path

# ---- picture for one scene: footage clips concatenated to `length` seconds with crossfades ----
def picture(clips, length, out):
    """Cut the clips in order (loop the list if short), crossfade XF, trim to length. Each clip <= 8 s."""
    if os.path.exists(out): return out
    seq, t = [], 0.0; i = 0
    while t < length + 1:
        c = clips[i % len(clips)]; i += 1; d = min(dur(c), 8.0); seq.append((c, d)); t += d - XF
    cmd = ["ffmpeg", "-y"]; fl = []
    for k, (c, d) in enumerate(seq): cmd += ["-i", c]; fl.append(f"[{k}:v]trim=0:{d:.2f},setpts=PTS-STARTPTS,scale=1920:1080,fps={FPS},format=yuv420p[v{k}]")
    prev, off = "v0", 0.0
    for k in range(1, len(seq)):
        off += seq[k - 1][1] - XF; fl.append(f"[{prev}][v{k}]xfade=transition=fade:duration={XF}:offset={off:.2f}[x{k}]"); prev = f"x{k}"
    fl.append(f"[{prev}]trim=0:{length:.2f},setpts=PTS-STARTPTS[out]")
    run(cmd + ["-filter_complex", ";".join(fl), "-map", "[out]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", out]); return out

def overlay(video, png, out, fade_in=0.4, hold_from=0.0, hold_to=None):
    """Composite a transparent PNG over the video with fades; hold_to=None means to the end."""
    end = hold_to if hold_to is not None else dur(video)
    run(["ffmpeg", "-y", "-i", video, "-loop", "1", "-i", png, "-filter_complex",
         f"[1:v]format=rgba,fade=t=in:st={hold_from:.2f}:d={fade_in}:alpha=1,fade=t=out:st={end-0.5:.2f}:d=0.5:alpha=1[o];[0:v][o]overlay=0:0:shortest=1[v]",
         "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", "-t", f"{dur(video):.2f}", out]); return out

def card_clip(scene, target, length, out):
    """Title and close stay typographic, but breathe: slow zoom on the card (per the doc-film playbook)."""
    if os.path.exists(out): return out
    png = out.replace(".mp4", ".png"); cards.render(scene, target, png)
    frames = int(length * FPS)
    run(["ffmpeg", "-y", "-loop", "1", "-i", png, "-vf", f"scale=2304:1296,zoompan=z='1.0+0.06*on/{frames}':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps={FPS},format=yuv420p", "-t", f"{length:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", out]); return out

def build(film, manifest, shots):
    slug, target, scenes = film["slug"], film["target"], film["scenes"]
    d = os.path.join(OUT, "films", slug); os.makedirs(d, exist_ok=True); shared = os.path.join(OUT, "spine"); os.makedirs(shared, exist_ok=True)
    parts, durs, vo = [], [], []
    for i, sc in enumerate(scenes):
        h = sha(sc["voice"]); vdur = manifest[h]["dur"]; L = round(vdur + PAD + (XF if i else 0), 2)
        sid = sc["id"]; is_shared = sid not in ("title", "open", "close")
        base = os.path.join(shared if is_shared else d, f"{sid if is_shared else slug + '-' + sid}")
        if sid in ("title", "close"):
            clip = card_clip(sc, target, L, base + ".mp4")
        else:
            pic = picture(shots[sid], L, base + "-pic.mp4")
            clip = base + ".mp4"
            if not os.path.exists(clip):
                if sid == "open": overlay(pic, lower_third("For " + target, sc["headline"], base + "-lt.png"), clip, hold_from=0.6, hold_to=min(L, 6.5))
                elif sid == "ask": overlay(pic, number_insert("$175,000" if "SAFE" in sc["headline"] else "$175,000", "the ask, on a SAFE" if "SAFE" in sc["headline"] else "the pilot budget", base + "-n.png"), clip, hold_from=0.8, hold_to=L - 0.6)
                elif sid == "proven": overlay(pic, number_insert("105", "tests, all green", base + "-n.png"), clip, hold_from=1.0, hold_to=min(L, 7.0))
                elif sid == "envelope": overlay(pic, number_insert("43", "condition bands, each cited", base + "-n.png"), clip, hold_from=1.0, hold_to=min(L, 7.0))
                elif sid == "notproven": overlay(pic, lower_third("No node has run in a room yet", "the pilot: 25 nodes, 10 growers", base + "-lt.png"), clip, hold_from=0.6, hold_to=min(L, 8.0))
                elif sid == "founder": overlay(pic, lower_third("Michael Crowe", "Founder, Crowe Logic. Growing since 2005", base + "-lt.png"), clip, hold_from=0.6, hold_to=min(L, 7.5))
                elif sid == "what": overlay(pic, lower_third("Crowe Sense", "a sensing node for a growing room, about $280 in parts", base + "-lt.png"), clip, hold_from=1.0, hold_to=min(L, 7.5))
                else: os.symlink(os.path.abspath(pic), clip) if not os.path.exists(clip) else None
        parts.append(clip); durs.append(L); vo.append((manifest[h]["wav"], vdur))
    # concat with xfade
    cmd = ["ffmpeg", "-y"]; fl = []; prev, off = "0:v", 0.0
    for c in parts: cmd += ["-i", c]
    for k in range(1, len(parts)):
        off += durs[k - 1] - XF; fl.append(f"[{prev}][{k}:v]xfade=transition=fade:duration={XF}:offset={off:.2f}[x{k}]"); prev = f"x{k}"
    silent = os.path.join(d, "silent.mp4")
    # grade + grain on the way through (the doc-film master look): gentle curves, warmth, vignette, fine grain
    grade = "curves=preset=medium_contrast,eq=saturation=1.08:gamma=1.06:brightness=0.02,colorbalance=rs=.02:bs=-.02,vignette=PI/8"
    fl.append(f"[{prev}]{grade}[g]")
    run(cmd + ["-filter_complex", ";".join(fl), "-map", "[g]", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", silent])
    total = sum(durs) - XF * (len(parts) - 1)
    # narration track
    acmd = ["ffmpeg", "-y"]; starts, t = [], 0.0
    for i, (w, vd) in enumerate(vo): acmd += ["-i", w]; starts.append(t + 0.35); t += durs[i] - (XF if i < len(durs) - 1 else 0)
    af = "".join(f"[{i}:a]aresample=48000,adelay={int(s*1000)}|{int(s*1000)}[a{i}];" for i, s in enumerate(starts)) + "".join(f"[a{i}]" for i in range(len(starts))) + f"amix=inputs={len(starts)}:normalize=0,alimiter=limit=0.95[vo]"
    narration = os.path.join(d, "narration.wav"); run(acmd + ["-filter_complex", af, "-map", "[vo]", "-t", f"{total:.2f}", "-c:a", "pcm_s16le", narration])
    # master: score ducked under the voice by sidechain, then loudnorm
    master = os.path.join(d, f"{slug}.mp4")
    run(["ffmpeg", "-y", "-i", silent, "-i", narration, "-i", SCORE, "-filter_complex",
         f"[2:a]atrim=0:{total:.2f},asetpts=PTS-STARTPTS,volume=-14dB,afade=t=in:d=2,afade=t=out:st={max(0,total-4):.2f}:d=4[bed];"
         f"[1:a]asplit=2[v1][v2];[bed][v2]sidechaincompress=threshold=0.05:ratio=6:attack=40:release=600:makeup=1[ducked];"
         f"[v1][ducked]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=9[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", master])
    web = os.path.join(d, f"{slug}-720p.mp4")
    run(["ffmpeg", "-y", "-i", master, "-vf", "scale=1280:720", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", web])
    return dict(slug=slug, target=target, master=master, web=web, seconds=round(total, 1))

if __name__ == "__main__":
    from targets import all_scripts
    man = json.load(open(os.path.join(VOICE, "manifest.json"))); shots = json.load(open(os.path.join(HERE, "shotlist.json")))
    films = all_scripts(); only = sys.argv[1:]
    if only: films = [f for f in films if any(f["slug"].startswith(o) for o in only)]
    for f in films: print(json.dumps(build(f, man, shots)), flush=True)
