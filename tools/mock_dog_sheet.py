#!/usr/bin/env python3
"""Render a silhouette in the C4 style: airy typed marks, contour rings, tasks bottom-up.

Usage: python tools/mock_dog_sheet.py <silhouette.png> <out.png> [px] [sim_days] [width_cells]

C4 is the light variant of vocabulary C: done cells are mostly bare marks in
colour with a minority of solid squares, to-do is dim marks and dither, blocked
is a Z. Rings come from the distance field around the silhouette, typed along
the contour direction.
"""
import json
import random
import sys
from datetime import date

import numpy as np
from PIL import Image

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import mock_vocab_lib as mv  # noqa: E402

src, out = sys.argv[1], sys.argv[2]
px = int(sys.argv[3]) if len(sys.argv) > 3 else 8
sim = float(sys.argv[4]) if len(sys.argv) > 4 else 5.4
width_cells = int(sys.argv[5]) if len(sys.argv) > 5 else 46
today = date(2026, 9, 25)
root = __file__.rsplit("/", 2)[0]
ROWS, COLS, CELL = 126, 70, 16
rng = random.Random(4)

# ── Cell mask, centred on the grid ───────────────────────────────────────
sil = Image.open(src).convert("L")
# Fit the silhouette to the frame on whichever axis binds, so wide and tall dogs
# both land at a comparable size.
max_w, max_h = width_cells * CELL, int(ROWS * 0.80) * CELL
scale = min(max_w / sil.width, max_h / sil.height)
sil = sil.resize((max(1, int(sil.width * scale)), max(1, int(sil.height * scale))), Image.LANCZOS)
canvas = Image.new("L", (COLS * CELL, ROWS * CELL), 0)
canvas.paste(sil, ((COLS * CELL - sil.width) // 2, (ROWS * CELL - sil.height) // 2))
arr = np.asarray(canvas) / 255.0
mask = arr.reshape(ROWS, CELL, COLS, CELL).mean(axis=(1, 3)) >= 0.5
body = [(r, c) for r in range(ROWS - 1, -1, -1) for c in range(COLS) if mask[r, c]]

# ── Tasks bottom-up, as the page orders them ─────────────────────────────
tasks = json.load(open(f"{root}/tools/fixture.json"))["tasks"]
by_id = {t["id"]: t for t in tasks}
level = {}


def lvl(t):
    if t["id"] not in level:
        level[t["id"]] = max([lvl(by_id[b]) + 1 for b in t["blockedBy"] if b in by_id] or [0])
    return level[t["id"]]


core = sorted([t for t in tasks if t["due"] and t["effort"] and t["milestone"] in tuple(f"M{i}" for i in range(8))],
              key=lambda t: (t["due"], lvl(t), t["id"]))
total = sum(t["effort"] for t in core)
acc = idx = 0
for i, t in enumerate(core):
    acc += t["effort"]
    end = len(body) if i == len(core) - 1 else round(acc * len(body) / total)
    t["cells"] = body[idx:end]
    idx = end
    t["state"] = "done" if acc <= sim + 1e-9 else "started" if acc - t["effort"] < sim else "backlog"
done = {t["id"] for t in core if t["state"] == "done"}
for t in core:
    if t["state"] == "backlog":
        t["state"] = "blocked" if any(b not in done and b in by_id for b in t["blockedBy"]) else "todo"
    t["pocket"] = t["state"] != "done" and date.fromisoformat(t["due"]) <= today
owner = {rc: t for t in core for rc in t["cells"]}

# ── Rings: contours of the distance field, typed along the contour ───────
ys, xs = np.nonzero(mask)
gy, gx = np.mgrid[0:ROWS, 0:COLS]
d = np.full((ROWS, COLS), 1e9)
for y, x in zip(ys, xs):
    d = np.minimum(d, np.hypot(gy - y, gx - x))
SPACING = 2.0
ring_id = np.floor(d / SPACING).astype(int)
ring = (d >= 1.5) & ((d / SPACING - np.floor(d / SPACING)) < 0.5)
grad_y, grad_x = np.gradient(d)
ring_dash = {}

TILE_KINDS = ["filled", "tile", "nested", "outline"]
COLOURS = ["blue", "white", "green", "yellow", "red"]


def cls_for(r, c, salt=0):
    q = random.Random(r * 1009 + c * 131 + salt)
    return {"kind": q.choice(TILE_KINDS), "colour": q.choice(COLOURS), "d": q.random(), "size": 1, "c": 0}


img = Image.new("RGBA", (COLS * px, ROWS * px), (0, 0, 0, 255))
for r in range(ROWS):
    for c in range(COLS):
        t = owner.get((r, c))
        if t:
            g = mv.draw_C3(cls_for(r, c), t["state"], True)
            if t["pocket"] and t["state"] != "done":
                from PIL import ImageDraw
                ImageDraw.Draw(g).line([2, 14, 14, 2], fill=(255, 70, 70), width=2)
        elif ring[r, c]:
            rid = int(ring_id[r, c])
            if rid not in ring_dash:
                ring_dash[rid] = rng.choice([(6, 1), (9, 2), (5, 1), (12, 1), (3, 1)])
            on, off = ring_dash[rid]
            if (r * 3 + c * 5 + rid * 7) % (on + off) >= on:
                continue
            gxv, gyv = grad_x[r, c], grad_y[r, c]
            kind = "vline" if abs(gxv) > 2.2 * abs(gyv) else "hline" if abs(gyv) > 2.2 * abs(gxv) else ("diag_down" if gxv * gyv < 0 else "diag_up")
            cq = random.Random(r * 977 + c * 31)
            g = mv.draw_C3({"kind": kind, "colour": cq.choice(COLOURS) if cq.random() < 0.25 else "white", "d": cq.random(), "size": 1, "c": 0}, "todo", False)
        else:
            continue
        img.alpha_composite(g.resize((px, px), Image.LANCZOS), (c * px, r * px))
img.convert("RGB").save(out)
print(f"wrote {out}: body {len(body)} cells, {len(core)} tasks, {len(done)} done")
