#!/usr/bin/env python3
"""The bark dog's interior filled like ASCII Man's body: the source quilt tiles, nothing else.

Usage: python tools/mock_bark_inside.py <bark.png> <out.png> [px] [sim_days] [today]
"""
import json, random, sys
from datetime import date
import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import mock_vocab_lib as mv  # noqa: E402

src, out = sys.argv[1], sys.argv[2]
px = int(sys.argv[3]) if len(sys.argv) > 3 else 10
sim = float(sys.argv[4]) if len(sys.argv) > 4 else 5.4
today = date.fromisoformat(sys.argv[5]) if len(sys.argv) > 5 else date(2026, 9, 25)
root = __file__.rsplit("/", 2)[0]
SRC = "/Users/francisco/dev/generative-art/ascii-man/07-web-export-runtime/public"
CELL, COLS = 16, 70

# ── Dog interior and eye from the poster's ink ───────────────────────────
im = Image.open(src).convert("RGBA")
bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
ink = np.asarray(bg.convert("L")) < 110
white = ~ink
wl, wn = ndimage.label(white)
sizes = ndimage.sum(white, wl, range(1, wn + 1))
order = np.argsort(-sizes) + 1
h, w = ink.shape
outside_ids = {wl[0, 0], wl[0, w - 1], wl[h - 1, 0], wl[h - 1, w - 1]} - {0}
enclosed = [i for i in order if i not in outside_ids and sizes[i - 1] > 400]
cy = {i: ndimage.center_of_mass(wl == i)[0] for i in enclosed[:6]}
sky_id = enclosed[0]
soil_id = max((i for i in enclosed[:6] if i != sky_id), key=lambda i: cy[i])
dog_ids = [i for i in enclosed if i not in (sky_id, soil_id)]
dog = ndimage.binary_fill_holes(ndimage.binary_closing(np.isin(wl, dog_ids), iterations=14))
il, inum = ndimage.label(ink)
isz = ndimage.sum(ink, il, range(1, inum + 1))
blobs = np.isin(il, [i + 1 for i, sz in enumerate(isz) if sz < 0.04 * isz.max()])
eye = blobs & ndimage.binary_erosion(dog, iterations=6)
ROWS = int(h * COLS * CELL / w) // CELL


def cells(mask, thresh=0.5):
    m = Image.fromarray((mask * 255).astype(np.uint8)).resize((COLS * CELL, ROWS * CELL), Image.LANCZOS)
    return (np.asarray(m) / 255.0).reshape(ROWS, CELL, COLS, CELL).mean(axis=(1, 3)) >= thresh


C_eye = cells(ndimage.binary_dilation(eye, iterations=3), 0.25)
C_dog = cells(dog) & ~C_eye
body = [(r, c) for r in range(ROWS - 1, -1, -1) for c in range(COLS) if C_dog[r, c]]
print(f"grid {COLS}x{ROWS}: dog {len(body)} cells, eye {int(C_eye.sum())}")

# ── Tasks bottom-up, as the page does ────────────────────────────────────
tasks = json.load(open(f"{root}/tools/fixture.json"))["tasks"]
by_id = {t["id"]: t for t in tasks}
level = {}
def lvl(t):
    if t["id"] not in level:
        level[t["id"]] = max([lvl(by_id[b]) + 1 for b in t["blockedBy"] if b in by_id] or [0])
    return level[t["id"]]
core = sorted([t for t in tasks if t["due"] and t["effort"] and t["milestone"] in tuple(f"M{i}" for i in range(8))], key=lambda t: (t["due"], lvl(t), t["id"]))
total = sum(t["effort"] for t in core); acc = 0.0; idx = 0
for i, t in enumerate(core):
    acc += t["effort"]; end = len(body) if i == len(core) - 1 else round(acc * len(body) / total)
    t["cells"] = body[idx:end]; idx = end
    t["state"] = "done" if acc <= sim + 1e-9 else "started" if acc - t["effort"] < sim else "backlog"
done = {t["id"] for t in core if t["state"] == "done"}
for t in core:
    if t["state"] == "backlog":
        t["state"] = "blocked" if any(b not in done and b in by_id for b in t["blockedBy"]) else "todo"
owner = {rc: t for t in core for rc in t["cells"]}

# ── ASCII Man's own tiles ────────────────────────────────────────────────
day = Image.open(f"{SRC}/glyphs.png").convert("RGBA")
night = Image.open(f"{root}/site/glyphs_night.png").convert("RGBA")
TILES = [g for g, c in enumerate(mv.CLS) if c["kind"] in ("filled", "tile", "nested", "outline")]
rng = random.Random(7)


def tile(g, sheet, alpha=1.0):
    x, y = (g % 18) * CELL, (g // 18) * CELL
    t = sheet.crop((x, y, x + CELL, y + CELL))
    if alpha < 1:
        a = np.asarray(t).astype(np.float32); a[..., :3] *= alpha
        t = Image.fromarray(a.astype(np.uint8), "RGBA")
    return t


img = Image.new("RGBA", (COLS * px, ROWS * px), (0, 0, 0, 255))
for (r, c), t in owner.items():
    g = TILES[(r * 31 + c * 17) % len(TILES)] if False else rng.choice(TILES)
    st = t["state"]
    if st == "done": tl = tile(g, day)
    elif st == "started": tl = tile(g, day if (r + c) % 2 else night)
    elif st == "todo": tl = tile(g, night)
    else: tl = tile(g, night, 0.5)
    img.alpha_composite(tl.resize((px, px), Image.LANCZOS), (c * px, r * px))
img.convert("RGB").save(out)
print("wrote", out)
