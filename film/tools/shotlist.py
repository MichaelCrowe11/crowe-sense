#!/usr/bin/env python3
"""shotlist.json: each scene's ordered clips. Curated by eye from the clip contact sheet on 2026-09-01
(face-free, no title cards or generated graphics, on topic). Motion assets made this session sit in assets/."""
import json, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); C = os.path.join(HERE, "footage", "clips"); A = os.path.join(HERE, "assets")
def clip(n): return os.path.join(C, n + ".mp4")
def asset(n): return os.path.join(A, n + ".mp4")
MACRO = ["9BaXvKDDRGY_003", "9BaXvKDDRGY_005", "9BaXvKDDRGY_010", "9BaXvKDDRGY_012", "aP5qnadCPUs_011", "dzNjDmP3Cgw_017", "dzNjDmP3Cgw_022", "asQtPL8d_to_016", "8KUYup2W2f4_036", "z2fpfQGNbQA_018", "9BaXvKDDRGY_001", "9BaXvKDDRGY_008"]
ROOM  = ["bgqt0q1I7J8_000", "bgqt0q1I7J8_016", "aP5qnadCPUs_062", "bgqt0q1I7J8_001", "z2fpfQGNbQA_073", "z2fpfQGNbQA_004"]
BENCH = ["aP5qnadCPUs_052", "Z8USXz3A1YE_007", "dzNjDmP3Cgw_015", "aP5qnadCPUs_040", "asQtPL8d_to_010", "Z8USXz3A1YE_015", "zb8TAU6Y-4s_025", "8KUYup2W2f4_007", "dzNjDmP3Cgw_003"]
shots = {
  "open":      [clip("bgqt0q1I7J8_000"), clip("9BaXvKDDRGY_003"), clip("aP5qnadCPUs_062")],
  "what":      [asset("turntable"), clip("bgqt0q1I7J8_016"), clip("z2fpfQGNbQA_073")],
  "path":      [asset("cli"), asset("mobile"), asset("desktop")],
  "dash":      [asset("dashboard")],
  "envelope":  [clip("dzNjDmP3Cgw_017"), asset("envelope")],
  "proven":    [asset("tests"), asset("relay")],
  "notproven": [clip("bgqt0q1I7J8_001"), clip("z2fpfQGNbQA_004"), clip("aP5qnadCPUs_062")],
  "founder":   [clip("aP5qnadCPUs_052"), clip("Z8USXz3A1YE_007"), clip("dzNjDmP3Cgw_015")],
  "ask":       [clip("9BaXvKDDRGY_010"), clip("dzNjDmP3Cgw_022"), clip("bgqt0q1I7J8_016")],
}
missing = [p for v in shots.values() for p in v if not os.path.exists(p)]
json.dump(shots, open(os.path.join(HERE, "shotlist.json"), "w"), indent=1)
print("shotlist written;", "missing:", [os.path.basename(m) for m in missing] or "none")
