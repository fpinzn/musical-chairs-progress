#!/usr/bin/env python3
"""Procedural dog silhouettes on the 70x126 cell grid.

Each pose is drawn from primitives in a 110x100 design box, supersampled,
then placed on the 1120x2016 canvas at a given width in cells. Returns a
boolean cell mask. `python tools/silhouettes.py out_dir` writes previews.
"""
import sys

import numpy as np
from PIL import Image, ImageDraw

W, H, CELL = 1120, 2016, 16


def _crown(dr, x0, x1, base, top, s):
    """Three-point crown between x0 and x1, base line at `base`, tips at `top`."""
    n = 3
    pts = [(x0 * s, base * s)]
    step = (x1 - x0) / n
    for i in range(n):
        pts.append(((x0 + step * i + step / 2) * s, top * s))
        pts.append(((x0 + step * (i + 1)) * s, base * s))
    dr.polygon(pts, fill=255)
    dr.rectangle([x0 * s, (base - 3) * s, x1 * s, (base + 4) * s], fill=255)
    r = 2.2 * s
    for i in range(n):
        cx = (x0 + step * i + step / 2) * s
        dr.ellipse([cx - r, top * s - r, cx + r, top * s + r], fill=255)


OY = 14          # headroom so the crown can float above the head
CROWN_GAP = 5    # design units of air between the head and the crown


def _shift(box):
    return [box[0], box[1] + OY, box[2], box[3] + OY]


def beagle_sitting(s=8, crown=True):
    im = Image.new("L", (110 * s, (100 + OY) * s), 0)
    dr = ImageDraw.Draw(im)
    E = lambda box: dr.ellipse([v * s for v in _shift(box)], fill=255)
    R = lambda box, rad=3: dr.rounded_rectangle([v * s for v in _shift(box)], radius=rad * s, fill=255)
    E([14, 46, 66, 92])          # haunches
    E([40, 30, 74, 86])          # chest
    E([56, 24, 80, 52])          # neck
    E([64, 12, 92, 38])          # head, domed
    R([82, 24, 104, 36], 3)      # muzzle, squarish
    E([60, 20, 74, 54])          # floppy ear, hangs down the back of the head
    R([58, 66, 66, 96], 2)       # front leg
    R([68, 66, 76, 96], 2)       # front leg
    R([54, 90, 70, 98], 2)       # front paw
    R([66, 90, 82, 98], 2)       # front paw
    R([26, 86, 48, 98], 3)       # hind paw
    dr.polygon([(18 * s, (62 + OY) * s), (8 * s, (34 + OY) * s), (14 * s, (32 + OY) * s), (26 * s, (58 + OY) * s)], fill=255)  # tail up
    E([6, 28, 16, 38])           # tail tip
    if crown:
        base = 12 + OY - CROWN_GAP
        _crown(dr, 64, 88, base, base - 12, s)
    return im


def beagle_standing(s=8, crown=True):
    im = Image.new("L", (110 * s, (100 + OY) * s), 0)
    dr = ImageDraw.Draw(im)
    E = lambda box: dr.ellipse([v * s for v in _shift(box)], fill=255)
    R = lambda box, rad=3: dr.rounded_rectangle([v * s for v in _shift(box)], radius=rad * s, fill=255)
    E([20, 40, 80, 70])          # body
    E([64, 28, 86, 56])          # neck
    E([74, 18, 98, 42])          # head
    R([90, 28, 108, 40], 3)      # muzzle
    E([70, 24, 82, 56])          # ear
    for x in (28, 40, 60, 72):   # legs
        R([x, 62, x + 8, 94], 2)
        R([x - 3, 88, x + 12, 97], 2)
    dr.polygon([(26 * s, (46 + OY) * s), (14 * s, (22 + OY) * s), (20 * s, (20 + OY) * s), (32 * s, (44 + OY) * s)], fill=255)  # tail up
    E([12, 16, 22, 26])
    if crown:
        base = 18 + OY - CROWN_GAP
        _crown(dr, 76, 96, base, base - 12, s)
    return im


POSES = {"sitting": beagle_sitting, "standing": beagle_standing}


def image_mask(path):
    """A silhouette from any RGBA or greyscale image: alpha where present, else luminance."""
    src = Image.open(path)
    if "A" in src.getbands():
        return src.split()[-1]
    return src.convert("L")


def cell_mask(pose, width_cells=48, y_center=0.52, crown=True):
    im = POSES[pose](crown=crown) if pose in POSES else image_mask(pose)
    bbox = im.getbbox()
    im = im.crop(bbox)
    scale = (width_cells * CELL) / im.width
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    canvas = Image.new("L", (W, H), 0)
    canvas.paste(im, ((W - im.width) // 2, int(H * y_center) - im.height // 2))
    a = np.asarray(canvas) > 127
    rows, cols = H // CELL, W // CELL
    m = a.reshape(rows, CELL, cols, CELL).mean(axis=(1, 3)) >= 0.5
    return m


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    for name in POSES:
        m = cell_mask(name)
        img = Image.fromarray((m * 255).astype(np.uint8)).resize((70 * 6, 126 * 6), Image.NEAREST)
        img.save(f"{out}/sil_{name}.png")
        print(name, int(m.sum()), "cells")
