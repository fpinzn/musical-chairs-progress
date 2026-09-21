#!/usr/bin/env python3
"""Bake a silhouette into the page's figure format.

Usage: python tools/build_figure.py <silhouette.png> <name> [width_cells]

Writes site/data/body_<name>.json with:
  runs    body cells, as per-row [start, end) runs
  accent  thin strokes peeled off the body, always lit
  blank   cells any other figure lights that this one must clear
  source  per body cell, the human-figure cell it samples for the source style
  rings   flat [r, c, dir] triples for the contour aura (dir 0 h, 1 v, 2 up, 3 down)
"""
import json
import random
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

src, name = sys.argv[1], sys.argv[2]
width_cells = int(sys.argv[3]) if len(sys.argv) > 3 else 56
root = __file__.rsplit("/", 2)[0]
human = json.load(open(f"{root}/site/data/body_human.json"))
ROWS, COLS, CELL = human["rows"], human["cols"], 16
rng = random.Random(4)

sil = Image.open(src).convert("L")
a = np.asarray(sil) > 128
ys, xs = np.nonzero(a)
crop = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
opened = ndimage.binary_opening(crop, iterations=max(1, int(crop.shape[1] * 0.012)))
lab, n = ndimage.label(opened)
sizes = ndimage.sum(opened, lab, range(1, n + 1))
body_px = ndimage.binary_fill_holes(lab == (int(np.argmax(sizes)) + 1))
accent_px = crop & ~ndimage.binary_dilation(body_px, iterations=2)

max_w, max_h = width_cells * CELL, int(ROWS * 0.78) * CELL
scale = min(max_w / crop.shape[1], max_h / crop.shape[0])
W, H = max(1, int(crop.shape[1] * scale)), max(1, int(crop.shape[0] * scale))
ox, oy = (COLS * CELL - W) // 2, (ROWS * CELL - H) // 2


def to_cells(mask, thresh):
    m = Image.fromarray((mask * 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    canvas = Image.new("L", (COLS * CELL, ROWS * CELL), 0)
    canvas.paste(m, (ox, oy))
    return (np.asarray(canvas) / 255.0).reshape(ROWS, CELL, COLS, CELL).mean(axis=(1, 3)) >= thresh


body = to_cells(body_px, 0.5)
accent = to_cells(accent_px, 0.25) & ~body
hm = np.zeros((ROWS, COLS), bool)
for r, rr in enumerate(human["runs"]):
    for s, e in rr:
        hm[r, s:e] = True
blank = hm & ~body & ~accent


def runs(mask):
    out = []
    for r in range(ROWS):
        rr, c = [], 0
        while c < COLS:
            if mask[r, c]:
                s = c
                while c < COLS and mask[r, c]:
                    c += 1
                rr.append([s, c])
            else:
                c += 1
        out.append(rr)
    return out


dog_cells = [(r, c) for r in range(ROWS - 1, -1, -1) for c in range(COLS) if body[r, c]]
hum_cells = [(r, c) for r in range(ROWS - 1, -1, -1) for c in range(COLS) if hm[r, c]]
source = [hum_cells[min(len(hum_cells) - 1, int(k / len(dog_cells) * len(hum_cells)))] for k in range(len(dog_cells))]
source = [r * COLS + c for r, c in source]

# Contour rings around the silhouette.
solid = body | accent
ys2, xs2 = np.nonzero(solid)
gy, gx = np.mgrid[0:ROWS, 0:COLS]
d = np.full((ROWS, COLS), 1e9)
for y, x in zip(ys2, xs2):
    d = np.minimum(d, np.hypot(gy - y, gx - x))
SPACING = 2.0
ring_id = np.floor(d / SPACING).astype(int)
lit = (d >= 1.5) & ((d / SPACING - np.floor(d / SPACING)) < 0.5) & ~solid
grad_y, grad_x = np.gradient(d)
dash = {}
rings = []
for r in range(ROWS):
    for c in range(COLS):
        if not lit[r, c]:
            continue
        rid = int(ring_id[r, c])
        if rid not in dash:
            dash[rid] = rng.choice([(6, 1), (9, 2), (5, 1), (12, 1), (3, 1)])
        on, off = dash[rid]
        if (r * 3 + c * 5 + rid * 7) % (on + off) >= on:
            continue
        gxv, gyv = grad_x[r, c], grad_y[r, c]
        dirn = 1 if abs(gxv) > 2.2 * abs(gyv) else 0 if abs(gyv) > 2.2 * abs(gxv) else (3 if gxv * gyv < 0 else 2)
        rings += [r, c, dirn]

out = {"rows": ROWS, "cols": COLS, "runs": runs(body), "accent": runs(accent), "blank": runs(blank),
       "source": source, "rings": rings}
json.dump(out, open(f"{root}/site/data/body_{name}.json", "w"))
print(f"{name}: body {int(body.sum())} accent {int(accent.sum())} blank {int(blank.sum())} rings {len(rings)//3}")
