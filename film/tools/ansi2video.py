#!/usr/bin/env python3
"""Render captured terminal sessions to a 1080p typewriter video: ansi2video.py CAPTURE_DIR OUT.mp4
CAPTURE_DIR holds N.cmd (the command line) and N.ansi (its real output). Commands are typed at 24 chars/s,
output is revealed line by line, colors come through a real terminal emulator (pyte)."""
import os, sys, subprocess, glob
import pyte
from PIL import Image, ImageDraw, ImageFont
cap, out = sys.argv[1], sys.argv[2]; frames = out[:-4] + "_frames"; os.makedirs(frames, exist_ok=True)
for f in os.listdir(frames): os.remove(os.path.join(frames, f))
COLS, ROWS = 100, 26; FONT = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 30); CW, CH = 18, 36
PAL = {"default": "#E9E6DC", "black": "#141814", "red": "#D8705A", "green": "#86AA6E", "yellow": "#C9A227", "blue": "#7FA3C9", "magenta": "#B58AC9", "cyan": "#7FC9C0", "white": "#E9E6DC", "brightblack": "#9AA096", "brightred": "#D8705A", "brightgreen": "#86AA6E", "brightyellow": "#C9A227", "brightblue": "#7FA3C9", "brightmagenta": "#B58AC9", "brightcyan": "#7FC9C0", "brightwhite": "#FFFFFF"}
def color(c):
    if c in PAL: return PAL[c]
    if len(c) == 6:
        try: int(c, 16); return "#" + c
        except ValueError: pass
    return PAL["default"]
screen = pyte.Screen(COLS, ROWS); stream = pyte.ByteStream(screen)
def paint(path, cursor=True):
    im = Image.new("RGB", (1920, 1080), "#141814"); d = ImageDraw.Draw(im)
    x0, y0 = 60, 40
    for y in range(ROWS):
        line = screen.buffer[y]
        for x in range(COLS):
            ch = line[x]
            if ch.data and ch.data != " ":
                col = color(ch.fg) if ch.fg != "default" else PAL["default"]
                if ch.bold and ch.fg == "default": col = "#FFFFFF"
                d.text((x0 + x * CW, y0 + y * CH), ch.data, font=FONT, fill=col)
    if cursor: d.rectangle((x0 + screen.cursor.x * CW, y0 + screen.cursor.y * CH + 4, x0 + screen.cursor.x * CW + 12, y0 + screen.cursor.y * CH + CH - 4), fill="#C9A227")
    d.text((60, 1030), "recorded against the demonstration node, 2026-09-01", font=ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 20), fill="#9AA096")
    im.save(path)
n = 0; FPS = 30
def hold(frames_n):
    global n
    for _ in range(frames_n): paint(os.path.join(frames, f"f{n:05d}.png")); n += 1
def feed(b): stream.feed(b)
hold(int(0.8 * FPS))
for cmdfile in sorted(glob.glob(os.path.join(cap, "*.cmd")), key=lambda p: int(os.path.basename(p).split(".")[0])):
    cmd = open(cmdfile).read().strip(); ansi = open(cmdfile[:-4] + ".ansi", "rb").read()
    feed(b"\x1b[33m$ \x1b[0m")
    shown = ("crowe " + cmd) if cmd.startswith("sense") else cmd
    for ch in shown:
        feed(ch.encode()); hold(max(1, FPS // 24))
    hold(int(0.5 * FPS)); feed(b"\r\n")
    lines = ansi.replace(b"\r\n", b"\n").split(b"\n")
    for ln in lines:
        feed(ln + b"\r\n"); hold(max(1, int(0.06 * FPS)))
    hold(int(1.6 * FPS))
hold(int(2.0 * FPS))
subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS), "-i", os.path.join(frames, "f%05d.png"), "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", out], check=True)
print(out, round(n / FPS, 1), "s")
