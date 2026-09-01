"""Per-target scripts: the spine wrapped in each outreach draft's own opening and close."""
import csv, glob, re, os
from spine import SPINE, ASK_INVESTOR, ASK_PROGRAM, TITLE, YOUTUBE, HARRISON, open_scene, close_scene

HERE = os.path.dirname(os.path.abspath(__file__))
OUTREACH = os.path.join(HERE, "..", "docs", "outreach")

def _speech(s):
    s = re.sub(r"https?://\S+", "", s)
    s = s.replace("$175,000", "one hundred seventy five thousand dollars").replace("$150,000", "one hundred fifty thousand dollars")
    s = s.replace("$100,000", "one hundred thousand dollars").replace("$250,000", "two hundred fifty thousand dollars").replace("$278", "two hundred seventy eight dollars")
    s = s.replace("$449", "four hundred forty nine dollars").replace("$35,000", "thirty five thousand dollars").replace("$50,000", "fifty thousand dollars")
    s = re.sub(r"\bCEA\b", "controlled environment agriculture", s)
    s = re.sub(r"\bJV\b", "joint venture", s).replace("SBIR", "S B I R").replace("NSF", "N S F").replace("USDA", "U S D A").replace("SAFE", "safe note")
    s = s.replace("3D", "three D").replace("Pi 5", "Pi five").replace("Q&A", "Q and A")
    return re.sub(r"\s+", " ", s).strip()

def _first_sentence(s, limit=110):
    m = re.match(r"(.+?[.!?])(\s|$)", s)
    t = (m.group(1) if m else s)
    if len(t) <= limit: return t
    cut = t[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "."

def draft_parts(n):
    f = glob.glob(os.path.join(OUTREACH, f"{n:02d}-*.md"))[0]
    text = open(f).read().split("\n---\n", 1)[1]
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    subject = next(l for l in paras[0].split("\n") if l.startswith("Subject:")).split(":", 1)[1].strip()
    why = paras[1]
    # the close is the paragraph right before the attachment line
    i = next(i for i, p in enumerate(paras) if p.startswith("The investor report is attached"))
    close = paras[i - 1]
    return subject, why, close

def investor_scripts():
    rows = list(csv.DictReader(open(os.path.join(OUTREACH, "..", "investors-30.csv"))))
    out = []
    for i, r in enumerate(rows, 1):
        subject, why, close = draft_parts(i)
        ask = ASK_PROGRAM if r["type"] == "non-dilutive" else ASK_INVESTOR
        line = re.sub(r"^Crowe Sense:\s*", "", subject)
        line = line[0].upper() + line[1:]
        scenes = [TITLE, open_scene(r["name"], _speech(why), line)] + SPINE + [ask, close_scene(_speech(close), _first_sentence(close))]
        out.append(dict(slug=f"{i:02d}-" + re.sub(r"[^a-z0-9]+", "-", r["name"].lower()).strip("-")[:40], target=r["name"], scenes=scenes))
    return out

def special_scripts():
    yt = [TITLE, open_scene("growers", YOUTUBE["open"]["voice"], YOUTUBE["open"]["line"])] + SPINE + [close_scene(YOUTUBE["close"]["voice"], YOUTUBE["close"]["line"], contact=False)]
    hk = [TITLE, open_scene("Harrison Mushrooms", HARRISON["open"]["voice"], HARRISON["open"]["line"])] + SPINE + [HARRISON["ask"], close_scene(HARRISON["close"]["voice"], HARRISON["close"]["line"])]
    return [dict(slug="00-youtube", target="YouTube", scenes=yt), dict(slug="31-harrison", target="Harrison Mushrooms", scenes=hk)]

def all_scripts():
    return special_scripts() + investor_scripts()

if __name__ == "__main__":
    import json
    s = all_scripts()
    texts = {sc["voice"] for f in s for sc in f["scenes"]}
    words = sum(len(t.split()) for t in texts)
    print(len(s), "films;", len(texts), "distinct voice segments;", words, "words to synthesize (about", round(words / 150), "minutes of speech)")
    for f in s[:3]: print(" ", f["slug"], [sc["id"] for sc in f["scenes"]])
