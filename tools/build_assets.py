#!/usr/bin/env python3
"""Bake the body mask and the night glyph sheet from the ASCII Man export.

Usage: python tools/build_assets.py <ascii-man public dir>

Writes site/glyphs_night.png and site/data/body.json.
"""
import colorsys
import json
import sys
from collections import deque

import numpy as np
from PIL import Image

src = sys.argv[1]
SHEET_COLS, CELL = 18, 16

sheet = Image.open(f"{src}/glyphs.png").convert("RGBA")
grid = np.array(json.load(open(f"{src}/data/initial_grid.json"))["grid"], dtype=np.int32)
rows, cols = grid.shape
num_glyphs = (sheet.width // CELL) * (sheet.height // CELL)

# Density and colourfulness per glyph.
arr = np.asarray(sheet).astype(np.float32)
density = np.zeros(num_glyphs)
sat = np.zeros(num_glyphs)
for g in range(num_glyphs):
    x, y = (g % SHEET_COLS) * CELL, (g // SHEET_COLS) * CELL
    px = arr[y:y + CELL, x:x + CELL, :3]
    bright = px.max(axis=2) > 20
    density[g] = bright.mean()
    if bright.any():
        p = px[bright]
        sat[g] = ((p.max(axis=1) - p.min(axis=1)) / (p.max(axis=1) + 1e-6)).mean()

# Body: dense or colourful cells, closed, largest component, holes filled.
dense = density[grid] > 0.40
colourful = np.zeros_like(dense)
mask = dense.copy()

def shift(m, dr, dc):
    out = np.zeros_like(m)
    rs, re = max(0, -dr), m.shape[0] - max(0, dr)
    cs, ce = max(0, -dc), m.shape[1] - max(0, dc)
    out[rs + dr:re + dr, cs + dc:ce + dc] = m[rs:re, cs:ce]
    return out

def dilate(m):
    o = m.copy()
    for d in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        o |= shift(m, *d)
    return o

def erode(m):
    o = m.copy()
    for d in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        o &= shift(m, *d)
    return o

mask = erode(dilate(dilate(mask)))  # close with radius 2, then shrink 1
mask = dilate(erode(mask))          # open to drop specks

def largest_component(m):
    seen = np.zeros_like(m)
    best = None
    for r in range(rows):
        for c in range(cols):
            if m[r, c] and not seen[r, c]:
                comp, q = [], deque([(r, c)])
                seen[r, c] = True
                while q:
                    cr, cc = q.popleft()
                    comp.append((cr, cc))
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = cr + dr, cc + dc
                        if 0 <= nr < rows and 0 <= nc < cols and m[nr, nc] and not seen[nr, nc]:
                            seen[nr, nc] = True
                            q.append((nr, nc))
                if best is None or len(comp) > len(best):
                    best = comp
    out = np.zeros_like(m)
    for r, c in best:
        out[r, c] = True
    return out

mask = largest_component(mask)

# Fill holes: anything not reachable from the border through non-mask cells.
outside = np.zeros_like(mask)
q = deque()
for r in range(rows):
    for c in (0, cols - 1):
        if not mask[r, c]:
            outside[r, c] = True
            q.append((r, c))
for c in range(cols):
    for r in (0, rows - 1):
        if not mask[r, c] and not outside[r, c]:
            outside[r, c] = True
            q.append((r, c))
while q:
    cr, cc = q.popleft()
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = cr + dr, cc + dc
        if 0 <= nr < rows and 0 <= nc < cols and not mask[nr, nc] and not outside[nr, nc]:
            outside[nr, nc] = True
            q.append((nr, nc))
mask = ~outside

runs = []
for r in range(rows):
    row_runs, c = [], 0
    while c < cols:
        if mask[r, c]:
            s = c
            while c < cols and mask[r, c]:
                c += 1
            row_runs.append([s, c])
        else:
            c += 1
    runs.append(row_runs)
json.dump({"rows": rows, "cols": cols, "runs": runs}, open("site/data/body.json", "w"))
print(f"body cells: {int(mask.sum())} of {rows*cols}; rows with body: {sum(1 for r in runs if r)}")

# Preview for a visual check.
prev = Image.new("RGB", (cols * 4, rows * 4), "black")
for r in range(rows):
    for c in range(cols):
        if mask[r, c]:
            prev.paste((255, 255, 255), (c * 4, r * 4, c * 4 + 4, r * 4 + 4))
        elif dense[r, c] or colourful[r, c]:
            prev.paste((80, 80, 80), (c * 4, r * 4, c * 4 + 4, r * 4 + 4))
prev.save("/private/tmp/claude-501/-Users-francisco-dev-barknito-unity-game/9e4f56dc-5e64-46be-9891-c18c1ed0fca5/scratchpad/body_mask.png")

# Night sheet: brightness 0.35, saturation 0.4, hue rotated 200 degrees.
night = arr.copy()
rgb = night[..., :3] / 255.0
out = np.zeros_like(rgb)
for y in range(rgb.shape[0]):
    for x in range(rgb.shape[1]):
        h, s, v = colorsys.rgb_to_hsv(*rgb[y, x])
        if v > 0:
            h = (h + 200 / 360.0) % 1.0
            out[y, x] = colorsys.hsv_to_rgb(h, min(1.0, s * 0.4), v * 0.35)
night[..., :3] = out * 255
Image.fromarray(night.astype(np.uint8), "RGBA").save("site/glyphs_night.png")
print("wrote site/glyphs_night.png")
