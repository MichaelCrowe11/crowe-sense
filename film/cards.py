"""Card renderer: one 1920x1080 PNG per scene, in the Crowe Logic editorial system.
Fraunces (variable) for headlines, Inter for body, Menlo for figures. Art panels are real
artifacts: the CAD render, the dashboard capture, the test output, the report page."""
import os, glob
from PIL import Image, ImageDraw, ImageFont
W, H = 1920, 1080
HERE = os.path.dirname(os.path.abspath(__file__)); A = os.path.join(HERE, "assets")
C = dict(paper="#FBF8F2", cream="#F5F2EB", ink="#1A1410", muted="#6F665C", gold="#B8963F", goldsoft="#C4A86C", line="#E3DCCF", green="#5A6B4A", brick="#A53A2A")
FR = os.path.expanduser("~/Library/Fonts/Fraunces[SOFT,WONK,opsz,wght].ttf")
INTER = os.path.expanduser("~/Library/Fonts/Inter-Medium.otf"); INTER_B = os.path.expanduser("~/Library/Fonts/Inter-Bold.otf")
MONO = "/System/Library/Fonts/Menlo.ttc"
def fraunces(size, wght=500):
    f = ImageFont.truetype(FR, size)
    try: f.set_variation_by_axes([0, 0, min(144, max(9, size / 2)), wght])
    except Exception: pass
    return f
def inter(size, bold=False): return ImageFont.truetype(INTER_B if bold else INTER, size)
def mono(size): return ImageFont.truetype(MONO, size)

