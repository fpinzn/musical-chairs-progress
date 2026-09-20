#!/usr/bin/env python3
"""Render the progress figure as the barking-dog poster from the bark app.

Usage: python tools/mock_bark.py <bark.png> <out.png> [px] [sim_days] [today]

Regions are read from the poster's ink: the frame, the sky, the soil with its
dashes, the dog's interior, the eye, the bark lines. The dog is the task fill
(C7 families, lighter), the eye stays black, the soil gets a sparse dash glyph,
the frame becomes a block, the bark lines are accents.
"""
import json
import random
import sys
from datetime import date

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import mock_vocab_lib as mv  # noqa: E402

src, out = sys.argv[1], sys.argv[2]
px = int(sys.argv[3]) if len(sys.argv) > 3 else 8
sim = float(sys.argv[4]) if len(sys.argv) > 4 else 5.4
today = date.fromisoformat(sys.argv[5]) if len(sys.argv) > 5 else date(2026, 9, 25)
root = __file__.rsplit("/", 2)[0]
CELL = 16
COLS = 70

# ── Regions from the ink ─────────────────────────────────────────────────
im = Image.open(src).convert("RGBA")
bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
bg.alpha_composite(im)
g = np.asarray(bg.convert("L"))
ink = g < 110
white = ~ink

wl, wn = ndimage.label(white)
sizes = ndimage.sum(white, wl, range(1, wn + 1))
order = np.argsort(-sizes) + 1
h, w = ink.shape
# Outside: the white component touching the image corners.
outside_ids = {wl[0, 0], wl[0, w - 1], wl[h - 1, 0], wl[h - 1, w - 1]} - {0}
outside = np.isin(wl, list(outside_ids))
# Sky and soil: the two largest enclosed white regions; sky is the higher one.
enclosed = [i for i in order if i not in outside_ids and sizes[i - 1] > 400]
cy = {i: ndimage.center_of_mass(wl == i)[0] for i in enclosed[:6]}
sky_id = enclosed[0]
soil_id = max((i for i in enclosed[:6] if i != sky_id), key=lambda i: cy[i])
sky, soil = wl == sky_id, wl == soil_id
dog_ids = [i for i in enclosed if i not in (sky_id, soil_id)]
dog_white = np.isin(wl, dog_ids)
frame_ink = ink & ndimage.binary_dilation(outside, iterations=45)
dog = ndimage.binary_closing(dog_white, iterations=14)
dog = ndimage.binary_fill_holes(dog)
# Ink blobs that are not the main outline: eye, mouth, bark lines, soil dashes.
il, inum = ndimage.label(ink)
isz = ndimage.sum(ink, il, range(1, inum + 1))
small = [i + 1 for i, sz in enumerate(isz) if sz < 0.04 * isz.max()]
blobs = np.isin(il, small)
eye = blobs & ndimage.binary_erosion(dog, iterations=6)
soil_f = ndimage.binary_fill_holes(soil)
sky_f = ndimage.binary_fill_holes(sky)
dashes = blobs & soil_f
bark = blobs & sky_f & ~dog
dog_fill = dog & ~ndimage.binary_dilation(eye, iterations=4)
horizon = ink & ndimage.binary_dilation(sky, iterations=3) & ndimage.binary_dilation(soil, iterations=3)

# ── Cell grid ────────────────────────────────────────────────────────────
scale = COLS * CELL / w
H = int(h * scale)
ROWS = H // CELL


def cells(mask, thresh=0.5):
    m = Image.fromarray((mask * 255).astype(np.uint8)).resize((COLS * CELL, ROWS * CELL), Image.LANCZOS)
    a = np.asarray(m) / 255.0
    return a.reshape(ROWS, CELL, COLS, CELL).mean(axis=(1, 3)) >= thresh


C_dog = cells(dog_fill)
C_eye = cells(ndimage.binary_dilation(eye, iterations=3), 0.25)
C_frame = cells(frame_ink, 0.35)
C_soil = cells(soil, 0.5) & ~C_dog
C_sky = cells(sky, 0.5) & ~C_dog
C_dash = cells(ndimage.binary_dilation(dashes, iterations=4), 0.2) & C_soil
C_bark = cells(ndimage.binary_dilation(bark, iterations=4), 0.2) & ~C_dog
C_horizon = cells(ndimage.binary_dilation(horizon, iterations=2), 0.3) & ~C_dog
C_dog = C_dog & ~C_eye
body_cells = [(r, c) for r in range(ROWS - 1, -1, -1) for c in range(COLS) if C_dog[r, c]]
print(f"grid {COLS}x{ROWS}: dog {len(body_cells)} eye {int(C_eye.sum())} frame {int(C_frame.sum())} soil {int(C_soil.sum())} dashes {int(C_dash.sum())} bark {int(C_bark.sum())}")

# Debug view of the regions.
dbg = np.zeros((ROWS, COLS, 3), np.uint8)
dbg[C_sky] = (20, 20, 40); dbg[C_soil] = (40, 30, 15); dbg[C_dash] = (160, 120, 60); dbg[C_frame] = (200, 200, 200)
dbg[C_dog] = (60, 120, 200); dbg[C_eye] = (255, 0, 0); dbg[C_bark] = (255, 220, 60); dbg[C_horizon] = (120, 120, 120)
Image.fromarray(dbg).resize((COLS * 6, ROWS * 6), Image.NEAREST).save(out.replace(".png", "_regions.png"))

# ── Tasks onto the dog ───────────────────────────────────────────────────
tasks = json.load(open(f"{root}/tools/fixture.json"))["tasks"]
by_id = {t["id"]: t for t in tasks}
level = {}
def lvl(t):
    if t["id"] not in level:
        level[t["id"]] = max([lvl(by_id[b]) + 1 for b in t["blockedBy"] if b in by_id] or [0])
    return level[t["id"]]
