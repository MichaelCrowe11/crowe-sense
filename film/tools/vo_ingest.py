#!/usr/bin/env python3
"""Turn Michael's own recording into the voice track the films use.

  vo_ingest.py RECORDING [RECORDING...]   (m4a, wav, mp3; one long take or several files)

Splits on silence (>= 1.1 s below -35 dB), treats short chunks (< 2.2 s) as the spoken line
numbers and drops them, transcribes each remaining chunk with faster-whisper when available to
confirm which numbered line it is (last take of a number wins; falls back to sequential order),
normalizes each line to -19 LUFS, and writes out/voice-human/manifest.json with the SAME keys the
XTTS manifest uses, so `VOICE_DIR=out/voice-human` makes assemble2/run2 use his voice.
Lines not recorded fall back to the generic opening/close (tier one 15-18), never to XTTS.
"""
import hashlib, json, os, re, subprocess, sys, glob, difflib
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
from spine import SPINE, TITLE, ASK_INVESTOR, ASK_PROGRAM, YOUTUBE, HARRISON
from targets import all_scripts
OUT = os.path.join(HERE, "out", "voice-human"); os.makedirs(OUT, exist_ok=True)
smap = json.load(open(os.path.join(HERE, "out", "vo-script-map.json"))); ORDER, HUMAN = smap["tier1"], smap["human"]
def sha(t): return hashlib.sha1(t.encode()).hexdigest()[:16]
def run(c): return subprocess.run(c, capture_output=True, text=True)
def dur(p): return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).stdout.strip() or 0)

# 1. concatenate inputs to one 48k mono wav
src = os.path.join(OUT, "_take.wav")
if len(sys.argv[1:]) == 1: run(["ffmpeg", "-y", "-v", "error", "-i", sys.argv[1], "-ac", "1", "-ar", "48000", src])
else:
    lst = os.path.join(OUT, "_list.txt"); open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in sys.argv[1:]))
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-ac", "1", "-ar", "48000", src])
total = dur(src)
# 2. silence split
log = run(["ffmpeg", "-nostats", "-i", src, "-af", "silencedetect=noise=-35dB:d=1.1", "-f", "null", "-"]).stderr
starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]; ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
bounds = [0.0] + sorted(starts + ends) + [total]
chunks = []
for i in range(0, len(bounds) - 1):
    a, b = bounds[i], bounds[i + 1]
    if a in ends or a == 0.0:   # speech runs from a silence_end (or 0) to the next silence_start
        if b - a >= 0.6: chunks.append((a, b))
print(f"{total:.0f}s take, {len(chunks)} speech chunks", flush=True)
# 3. transcribe (optional) to read the spoken numbers
try:
    from faster_whisper import WhisperModel
    model = WhisperModel("base.en", device="cpu", compute_type="int8")
    def stt(a, b):
        p = os.path.join(OUT, "_chunk.wav"); run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.2f}", "-t", f"{b-a:.2f}", "-i", src, p])
        segs, _ = model.transcribe(p, beam_size=1); return " ".join(s.text for s in segs).strip()
except Exception as e:
    print("faster-whisper unavailable, sequential mapping:", str(e)[:80]); stt = None
WORDS = {"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10,"eleven":11,"twelve":12,"thirteen":13,"fourteen":14,"fifteen":15,"sixteen":16,"seventeen":17,"eighteen":18}
def spoken_number(t):
    t = t.lower().strip(" .,")
    m = re.match(r"^(one hundred (and )?)?([a-z\- ]+)$", t) or None
    if re.fullmatch(r"\d{1,3}", t): return int(t)
    if t in WORDS: return WORDS[t]
    m2 = re.match(r"(?:one hundred|a hundred)(?: and)? ?(\w+)?(?: ?(\w+))?$", t)
    if m2:
        n = 100; tens = {"ten":10,"twenty":20,"thirty":30,"forty":40,"fifty":50,"sixty":60}
        for w in [m2.group(1), m2.group(2)]:
            if w in tens: n += tens[w]
            elif w in WORDS: n += WORDS[w]
        return n
    return None
takes = {}; seq = []; current = None
for (a, b) in chunks:
    text = stt(a, b) if stt else ""
    if b - a < 2.2 and (spoken_number(text) is not None or not stt):
        n = spoken_number(text) if stt else None
        current = n; continue
    if stt and current is None:  # no number heard: sequential
        current = (max(takes) + 1) if takes else 1
    n = current if current is not None else (max(takes) + 1 if takes else 1)
    takes[n] = (a, b, text); current = None
print(f"{len(takes)} lines mapped: {sorted(takes)}", flush=True)
# 4. export normalized lines
def export(n, a, b):
    p = os.path.join(OUT, f"line{n:03d}.wav")
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0,a-0.15):.2f}", "-t", f"{b-a+0.3:.2f}", "-i", src, "-af", "highpass=f=70,afftdn=nf=-28,loudnorm=I=-19:TP=-1.5:LRA=7", "-ar", "24000", p]); return p
files = {n: export(n, a, b) for n, (a, b, _) in takes.items()}
# 5. manifest with the XTTS keys: line number -> which scene texts it stands in for
line_of = {"title": 1, "what": 2, "path": 3, "dash": 4, "envelope": 5, "proven": 6, "notproven": 7, "founder": 8}
man = {}; missing = set()
def put(text, n):
    if n in files: man[sha(text)] = {"text": text, "wav": files[n], "dur": dur(files[n]), "line": n}
    else: missing.add(n)
for sc in [TITLE] + SPINE: put(sc["voice"], line_of[sc["id"]])
put(ASK_INVESTOR["voice"], 9); put(ASK_PROGRAM["voice"], 10)
for f in all_scripts():
    op = next(s for s in f["scenes"] if s["id"] == "open"); cl = next(s for s in f["scenes"] if s["id"] == "close")
    if f["slug"] == "00-youtube": put(op["voice"], 11); put(cl["voice"], 12)
    elif f["slug"] == "31-harrison": put(op["voice"], 13); put(cl["voice"], 14)
    else:
        i = int(f["slug"][:2]); prog = any(s["id"] == "ask" and "budget" in s["headline"].lower() for s in f["scenes"])
        tn_o, tn_c = 100 + 2 * i - 1, 100 + 2 * i
        put(op["voice"], tn_o if tn_o in files else (17 if prog else 15)); put(cl["voice"], tn_c if tn_c in files else (18 if prog else 16))
json.dump(man, open(os.path.join(OUT, "manifest.json"), "w"), indent=1)
print(f"manifest: {len(man)} scene texts covered by {len(files)} recorded lines; unrecorded line numbers referenced: {sorted(missing) or 'none'}")
print("then: VOICE_DIR=out/voice-human python3 run2.py 5")
