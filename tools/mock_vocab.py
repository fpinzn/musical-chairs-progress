#!/usr/bin/env python3
"""Mock two replacement vocabularies for the ASCII Man glyphs and render both.

Usage: python tools/mock_vocab.py <ascii-man public dir> <out.png>

A: fine grid (70x126), abstract marks that survive 7 px cells.
B: half grid (35x63), pictorial marks: chairs, sitting dogs, notes.
Each source glyph index maps to a drawing per state, so the page could swap
sheets per state instead of tinting.
"""
import json
import sys

import numpy as np
from PIL import Image, ImageDraw

src, out = sys.argv[1], sys.argv[2]
SHEET_COLS, CELL = 18, 16
sheet = np.asarray(Image.open(f"{src}/glyphs.png").convert("RGBA")).astype(np.float32)
grid = np.array(json.load(open(f"{src}/data/initial_grid.json"))["grid"])
ROWS, COLS = grid.shape
N = 324

PALETTE = {"blue": (122, 134, 255), "white": (242, 232, 213), "green": (47, 184, 166),
           "yellow": (255, 182, 61), "red": (255, 90, 78), "grey": (120, 120, 120), "none": (0, 0, 0)}
BLOCKED = (58, 58, 70)


# ── Classify the source alphabet ─────────────────────────────────────────
def classify(g):
    x, y = (g % SHEET_COLS) * CELL, (g // SHEET_COLS) * CELL
    px = sheet[y:y + CELL, x:x + CELL, :3]
    b = px.max(axis=2) > 20
    d = float(b.mean())
    if d == 0:
        return {"kind": "empty", "colour": "none", "d": 0}
    p = px[b]
    m = p.mean(0)
    r, gr, bl = m
    mx, mn = m.max(), m.min()
    if mx - mn < 40:
        colour = "white" if mx > 150 else "grey"
    elif r > gr and r > bl:
        colour = "red" if gr < 120 else "yellow"
    elif gr > r and gr > bl:
        colour = "green"
    else:
        colour = "blue"
    ys, xs = np.nonzero(b)
    rows, cols = b.any(1).sum(), b.any(0).sum()
    size = max(rows, cols) / CELL
    inner = b[3:13, 3:13].mean()
    c = np.corrcoef(xs, ys)[0, 1] if xs.std() > 0 and ys.std() > 0 else 0.0
    if d >= 0.75:
        kind = "filled"
    elif rows >= 10 and cols >= 10 and d > 0.25 and inner < 0.15:
        kind = "outline"
    elif rows >= 10 and cols >= 10 and d > 0.3 and inner < 0.6:
        kind = "nested"
    elif rows >= 8 and cols >= 8 and abs(c) > 0.7 and d < 0.35:
        kind = "diag_down" if c > 0 else "diag_up"
    elif rows <= 3 and cols >= 6:
        kind = "hline"
    elif cols <= 3 and rows >= 6:
        kind = "vline"
    elif d < 0.08:
        kind = "dot"
    elif rows >= 8 and cols >= 8:
        kind = "tile"          # square with inner marks
    else:
        kind = "corner" if (rows >= 5 and cols >= 5) else "fragment"
    return {"kind": kind, "colour": colour, "d": d, "size": size, "c": c}


CLS = [classify(g) for g in range(N)]


# ── Drawing helpers (supersampled) ───────────────────────────────────────
def canvas(size, ss=4):
    im = Image.new("RGBA", (size * ss, size * ss), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im), ss


def finish(im, size):
    return im.resize((size, size), Image.LANCZOS)


def dim(col, f):
    return tuple(int(v * f) for v in col)


def state_colour(colour, state):
    base = PALETTE[colour]
    if state == "blocked":
        return BLOCKED
    if state == "todo":
        return dim(base, 0.55)
    return base


# ── Vocabulary A: abstract marks, 16 px ──────────────────────────────────
def draw_A(cls, state):
    size = 16
    im, dr, ss = canvas(size)
    k, col = cls["kind"], state_colour(cls["colour"], state)
    S = size * ss
    if k == "empty":
        return finish(im, size)
    w = max(2, int(1.6 * ss))
    if k in ("diag_up", "diag_down", "hline", "vline", "corner", "fragment", "dot"):
        # Strokes become beads along the same direction.
        c = dim(PALETTE[cls["colour"]], 0.7)
        pts = {"diag_up": [(0.2, 0.8), (0.5, 0.5), (0.8, 0.2)], "diag_down": [(0.2, 0.2), (0.5, 0.5), (0.8, 0.8)],
               "hline": [(0.2, 0.5), (0.5, 0.5), (0.8, 0.5)], "vline": [(0.5, 0.2), (0.5, 0.5), (0.5, 0.8)],
               "corner": [(0.25, 0.5), (0.5, 0.5), (0.5, 0.75)], "fragment": [(0.35, 0.5), (0.65, 0.5)], "dot": [(0.5, 0.5)]}[k]
        rad = 1.3 * ss if k != "dot" else 1.0 * ss
        for (px, py) in pts:
            dr.ellipse([px * S - rad, py * S - rad, px * S + rad, py * S + rad], fill=c)
        return finish(im, size)
    # Tiles become geometric marks; the state decides the fill.
    pad = 2.2 * ss
    box = [pad, pad, S - pad, S - pad]
    shape = {"filled": "circle", "tile": "ring_dot", "nested": "double", "outline": "square"}[k]
    if state == "blocked":
        dr.ellipse(box, outline=col, width=w) if shape != "square" else dr.rectangle(box, outline=col, width=w)
        dr.line([pad, S - pad, S - pad, pad], fill=col, width=w)
        return finish(im, size)
    if shape == "square":
        if state == "done":
            dr.rectangle(box, fill=col)
        elif state == "started":
            dr.rectangle(box, outline=col, width=w)
            dr.rectangle([pad, S / 2, S - pad, S - pad], fill=col)
        else:
            dr.rectangle(box, outline=col, width=w)
    elif shape == "double":
        dr.ellipse(box, outline=col, width=w)
        inner = [pad * 2.2, pad * 2.2, S - pad * 2.2, S - pad * 2.2]
        if state == "done":
            dr.ellipse(inner, fill=col)
        elif state == "started":
            dr.pieslice(inner, 90, 270, fill=col)
            dr.ellipse(inner, outline=col, width=w)
        else:
            dr.ellipse(inner, outline=col, width=w)
    else:
        if state == "done":
            dr.ellipse(box, fill=col)
            if shape == "ring_dot":
                dr.ellipse([S / 2 - 1.4 * ss, S / 2 - 1.4 * ss, S / 2 + 1.4 * ss, S / 2 + 1.4 * ss], fill=(0, 0, 0, 255))
        elif state == "started":
            dr.ellipse(box, outline=col, width=w)
            dr.pieslice(box, 90, 270, fill=col)
        else:
            dr.ellipse(box, outline=col, width=w)
            if shape == "ring_dot":
                dr.ellipse([S / 2 - 1.2 * ss, S / 2 - 1.2 * ss, S / 2 + 1.2 * ss, S / 2 + 1.2 * ss], fill=col)
    return finish(im, size)


# ── Vocabulary B: pictorial marks, 32 px ─────────────────────────────────
def note(dr, S, ss, col, flip):
    # Eighth note: head bottom-left, stem up the right side, flag.
    hx, hy = (0.36 * S, 0.72 * S) if not flip else (0.64 * S, 0.72 * S)
    rx, ry = 0.16 * S, 0.11 * S
    dr.ellipse([hx - rx, hy - ry, hx + rx, hy + ry], fill=col)
    sx = hx + rx * 0.85 if not flip else hx - rx * 0.85
    dr.line([sx, hy - ry * 0.4, sx, 0.18 * S], fill=col, width=int(1.6 * ss))
    fx = 0.2 * S if not flip else -0.2 * S
    dr.line([sx, 0.18 * S, sx + fx, 0.36 * S], fill=col, width=int(1.6 * ss))


def chair(dr, S, ss, col, fill, knocked=False):
    w = int(1.8 * ss)
    if knocked:
        # On its side: back along the floor, legs pointing right.
        dr.rectangle([0.18 * S, 0.62 * S, 0.82 * S, 0.70 * S], fill=col if fill else None, outline=col, width=w)   # back on floor
        dr.rectangle([0.18 * S, 0.44 * S, 0.30 * S, 0.62 * S], fill=col if fill else None, outline=col, width=w)   # seat, upright
        dr.line([0.30 * S, 0.48 * S, 0.62 * S, 0.48 * S], fill=col, width=w)                                        # leg
        dr.line([0.30 * S, 0.58 * S, 0.62 * S, 0.58 * S], fill=col, width=w)                                        # leg
        return
    dr.rectangle([0.22 * S, 0.14 * S, 0.34 * S, 0.60 * S], fill=col if fill else None, outline=col, width=w)       # back
    dr.rectangle([0.22 * S, 0.56 * S, 0.76 * S, 0.66 * S], fill=col if fill else None, outline=col, width=w)       # seat
    dr.line([0.26 * S, 0.66 * S, 0.26 * S, 0.90 * S], fill=col, width=w)
    dr.line([0.72 * S, 0.66 * S, 0.72 * S, 0.90 * S], fill=col, width=w)


def dog(dr, S, ss, col, sitting, x0=0.0, y0=0.0):
    # A sitting dog facing right, or a standing one lower and longer.
    if sitting:
        dr.ellipse([(0.36 + x0) * S, (0.30 + y0) * S, (0.72 + x0) * S, (0.62 + y0) * S], fill=col)               # body
        dr.ellipse([(0.56 + x0) * S, (0.12 + y0) * S, (0.84 + x0) * S, (0.38 + y0) * S], fill=col)               # head
        dr.polygon([((0.58 + x0) * S, (0.16 + y0) * S), ((0.52 + x0) * S, (0.02 + y0) * S), ((0.66 + x0) * S, (0.12 + y0) * S)], fill=col)  # ear
        dr.line([(0.62 + x0) * S, (0.56 + y0) * S, (0.62 + x0) * S, (0.66 + y0) * S], fill=col, width=int(2.2 * ss))  # front leg
        dr.line([(0.40 + x0) * S, (0.50 + y0) * S, (0.26 + x0) * S, (0.40 + y0) * S], fill=col, width=int(1.6 * ss))  # tail
    else:
        dr.ellipse([(0.30 + x0) * S, (0.50 + y0) * S, (0.76 + x0) * S, (0.72 + y0) * S], fill=col)
        dr.ellipse([(0.66 + x0) * S, (0.36 + y0) * S, (0.90 + x0) * S, (0.58 + y0) * S], fill=col)
        for lx in (0.38, 0.50, 0.60, 0.70):
            dr.line([(lx + x0) * S, (0.68 + y0) * S, (lx + x0) * S, (0.90 + y0) * S], fill=col, width=int(1.8 * ss))
        dr.line([(0.32 + x0) * S, (0.56 + y0) * S, (0.20 + x0) * S, (0.44 + y0) * S], fill=col, width=int(1.6 * ss))


def draw_B(cls, state):
    size = 32
    im, dr, ss = canvas(size)
    k = cls["kind"]
    S = size * ss
    if k == "empty":
        return finish(im, size)
    if k in ("diag_up", "diag_down", "hline", "vline", "corner", "fragment", "dot"):
        col = dim(PALETTE[cls["colour"]], 0.75)
        if k in ("diag_up", "corner"):
            note(dr, S, ss, col, False)
        elif k == "diag_down":
            note(dr, S, ss, col, True)
        elif k == "hline":
            dr.rectangle([0.25 * S, 0.44 * S, 0.75 * S, 0.56 * S], fill=col)                     # whole rest
        elif k == "vline":
            dr.line([0.5 * S, 0.15 * S, 0.5 * S, 0.85 * S], fill=col, width=int(2 * ss))       # bar line
            dr.ellipse([0.62 * S, 0.36 * S, 0.72 * S, 0.46 * S], fill=col)
            dr.ellipse([0.62 * S, 0.54 * S, 0.72 * S, 0.64 * S], fill=col)
        elif k == "fragment":
            dr.ellipse([0.4 * S, 0.4 * S, 0.6 * S, 0.6 * S], fill=col)
        else:
            dr.ellipse([0.44 * S, 0.44 * S, 0.56 * S, 0.56 * S], fill=col)
        return finish(im, size)
    col = state_colour(cls["colour"], state)
    if state == "blocked":
        chair(dr, S, ss, col, False, knocked=True)
    elif state == "todo":
        chair(dr, S, ss, col, False)
    elif state == "started":
        chair(dr, S, ss, col, True)
        dog(dr, S, ss, PALETTE["white"], False, x0=0.12, y0=0.06)
    else:
        chair(dr, S, ss, col, True)
        dog(dr, S, ss, PALETTE["white"], True, x0=0.02, y0=0.02)
    return finish(im, size)


# ── Body mask and a simulated state field ────────────────────────────────
body = json.load(open("site/data/body.json"))
mask = np.zeros((ROWS, COLS), dtype=bool)
for r, runs in enumerate(body["runs"]):
    for s, e in runs:
        mask[r, s:e] = True


def state_field(mask, done=0.36, started=0.05, todo=0.14):
    """Bottom-up fill: done, in progress, to-do, then blocked to the top."""
    order = [(r, c) for r in range(mask.shape[0] - 1, -1, -1) for c in range(mask.shape[1]) if mask[r, c]]
    n = len(order)
    field = {}
    for i, rc in enumerate(order):
        f = i / n
        field[rc] = "done" if f < done else "started" if f < done + started else "todo" if f < done + started + todo else "blocked"
    return field


def render(vocab, draw, tile, step, cell_px):
    """Render the figure sampling every `step` cells, `cell_px` on screen per cell."""
    rows, cols = (ROWS + step - 1) // step, (COLS + step - 1) // step
    m = mask[::step, ::step]
    field = state_field(m)
    cache = {}
    img = Image.new("RGBA", (cols * cell_px, rows * cell_px), (0, 0, 0, 255))
    for r in range(rows):
        for c in range(cols):
            g = int(grid[r * step, c * step])
            cls = CLS[g]
            st = field.get((r, c), "ring")
            key = (g, st)
            if key not in cache:
                if st == "ring":
                    t = draw(cls, "todo") if cls["kind"] not in ("filled", "tile", "nested", "outline") else draw({"kind": "dot", "colour": cls["colour"]}, "todo")
                    t = Image.eval(t, lambda v: v)  # copy
                    a = np.asarray(t).astype(np.float32); a[..., :3] *= 0.55
                    t = Image.fromarray(a.astype(np.uint8), "RGBA")
                else:
                    t = draw(cls, st)
                cache[key] = t.resize((cell_px, cell_px), Image.LANCZOS if cell_px < tile else Image.NEAREST)
            img.alpha_composite(cache[key], (c * cell_px, r * cell_px))
    return img


panels = [
    ("A · FINE GRID 70x126 · DESKTOP 8 px", render("A", draw_A, 16, 1, 8)),
    ("B · HALF GRID 35x63 · DESKTOP 16 px", render("B", draw_B, 32, 2, 16)),
    ("A · PHONE 5 px", render("A", draw_A, 16, 1, 5)),
    ("B · PHONE 10 px", render("B", draw_B, 32, 2, 10)),
]
gap, top = 24, 28
W = sum(p.width for _, p in panels) + gap * (len(panels) + 1)
H = max(p.height for _, p in panels) + top + gap
sheet_img = Image.new("RGB", (W, H), (12, 12, 12))
dr = ImageDraw.Draw(sheet_img)
x = gap
for label, p in panels:
    dr.text((x, 8), label, fill=(200, 200, 200))
    sheet_img.paste(p, (x, top), p)
    x += p.width + gap
sheet_img.save(out)

# Also a legend strip of the tiles per state for each vocabulary.
leg = Image.new("RGB", (4 * 40 + 40, 2 * 48 + 20), (12, 12, 12))
for vi, (draw, tile) in enumerate([(draw_A, 16), (draw_B, 32)]):
    for si, st in enumerate(["todo", "started", "done", "blocked"]):
        t = draw({"kind": "filled", "colour": "blue", "d": 1, "size": 1, "c": 0}, st).resize((32, 32), Image.NEAREST)
        leg.paste(t, (20 + si * 40, 10 + vi * 48), t)
leg.save(out.replace(".png", "_legend.png"))
print("wrote", out)