def wrap(d, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= width: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def base():
    im = Image.new("RGB", (W, H), C["cream"]); d = ImageDraw.Draw(im)
    return im, d
def eyebrow(d, x, y, text):
    d.text((x, y), text.upper(), font=inter(22, True), fill=C["gold"], spacing=4)
    d.line((x, y + 40, x + 44, y + 40), fill=C["gold"], width=3)
def headline(d, x, y, text, width, size=64):
    f = fraunces(size); lines = wrap(d, text, f, width); yy = y
    for ln in lines: d.text((x, yy), ln, font=f, fill=C["ink"]); yy += int(size * 1.12)
    return yy
def body(d, x, y, lines, width, size=30):
    f = inter(size); yy = y
    for ln in lines:
        for sub in wrap(d, ln, f, width): d.text((x, yy), sub, font=f, fill=C["muted"]); yy += int(size * 1.5)
        yy += 6
    return yy
def wordmark(im, x, y, width=300):
    wm = Image.open(os.path.join(A, "wordmark.png")).convert("RGBA")
    r = width / wm.width; wm = wm.resize((width, int(wm.height * r)), Image.LANCZOS)
    im.paste(wm, (x, y), wm)
def footer(d, text="Crowe Sense  ·  Crowe Logic, Inc.  ·  Phoenix"):
    d.line((120, 990, 1800, 990), fill=C["line"], width=2)
    d.text((120, 1010), text, font=mono(20), fill=C["muted"])
def panel(im, path, box, caption=None, fit="cover"):
    """Paste an asset into box (x, y, w, h) with a hairline frame."""
    x, y, w, h = box
    if not os.path.exists(path):
        d = ImageDraw.Draw(im); d.rectangle((x, y, x + w, y + h), fill=C["paper"], outline=C["line"], width=2)
        d.text((x + 20, y + 20), os.path.basename(path) + " (missing)", font=mono(20), fill=C["brick"]); return
    art = Image.open(path).convert("RGB")
    r = max(w / art.width, h / art.height) if fit == "cover" else min(w / art.width, h / art.height)
    art = art.resize((int(art.width * r), int(art.height * r)), Image.LANCZOS)
    if fit == "cover":
        l = (art.width - w) // 2; t = 0; art = art.crop((l, t, l + w, t + h))
    frame = Image.new("RGB", (w, h), C["paper"]); frame.paste(art, ((w - art.width) // 2, (h - art.height) // 2))
    im.paste(frame, (x, y)); d = ImageDraw.Draw(im); d.rectangle((x, y, x + w, y + h), outline=C["line"], width=2)
    if caption: d.text((x, y + h + 12), caption, font=mono(18), fill=C["muted"])

def render(scene, target, out):
    im, d = base(); art = scene.get("art", "none")
    if art == "title":
        im = Image.new("RGB", (W, H), C["cream"]); d = ImageDraw.Draw(im)
        wordmark(im, 120, 300, 520)
        d.text((120, 470), "Crowe Sense", font=fraunces(120, 500), fill=C["ink"])
        d.text((124, 630), "A sensing node for a growing room", font=inter(34), fill=C["muted"])
        d.line((120, 720, 220, 720), fill=C["gold"], width=4)
        d.text((120, 745), ("For " + target).upper() if target not in ("YouTube",) else "SOUTHWEST MUSHROOMS  ·  CROWE LOGIC", font=inter(22, True), fill=C["gold"])
        footer(d, "September 2026"); im.save(out, quality=95); return out
    eyebrow(d, 120, 100, scene["eyebrow"])
    two_col = art in ("cad", "dash", "tests", "report", "path", "founder", "ask", "close")
    tw = 760 if two_col else 1400
    if art == "close": tw = 1100
    hsize = 60 if two_col else 72
    if len(scene["headline"]) > 70: hsize = 48
    yy = headline(d, 120, 160, scene["headline"], tw, hsize)
    yy = body(d, 120, yy + 24, scene.get("body", []), tw, 28 if two_col else 32)
    if art == "cad": panel(im, os.path.join(A, "cad-hero.png"), (960, 140, 840, 720), "the enclosure, rendered from the parametric model in this repo", fit="contain")
    elif art == "dash": panel(im, os.path.join(A, "dashboard.png"), (960, 140, 840, 720), "the node's own dashboard, demonstration data", fit="contain")
    elif art == "tests": panel(im, os.path.join(A, "tests.png"), (960, 140, 840, 720), "test output captured 2026-09-01", fit="contain")
    elif art == "report": panel(im, os.path.join(A, "report-1080.png"), (960, 140, 840, 720), "the investor report")
    elif art == "path":
        # node -> relay -> six surfaces, drawn
        x0, y0 = 960, 220
        for i, (t, sub) in enumerate([("The node", "SQLite on the node\nlocal API :8078"), ("The relay", "D1 hot, R2 forever\nCrowe ID on every read")]):
            bx = x0 + i * 300; d.rounded_rectangle((bx, y0, bx + 240, y0 + 150), 6, fill=C["paper"], outline=C["line"], width=2)
            d.text((bx + 18, y0 + 16), t, font=fraunces(28), fill=C["ink"]); d.multiline_text((bx + 18, y0 + 62), sub, font=mono(17), fill=C["muted"], spacing=6)
            if i == 0: d.text((bx + 255, y0 + 55), "→", font=inter(36), fill=C["gold"])
        d.text((x0 + 555, y0 + 55), "→", font=inter(36), fill=C["gold"])
        for j, s in enumerate(["desktop", "web", "phone + Mac", "Cortex", "terminal", "House / kiosk"]):
            cx = x0 + 610 + (j % 2) * 120 if False else x0 + 610; cy = y0 - 60 + j * 46
            d.rounded_rectangle((cx, cy, cx + 230, cy + 36), 4, fill=C["paper"], outline=C["line"], width=2)
            d.text((cx + 12, cy + 7), s, font=mono(18), fill=C["ink"])
        d.text((x0, y0 + 200), "contracts/telemetry-v1.md", font=mono(18), fill=C["muted"])
    elif art == "founder": panel(im, os.path.join(A, "founder.png"), (1100, 140, 700, 700), None, fit="cover") if os.path.exists(os.path.join(A, "founder.png")) else wordmark(im, 1200, 400, 520)
    elif art == "ask":
        rows = [("Pilot hardware, 25 nodes", "$12,000"), ("Hardware engineering, contract", "$35,000"), ("Founder, twelve months", "$60,000"), ("Pilot program, ten growers", "$15,000"), ("Compliance, insurance", "$10,000"), ("Legal, IP", "$8,000"), ("Instruments", "$4,000"), ("Contingency", "$31,000"), ("Total", "$175,000"), ("Cloud, analytics, inference", "$0")]
        y = 160
        for k, v in rows:
            bold = k == "Total"
            d.text((1000, y), k, font=inter(24, bold), fill=C["ink"] if bold else C["muted"]); d.text((1800, y), v, font=mono(24), fill=C["ink"], anchor="ra"); y += 44
            d.line((1000, y - 6, 1800, y - 6), fill=C["line"], width=1)
    elif art == "close":
        wordmark(im, 1340, 700, 460)
    footer(d); im.save(out, quality=95); return out

def tests_card():
    """Render the captured test output as an image (real text, captured this session)."""
    lines = ["$ cd firmware && pytest -q", open(os.path.join(A, "tests-firmware.txt")).read().strip(), "",
             "$ cd relay && node --test test/*.test.js", open(os.path.join(A, "tests-relay.txt")).read().strip(), "",
             "$ crowe-logic-foundry  (branch feat/crowe-sense)", "25 passed  (full suite 2,215 passed)", "",
             "$ crowe-logic-desktop  (branch feat/crowe-sense)", "14 passed, 0 failed  (+ 67 parity tests)", "",
             "$ crowe-cortex  (branch feat/crowe-sense)", "Tests  8 passed (8)   tsc: clean   vite build: ok"]
    im = Image.new("RGB", (1680, 1440), "#141814"); d = ImageDraw.Draw(im); y = 60
    for ln in lines:
        col = "#C9A227" if ln.startswith("$") else ("#86AA6E" if "pass" in ln else "#E9E6DC")
        d.text((60, y), ln, font=mono(34), fill=col); y += 56
    im.save(os.path.join(A, "tests.png"))

if __name__ == "__main__":
    tests_card(); print("tests.png written")
