"""Synthesize every distinct voice segment once with the local XTTS in Michael's voice.

  voice.py --worker K N     synthesize items K::N (run three of these in parallel, plain processes)
  voice.py --manifest       write out/voice/manifest.json once every wav exists
"""
import hashlib, json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out", "voice"); os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, HERE)
from targets import all_scripts
XTTS_DIR = os.path.expanduser("~/crowe-voice-deploy")

def sha(t): return hashlib.sha1(t.encode()).hexdigest()[:16]
def dur(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip() or 0)
def segments():
    texts = {}
    for f in all_scripts():
        for sc in f["scenes"]: texts[sha(sc["voice"])] = sc["voice"]
    return dict(sorted(texts.items(), key=lambda kv: -len(kv[1])))

def worker(k, n):
    sys.path.insert(0, XTTS_DIR)
    import xtts_local
    items = list(segments().items())[k::n]
    t0 = time.time(); done = 0
    for h, text in items:
        wav = os.path.join(OUT, h + ".wav")
        if os.path.exists(wav): continue
        t1 = time.time()
        xtts_local.speak(text, wav + ".tmp.wav"); os.replace(wav + ".tmp.wav", wav)
        done += 1
        print(f"[w{k}] {h} {len(text.split())}w -> {dur(wav):.1f}s audio in {time.time()-t1:.0f}s  ({done}/{len(items)}, {time.time()-t0:.0f}s)", flush=True)
    print(f"[w{k}] finished {done} segments in {time.time()-t0:.0f}s", flush=True)

def manifest():
    segs = segments(); missing = [h for h in segs if not os.path.exists(os.path.join(OUT, h + ".wav"))]
    if missing: print(f"{len(missing)} of {len(segs)} segments missing; not writing the manifest"); sys.exit(1)
    man = {h: {"text": t, "wav": os.path.join(OUT, h + ".wav"), "dur": dur(os.path.join(OUT, h + ".wav"))} for h, t in segs.items()}
    json.dump(man, open(os.path.join(OUT, "manifest.json"), "w"), indent=1)
    print(f"manifest: {len(man)} segments, {sum(m['dur'] for m in man.values())/60:.1f} min of speech")

if __name__ == "__main__":
    if sys.argv[1:2] == ["--worker"]: worker(int(sys.argv[2]), int(sys.argv[3]))
    elif sys.argv[1:2] == ["--manifest"]: manifest()
    else: print(len(segments()), "segments")
