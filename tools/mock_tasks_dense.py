#!/usr/bin/env python3
"""Render the figure from the real task layout with one mark per task.

Usage: python tools/mock_tasks.py <out.png> [px] [sim_days] [today]

Cells are assigned to tasks the way the page does it (bottom-up scanline,
due date then dependency depth). Each task gets one mark and one hue, so a
task reads as a run of identical glyphs. States come from a simulation of
`sim_days` of attention done.
"""
import json
import random
import sys
from datetime import date

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import mock_vocab_lib as mv  # noqa: E402

out = sys.argv[1]
px = int(sys.argv[2]) if len(sys.argv) > 2 else 8
sim = float(sys.argv[3]) if len(sys.argv) > 3 else 5.4
today = date.fromisoformat(sys.argv[4]) if len(sys.argv) > 4 else date(2026, 9, 25)
root = __file__.rsplit("/", 2)[0]
tasks = json.load(open(f"{root}/tools/fixture.json"))["tasks"]
body = json.load(open(f"{root}/site/data/body.json"))
ROWS, COLS = body["rows"], body["cols"]
mask = np.zeros((ROWS, COLS), bool)
for r, rr in enumerate(body["runs"]):
    for s, e in rr:
        mask[r, s:e] = True
cells = [(r, c) for r in range(ROWS - 1, -1, -1) for c in range(COLS) if mask[r, c]]

by_id = {t["id"]: t for t in tasks}
level = {}
def lvl(t):
    if t["id"] not in level:
        level[t["id"]] = max([lvl(by_id[b]) + 1 for b in t["blockedBy"] if b in by_id] or [0])
    return level[t["id"]]
core = [t for t in tasks if t["due"] and t["effort"] and t["milestone"] in ("M0", "M1", "M2", "M3", "M4", "M5", "M6", "M7")]
core.sort(key=lambda t: (t["due"], lvl(t), t["id"]))
total = sum(t["effort"] for t in core)
acc = 0.0
idx = 0
for i, t in enumerate(core):
    acc += t["effort"]
    end = len(cells) if i == len(core) - 1 else round(acc * len(cells) / total)
    t["cells"] = cells[idx:end]
    idx = end
    t["state"] = "done" if acc <= sim + 1e-9 else "started" if acc - t["effort"] < sim else "backlog"
done = {t["id"] for t in core if t["state"] == "done"}
for t in core:
    if t["state"] == "backlog":
        t["state"] = "blocked" if any(b not in done and b in by_id for b in t["blockedBy"]) else "todo"
    t["pocket"] = t["state"] != "done" and date.fromisoformat(t["due"]) <= today

HUES = [(255, 200, 40), (46, 196, 182), (70, 110, 255), (150, 80, 220), (60, 190, 90), (255, 120, 190), (255, 70, 70), (255, 140, 40), (236, 230, 216), (120, 220, 255)]
MS_HUE = {"M0": (236, 230, 216), "M1": (255, 200, 40), "M2": (46, 196, 182), "M3": (70, 110, 255),
          "M4": (150, 80, 220), "M5": (60, 190, 90), "M6": (255, 120, 190), "M7": (255, 70, 70)}
MARKS = ["sq", "sqs", "*", "/", "\\", "|", "-", "=", ">", "<", ";", "+", "x", ":"]
rng = random.Random(11)
for t in core:
    t["mark"] = rng.choice(MARKS + ["/", "\\", "*", "sqs"])
    t["hue"] = rng.choice(HUES)


def tile(t, r, c):
    size = 16
    im, dr, ss = mv.canvas(size)
    S = size * ss
    pad, w = 2.0 * ss, int(1.7 * ss)
    box = [pad, pad, S - pad, S - pad]
    hue, ch, st = t["hue"], t["mark"], t["state"]
    # Position inside the run's row segment, to make bars and end caps.
    row_cells = [cc for (rr, cc) in t["cells"] if rr == r]
    first, last = c == min(row_cells), c == max(row_cells)
    if st == "done":
        if t["bar"]:
            dr.rectangle([0 if not first else pad, pad, S if not last else S - pad, S - pad], fill=hue)
            if ch != "sq":
                mv._mark(dr, S, ss, "sqs" if ch == "sq" else ch, (0, 0, 0, 255), size=0.7)
        else:
            mv._mark(dr, S, ss, "sqs" if ch == "sq" else ch, hue, size=0.92)
    elif st == "started":
        dr.rectangle(box, outline=hue, width=w)
        mv._mark(dr, S, ss, "sqs" if ch in ("sq", "sqs") else ch, hue, size=0.6)
    elif st == "todo":
        if t["sparse"] and (r * 7 + c * 13) % 3 == 0:
            return mv.finish(im, size)
        mv._mark(dr, S, ss, "sqs" if ch == "sq" else ch, mv.dim(hue, 0.6), size=0.9)
    else:
        mv._mark(dr, S, ss, "Z", mv.dim(hue, 0.42), size=0.8)
    if t["pocket"] and st != "done":
        dr.line([pad, S - pad, S - pad, pad], fill=(255, 70, 70), width=int(1.6 * ss))
    return mv.finish(im, size)


for t in core:
    t["bar"] = rng.random() < 0.8
    t["sparse"] = False

# Rings from the distance field, one mark per ring, dashed in runs.
ys, xs = np.nonzero(mask)
gy, gx = np.mgrid[0:ROWS, 0:COLS]
d = np.full((ROWS, COLS), 1e9)
for y, x in zip(ys, xs):
    d = np.minimum(d, np.hypot(gy - y, gx - x))
SPACING = 2.0
ring_id = np.floor(d / SPACING).astype(int)
ring = (d >= 1.5) & ((d / SPACING) - np.floor(d / SPACING) < 0.5)
grad_y, grad_x = np.gradient(d)
ring_style = {}


def ring_tile(r, c):
    rid = int(ring_id[r, c])
    if rid not in ring_style:
        ring_style[rid] = rng.choice([(6, 1), (9, 2), (5, 1), (12, 1)])
    on, off = ring_style[rid]
    phase = (r * 3 + c * 5 + rid * 7) % (on + off)
    if phase >= on:
        return None
    cell_rng = random.Random(r * 1000 + c)
    coloured = cell_rng.random() < 0.22
    hue = cell_rng.choice(HUES[:8])
    gxv, gyv = grad_x[r, c], grad_y[r, c]
    kind = "vline" if abs(gxv) > 2.2 * abs(gyv) else "hline" if abs(gyv) > 2.2 * abs(gxv) else ("diag_down" if gxv * gyv < 0 else "diag_up")
    ch = {"hline": "-", "vline": "|", "diag_up": "/", "diag_down": "\\"}[kind]
    size = 16
    im, dr, ss = mv.canvas(size)
    S = size * ss
    mv._mark(dr, S, ss, ch, mv.dim(hue, 0.95) if coloured else mv.dim(mv.IVORY, 0.78), size=1.0)
    return mv.finish(im, size)


img = Image.new("RGBA", (COLS * px, ROWS * px), (0, 0, 0, 255))
owner = {}
for t in core:
    for rc in t["cells"]:
        owner[rc] = t
for r in range(ROWS):
    for c in range(COLS):
        t = owner.get((r, c))
        if t:
            tl = tile(t, r, c)
        elif ring[r, c]:
            tl = ring_tile(r, c)
        else:
            continue
        if tl is not None:
            img.alpha_composite(tl.resize((px, px), Image.LANCZOS), (c * px, r * px))
img.convert("RGB").save(out)
print("wrote", out, f"{len(core)} tasks, {len(done)} done")