core = [t for t in tasks if t["due"] and t["effort"] and t["milestone"] in ("M0", "M1", "M2", "M3", "M4", "M5", "M6", "M7")]
core.sort(key=lambda t: (t["due"], lvl(t), t["id"]))
total = sum(t["effort"] for t in core)
acc = 0.0; idx = 0
for i, t in enumerate(core):
    acc += t["effort"]
    end = len(body_cells) if i == len(core) - 1 else round(acc * len(body_cells) / total)
    t["cells"] = body_cells[idx:end]; idx = end
    t["state"] = "done" if acc <= sim + 1e-9 else "started" if acc - t["effort"] < sim else "backlog"
done = {t["id"] for t in core if t["state"] == "done"}
for t in core:
    if t["state"] == "backlog":
        t["state"] = "blocked" if any(b not in done and b in by_id for b in t["blockedBy"]) else "todo"
    t["pocket"] = t["state"] != "done" and date.fromisoformat(t["due"]) <= today
HUES = [(255, 200, 40), (46, 196, 182), (70, 110, 255), (150, 80, 220), (60, 190, 90), (255, 120, 190), (255, 70, 70), (255, 140, 40), (236, 230, 216), (120, 220, 255)]
rng = random.Random(11)
for t in core:
    t["hue"] = rng.choice(HUES); t["seed"] = rng.random()
owner = {}
for t in core:
    for rc in t["cells"]:
        owner[rc] = t

# Lighter done families, per the C4 preference: fewer solid frames.
LIGHT_FRAMES = {"done": ["solid", "solid_small", "thick", "none", "none", "bracket", "thin"], "started": ["thin", "thick", "thin", "none"], "todo": ["none", "none", "thin"], "blocked": ["none"]}


def family(frng, state):
    marks = mv.STATE_MARKS.get(state, mv.MARKS_ALL[:22])
    base = frng.sample(marks, 3)
    return [(frng.choice(LIGHT_FRAMES[state]), frng.choice(base), frng.choice(mv.EXTRAS if state == "done" else ["none", "none", "corner", "dots"])) for _ in range(10)]


def dog_tile(t, r, c):
    st = t["state"]
    if "family" not in t or t["family_state"] != st:
        t["family"] = family(random.Random(t["seed"]), st); t["family_state"] = st
    frame, mark, extra = t["family"][(r * 31 + c * 17 + int(t["seed"] * 97)) % 10]
    hue = t["hue"]
    col = hue if st == "done" else (hue if (r + c) % 2 else mv.IVORY) if st == "started" else mv.dim(hue, 0.6) if st == "todo" else mv.dim(hue, 0.42)
    g = mv.glyph(frame, mark, extra, col)
    if t["pocket"] and st != "done":
        ImageDraw.Draw(g).line([2, 14, 14, 2], fill=(255, 70, 70), width=2)
    return g


def soil_tile(r, c, dash):
    """Sparse dashes: the poster's soil marks, plus a thin scatter between them."""
    crng = random.Random(r * 1000 + c)
    if not dash and crng.random() > 0.12:
        return None
    im_, dr, ss = mv.canvas(16); S = 16 * ss
    col = mv.dim(mv.IVORY, 0.85 if dash else 0.4)
    ln = crng.choice([0.5, 0.7, 0.85]) if dash else 0.35
    t_ = (2.6 if dash else 1.4) * ss
    dr.rounded_rectangle([S * (0.5 - ln / 2), S / 2 - t_, S * (0.5 + ln / 2), S / 2 + t_], radius=t_, fill=col)
    return mv.finish(im_, 16)


def block_tile(r, c):
    im_, dr, ss = mv.canvas(16); S = 16 * ss
    dr.rectangle([0, 0, S, S], fill=mv.IVORY)
    crng = random.Random(r * 7 + c * 13)
    if crng.random() < 0.35:
        q = 0.18 * S; dr.rectangle([S / 2 - q, S / 2 - q, S / 2 + q, S / 2 + q], fill=(0, 0, 0, 255))
    return mv.finish(im_, 16)


def bark_tile(r, c):
    im_, dr, ss = mv.canvas(16); S = 16 * ss
    crng = random.Random(r * 91 + c * 7)
    col = (255, 200, 40)
    mv._mark(dr, S, ss, crng.choice(["/", "-", "\\", "=", "*"]), col, size=1.0)
    return mv.finish(im_, 16)


def sky_tile(r, c):
    crng = random.Random(r * 3 + c * 11)
    if crng.random() > 0.05:
        return None
    im_, dr, ss = mv.canvas(16); S = 16 * ss
    q = 0.08 * S; dr.rectangle([S / 2 - q, S / 2 - q, S / 2 + q, S / 2 + q], fill=mv.dim(mv.IVORY, 0.35))
    return mv.finish(im_, 16)


img = Image.new("RGBA", (COLS * px, ROWS * px), (0, 0, 0, 255))
for r in range(ROWS):
    for c in range(COLS):
        t = owner.get((r, c))
        if t:
            tl = dog_tile(t, r, c)
        elif C_eye[r, c]:
            tl = None
        elif C_frame[r, c]:
            tl = block_tile(r, c)
        elif C_bark[r, c]:
            tl = bark_tile(r, c)
        elif C_horizon[r, c]:
            tl = soil_tile(r, c, True)
        elif C_soil[r, c]:
            tl = soil_tile(r, c, C_dash[r, c])
        elif C_sky[r, c]:
            tl = sky_tile(r, c)
        else:
            tl = None
        if tl is not None:
            img.alpha_composite(tl.resize((px, px), Image.LANCZOS), (c * px, r * px))
img.convert("RGB").save(out)
print("wrote", out)
