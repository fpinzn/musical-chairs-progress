#!/usr/bin/env python3
"""Render a silhouette as the progress figure with vocabulary A, no source models.

Usage: python tools/mock_silhouette.py <pose> <out.png> [px]

Body cells get tile glyphs (random family and colour from the source alphabet),
rings are contours of the distance field around the body, drawn with stroke
glyphs oriented along the contour. States are simulated bottom-up.
"""
import random
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import mock_vocab_lib as mv          # noqa: E402
from silhouettes import cell_mask    # noqa: E402

random.seed(3)
pose, out = sys.argv[1], sys.argv[2]
px = int(sys.argv[3]) if len(sys.argv) > 3 else 8
mask = cell_mask(pose)
ROWS, COLS = mask.shape

TILES = [g for g, c in enumerate(mv.CLS) if c["kind"] in ("filled", "tile", "nested", "outline")]
STROKES = {k: [g for g, c in enumerate(mv.CLS) if c["kind"] == k] for k in ("diag_up", "diag_down", "hline", "vline")}
WHITE = {k: [g for g in v if mv.CLS[g]["colour"] == "white"] for k, v in STROKES.items()}

# Distance field in cells from the body.
ys, xs = np.nonzero(mask)
gy, gx = np.mgrid[0:ROWS, 0:COLS]
d = np.full((ROWS, COLS), 1e9)
for y, x in zip(ys, xs):
    d = np.minimum(d, np.hypot(gy - y, gx - x))
d[mask] = 0

# Rings: log-spaced bands, breathing outward.
d0, ratio, band = 2.2, 1.22, 0.32
k = np.where(d > 0, np.log(np.maximum(d, 1e-6) / d0) / np.log(ratio), -1)
ring = (d >= d0) & ((k - np.floor(k)) < band)
grad_y, grad_x = np.gradient(d)


def stroke_kind(r, c):
    gxv, gyv = grad_x[r, c], grad_y[r, c]
    if abs(gxv) > 2.2 * abs(gyv):
        return "vline"
    if abs(gyv) > 2.2 * abs(gxv):
        return "hline"
    return "diag_down" if gxv * gyv < 0 else "diag_up"


order = [(r, c) for r in range(ROWS - 1, -1, -1) for c in range(COLS) if mask[r, c]]
n = len(order)
state = {}
for i, rc in enumerate(order):
    f = i / n
    state[rc] = "done" if f < 0.36 else "started" if f < 0.41 else "todo" if f < 0.55 else "blocked"

img = Image.new("RGBA", (COLS * px, ROWS * px), (0, 0, 0, 255))
cache = {}


def put(t, r, c):
    key = id(t)
    img.alpha_composite(t.resize((px, px), Image.LANCZOS), (c * px, r * px))


for r in range(ROWS):
    for c in range(COLS):
        if mask[r, c]:
            g = random.choice(TILES)
            put(mv.draw_A(mv.CLS[g], state[(r, c)]), r, c)
        elif ring[r, c] and random.random() > 0.22:
            kind = stroke_kind(r, c)
            pool = WHITE[kind] if random.random() < 0.7 else STROKES[kind]
            g = random.choice(pool or STROKES[kind])
            t = mv.draw_A(mv.CLS[g], "todo")
            a = np.asarray(t).astype(np.float32)
            a[..., :3] *= 0.6
            put(Image.fromarray(a.astype(np.uint8), "RGBA"), r, c)
img.convert("RGB").save(out)
print("wrote", out, "body cells", n)
