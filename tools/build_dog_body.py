#!/usr/bin/env python3
"""Body mask from a white-on-black silhouette: the largest blob is the body, the rest are accents.

Usage: python tools/build_dog_body.py <silhouette.png> <human_body.json> <out body.json> [width_cells]
"""
import json, sys
import numpy as np
from PIL import Image
from scipy import ndimage

src, human_path, out = sys.argv[1:4]
width_cells = int(sys.argv[4]) if len(sys.argv) > 4 else 56
human = json.load(open(human_path))
ROWS, COLS, CELL = human["rows"], human["cols"], 16

im = Image.open(src).convert("L")
a = np.asarray(im) > 128
ys, xs = np.nonzero(a)
crop = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
# Opening drops thin strokes (a horizon line touching the legs) out of the body.
opened = ndimage.binary_opening(crop, iterations=int(crop.shape[1] * 0.012))
lab, n = ndimage.label(opened)
sizes = ndimage.sum(opened, lab, range(1, n + 1))
body_px = lab == (int(np.argmax(sizes)) + 1)
accent_px = crop & ~ndimage.binary_dilation(body_px, iterations=2)

scale = width_cells * CELL / crop.shape[1]
W, H = int(crop.shape[1] * scale), int(crop.shape[0] * scale)
def to_cells(mask, thresh):
    m = Image.fromarray((mask * 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    canvas = Image.new("L", (COLS * CELL, ROWS * CELL), 0)
    canvas.paste(m, ((COLS * CELL - W) // 2, (ROWS * CELL - H) // 2))
    arr = np.asarray(canvas) / 255.0
    return arr.reshape(ROWS, CELL, COLS, CELL).mean(axis=(1, 3)) >= thresh
body = to_cells(body_px, 0.5)
accent = to_cells(accent_px, 0.25) & ~body
hm = np.zeros((ROWS, COLS), bool)
for r, rr in enumerate(human["runs"]):
    for s, e in rr:
        hm[r, s:e] = True
blank = hm & ~body & ~accent

def runs(mask):
    out_ = []
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
        out_.append(rr)
    return out_
# Source map: dog body cell k (bottom-up scanline) samples human body cell at the same fraction.
dog_cells = [(r, c) for r in range(ROWS - 1, -1, -1) for c in range(COLS) if body[r, c]]
hum_cells = [(r, c) for r in range(ROWS - 1, -1, -1) for c in range(COLS) if hm[r, c]]
source = [hum_cells[min(len(hum_cells) - 1, int(k / len(dog_cells) * len(hum_cells)))] for k in range(len(dog_cells))]
source = [r * COLS + c for r, c in source]
json.dump({"rows": ROWS, "cols": COLS, "runs": runs(body), "accent": runs(accent), "blank": runs(blank), "source": source}, open(out, "w"))
print(f"body {int(body.sum())} cells, accent {int(accent.sum())}, blank {int(blank.sum())}, rows {np.nonzero(body.any(1))[0][[0,-1]]}")
