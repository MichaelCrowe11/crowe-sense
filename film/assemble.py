"""Assemble one film: cards timed to the voice, crossfades, the Substrate bed under the voice, 1080p master and a 720p web copy."""
import json, os, subprocess, sys, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); VOICE = os.path.join(OUT, "voice")
sys.path.insert(0, HERE)
import cards
MUSIC = os.path.expanduser("~/substrate-film/OneFloorBelowTheDawn_v14.mp3")
PAD, XF = 0.8, 0.6
def sha(t): return hashlib.sha1(t.encode()).hexdigest()[:16]
def run(cmd): subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

def build(film, manifest, quality="1080"):
    slug, target, scenes = film["slug"], film["target"], film["scenes"]
    d = os.path.join(OUT, "films", slug); os.makedirs(os.path.join(d, "clips"), exist_ok=True)
    frames_dir = os.path.join(OUT, "cards"); os.makedirs(frames_dir, exist_ok=True)
    clips, durs, vo_parts = [], [], []
    for i, sc in enumerate(scenes):
        h = sha(sc["voice"]); vo = manifest[h]["wav"]; vdur = manifest[h]["dur"]
        cdur = round(vdur + PAD + (XF if i else 0), 2)
        # shared spine cards are rendered once; per-target cards carry the slug
        shared = sc["id"] not in ("title", "open", "close")
        png = os.path.join(frames_dir, (sc["id"] if shared else f"{slug}-{sc['id']}") + ".png")
        if not os.path.exists(png): cards.render(sc, target, png)
        clip = os.path.join(d, "clips", f"{i:02d}.mp4")
        if not os.path.exists(clip):
            run(["ffmpeg", "-y", "-loop", "1", "-i", png, "-t", str(cdur), "-vf", "scale=1920:1080,format=yuv420p", "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", clip])
        clips.append(clip); durs.append(cdur); vo_parts.append((vo, vdur))
    # video: xfade chain
    cmd = ["ffmpeg", "-y"]
    for c in clips: cmd += ["-i", c]
    filters, prev, off = [], "0:v", 0.0
    for i in range(1, len(clips)):
        off += durs[i - 1] - XF
        filters.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={XF}:offset={off:.2f}[x{i}]"); prev = f"x{i}"
    silent = os.path.join(d, "silent.mp4")
    run(cmd + ["-filter_complex", ";".join(filters), "-map", f"[{prev}]", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", silent])
    total = sum(durs) - XF * (len(clips) - 1)
    # voice: each segment starts at its clip's start + 0.35 s
    acmd = ["ffmpeg", "-y"]; starts, t = [], 0.0
    for i, (vo, vdur) in enumerate(vo_parts):
        acmd += ["-i", vo]; starts.append(t + 0.35); t += durs[i] - (XF if i < len(durs) - 1 else 0)
    af = "".join(f"[{i}:a]aresample=48000,adelay={int(s*1000)}|{int(s*1000)}[a{i}];" for i, s in enumerate(starts))
    af += "".join(f"[a{i}]" for i in range(len(starts))) + f"amix=inputs={len(starts)}:normalize=0,alimiter=limit=0.95[vo]"
    narration = os.path.join(d, "narration.wav")
    run(acmd + ["-filter_complex", af, "-map", "[vo]", "-t", f"{total:.2f}", "-c:a", "pcm_s16le", narration])
    # mix: bed at -21 dB under the voice, 2 s in, 3 s out
    master = os.path.join(d, f"{slug}.mp4")
    run(["ffmpeg", "-y", "-i", silent, "-i", narration, "-ss", "40", "-i", MUSIC, "-filter_complex",
         f"[2:a]atrim=0:{total:.2f},asetpts=PTS-STARTPTS,volume=-21dB,afade=t=in:d=2,afade=t=out:st={max(0,total-3):.2f}:d=3[bed];[1:a][bed]amix=inputs=2:normalize=0[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", master])
    web = os.path.join(d, f"{slug}-720p.mp4")
    run(["ffmpeg", "-y", "-i", master, "-vf", "scale=1280:720", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", web])
    return dict(slug=slug, target=target, master=master, web=web, seconds=round(total, 1), scenes=len(scenes))

if __name__ == "__main__":
    from targets import all_scripts
    man = json.load(open(os.path.join(VOICE, "manifest.json")))
    films = all_scripts()
    only = sys.argv[1:]
    if only: films = [f for f in films if f["slug"] in only or any(f["slug"].startswith(o) for o in only)]
    for f in films: print(json.dumps(build(f, man)), flush=True)
