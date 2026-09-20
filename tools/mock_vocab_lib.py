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

src = "/Users/francisco/dev/generative-art/ascii-man/07-web-export-runtime/public"
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




# ── Vocabulary C: right angles, typed marks, flat colour ─────────────────
IVORY = (236, 230, 216)
HUES = [(46, 196, 182), (70, 110, 255), (150, 80, 220), (60, 190, 90), (255, 70, 70), (255, 120, 190), (255, 200, 40), (180, 160, 255)]


def _hash(cls, salt):
    return (hash((cls["kind"], cls["colour"], round(cls.get("d", 0), 2), salt)) & 0xFFFF) / 65535.0


def _hue(cls, salt=0):
    base = {"blue": 1, "white": 7, "green": 3, "yellow": 6, "red": 4, "grey": 0, "none": 0}[cls["colour"]]
    return HUES[(base + int(_hash(cls, salt) * 3)) % len(HUES)]


def _dither(dr, S, ss, col, seed):
    q = S / 4
    import random as _r
    rnd = _r.Random(seed)
    for i in range(4):
        for j in range(4):
            if rnd.random() < 0.45:
                dr.rectangle([i * q, j * q, (i + 1) * q - 1, (j + 1) * q - 1], fill=col)


def draw_C(cls, state, in_body=None):
    """in_body=True forces the tile drawing, False forces the stroke drawing."""
    size = 16
    im, dr, ss = canvas(size)
    k = cls["kind"]
    S = size * ss
    if k == "empty":
        return finish(im, size)
    is_stroke = k in ("diag_up", "diag_down", "hline", "vline", "corner", "fragment", "dot")
    if in_body is None:
        in_body = not is_stroke
    t = 2.0 * ss
    if not in_body:
        col = dim(IVORY, 0.7) if _hash(cls, 1) < 0.62 else dim(_hue(cls, 1), 0.9)
        kk = k if is_stroke else ("hline", "vline", "diag_up", "diag_down")[int(_hash(cls, 3) * 4)]
        if kk == "hline":
            dr.rectangle([0.15 * S, S / 2 - t / 2, 0.85 * S, S / 2 + t / 2], fill=col)
        elif kk == "vline":
            dr.rectangle([S / 2 - t / 2, 0.15 * S, S / 2 + t / 2, 0.85 * S], fill=col)
        elif kk in ("diag_up", "diag_down"):
            q = 0.22 * S
            steps = [(0.12, 0.66), (0.39, 0.39), (0.66, 0.12)] if kk == "diag_up" else [(0.12, 0.12), (0.39, 0.39), (0.66, 0.66)]
            for (x, y) in steps:
                dr.rectangle([x * S, y * S, x * S + q, y * S + q], fill=col)
        elif kk == "corner":
            dr.rectangle([0.2 * S, S / 2 - t / 2, 0.8 * S, S / 2 + t / 2], fill=col)
            dr.rectangle([S / 2 - t / 2, 0.2 * S, S / 2 + t / 2, 0.8 * S], fill=col)
        elif kk == "fragment":
            dr.rectangle([0.3 * S, S / 2 - t / 2, 0.7 * S, S / 2 + t / 2], fill=col)
        else:
            q = 0.2 * S
            dr.rectangle([S / 2 - q / 2, S / 2 - q / 2, S / 2 + q / 2, S / 2 + q / 2], fill=col)
        return finish(im, size)
    # Body tiles. The glyph kind only picks the variant.
    pad = 2.0 * ss
    box = [pad, pad, S - pad, S - pad]
    w = int(1.7 * ss)
    hole = 0.22 * S
    centre = [S / 2 - hole / 2, S / 2 - hole / 2, S / 2 + hole / 2, S / 2 + hole / 2]
    hue = _hue(cls, 2)
    if state == "blocked":
        c = dim(IVORY, 0.42)
        lw = int(2.0 * ss)
        dr.line([0.22 * S, 0.24 * S, 0.78 * S, 0.24 * S], fill=c, width=lw)
        dr.line([0.78 * S, 0.24 * S, 0.22 * S, 0.76 * S], fill=c, width=lw)
        dr.line([0.22 * S, 0.76 * S, 0.78 * S, 0.76 * S], fill=c, width=lw)
    elif state == "todo":
        if is_stroke and _hash(cls, 4) < 0.7:
            _dither(dr, S, ss, dim(IVORY, 0.45), int(_hash(cls, 5) * 1e6))
        else:
            dr.rectangle(box, outline=dim(IVORY, 0.55) if _hash(cls, 6) < 0.7 else dim(hue, 0.7), width=w)
    elif state == "started":
        c = hue if _hash(cls, 7) < 0.6 else IVORY
        dr.rectangle(box, outline=c, width=w)
        dr.rectangle(centre, fill=c)
    else:
        col = hue if _hash(cls, 8) < 0.62 else IVORY
        dr.rectangle(box, fill=col)
        if _hash(cls, 9) < 0.75:
            dr.rectangle(centre, fill=(0, 0, 0, 255))
    return finish(im, size)


# ── Vocabulary C3: typed marks, positive and negative ────────────────────
from PIL import ImageFont as _IF
_FONT_CACHE = {}


def _font(px):
    if px not in _FONT_CACHE:
        _FONT_CACHE[px] = _IF.truetype("/System/Library/Fonts/Menlo.ttc", px)
    return _FONT_CACHE[px]


BODY_MARKS = [("sq", 22), ("sqs", 12), ("*", 14), ("/", 9), ("\\", 9), ("|", 7), ("-", 7), ("=", 7), (">", 5), ("<", 5), (";", 3)]
_BODY_POOL = [m for m, w in BODY_MARKS for _ in range(w)]


def _mark(dr, S, ss, ch, col, box=None, size=0.78):
    """Draw a typed mark centred in the cell. 'sq' and 'sqs' are filled squares."""
    if ch == "sq":
        q = 0.62 * S; dr.rectangle([S / 2 - q / 2, S / 2 - q / 2, S / 2 + q / 2, S / 2 + q / 2], fill=col); return
    if ch == "sqs":
        q = 0.36 * S; dr.rectangle([S / 2 - q / 2, S / 2 - q / 2, S / 2 + q / 2, S / 2 + q / 2], fill=col); return
    f = _font(int(size * S))
    bb = dr.textbbox((0, 0), ch, font=f)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    dr.text((S / 2 - w / 2 - bb[0], S / 2 - h / 2 - bb[1]), ch, font=f, fill=col)


def draw_C3(cls, state, in_body=None):
    size = 16
    im, dr, ss = canvas(size)
    k = cls["kind"]
    S = size * ss
    if k == "empty":
        return finish(im, size)
    is_stroke = k in ("diag_up", "diag_down", "hline", "vline", "corner", "fragment", "dot")
    if in_body is None:
        in_body = not is_stroke
    if not in_body:
        col = dim(IVORY, 0.7) if _hash(cls, 1) < 0.62 else dim(_hue(cls, 1), 0.9)
        kk = k if is_stroke else ("hline", "vline", "diag_up", "diag_down")[int(_hash(cls, 3) * 4)]
        ch = {"hline": "-" if _hash(cls, 10) < 0.6 else "=", "vline": "|", "diag_up": "/", "diag_down": "\\",
              "corner": "+", "fragment": [">", "<", ";"][int(_hash(cls, 11) * 3)], "dot": "*" if _hash(cls, 12) < 0.5 else "."}[kk]
        _mark(dr, S, ss, ch, col, size=0.9)
        return finish(im, size)
    pad = 2.0 * ss
    box = [pad, pad, S - pad, S - pad]
    w = int(1.7 * ss)
    hue = _hue(cls, 2)
    ch = _BODY_POOL[int(_hash(cls, 13) * len(_BODY_POOL))]
    if state == "blocked":
        _mark(dr, S, ss, "Z", dim(IVORY, 0.42), size=0.8)
    elif state == "todo":
        c = dim(IVORY, 0.5) if _hash(cls, 6) < 0.7 else dim(hue, 0.7)
        if ch in ("sq", "sqs"):
            dr.rectangle(box, outline=c, width=w)
        else:
            _mark(dr, S, ss, ch, c)
    elif state == "started":
        c = hue if _hash(cls, 7) < 0.6 else IVORY
        dr.rectangle(box, outline=c, width=w)
        _mark(dr, S, ss, "sqs" if ch in ("sq", "sqs") else ch, c, size=0.6)
    else:
        col = hue if _hash(cls, 8) < 0.62 else IVORY
        if _hash(cls, 9) < 0.3:
            dr.rectangle(box, fill=col)                       # negative: mark knocked out
            _mark(dr, S, ss, "sqs" if ch == "sq" else ch, (0, 0, 0, 255), size=0.7)
        else:
            pos = ch if ch not in ("sq",) else ("sqs" if _hash(cls, 14) < 0.5 else ["*", "x", ":", "+", "="][int(_hash(cls, 15) * 5)])
            _mark(dr, S, ss, pos, col, size=0.92)              # positive: mark in colour, no box
    return finish(im, size)


# ── Combinatorial alphabet: frame × mark × extra ─────────────────────────
FRAMES = ["none", "thin", "thick", "solid", "solid_small", "bracket"]
MARKS_ALL = ["sq", "sqs", "*", "/", "\\", "|", "-", "=", ">", "<", ";", "+", "x", ":", ".", "^", "~", "o", "#", "%", "&", "\"", "Z", "z", "S", "N"]
EXTRAS = ["none", "corner", "double", "underline", "dots"]


def glyph(frame, mark, extra, col, size=16, mark_col=None):
    """One glyph of the combinatorial alphabet, in colour `col`, transparent background."""
    im, dr, ss = canvas(size)
    S = size * ss
    pad, w = 2.0 * ss, int(1.7 * ss)
    box = [pad, pad, S - pad, S - pad]
    black = (0, 0, 0, 255)
    inner = mark_col or col
    if frame == "thin":
        dr.rectangle(box, outline=col, width=int(1.1 * ss))
    elif frame == "thick":
        dr.rectangle(box, outline=col, width=int(2.4 * ss))
    elif frame == "solid":
        dr.rectangle(box, fill=col); inner = black
    elif frame == "solid_small":
        q = 0.34 * S; dr.rectangle([pad, pad, S - pad, S - pad], fill=col); dr.rectangle([S / 2 - q, S / 2 - q, S / 2 + q, S / 2 + q], fill=black); inner = col
    elif frame == "bracket":
        dr.rectangle([pad, pad, pad + w, S - pad], fill=col); dr.rectangle([S - pad - w, pad, S - pad, S - pad], fill=col)
    msize = 0.62 if frame in ("solid", "solid_small", "thin", "thick", "bracket") else 0.92
    if mark == "sq":
        q = (0.62 if frame == "none" else 0.36) * S; dr.rectangle([S / 2 - q / 2, S / 2 - q / 2, S / 2 + q / 2, S / 2 + q / 2], fill=inner)
    elif mark == "sqs":
        q = 0.3 * S; dr.rectangle([S / 2 - q / 2, S / 2 - q / 2, S / 2 + q / 2, S / 2 + q / 2], fill=inner)
    else:
        _mark(dr, S, ss, mark, inner, size=msize)
    if extra == "corner":
        q = 0.18 * S; dr.rectangle([S - pad - q, pad, S - pad, pad + q], fill=inner if frame in ("solid",) else col)
    elif extra == "double" and mark not in ("sq", "sqs"):
        _mark(dr, S, ss, mark, inner, size=0.4)
        f = _font(int(0.4 * S)); bb = dr.textbbox((0, 0), mark, font=f)
        dr.text((S * 0.62 - bb[0], S * 0.62 - bb[1]), mark, font=f, fill=inner)
    elif extra == "underline":
        dr.rectangle([pad, S - pad - w, S - pad, S - pad], fill=inner if frame == "solid" else col)
    elif extra == "dots":
        q = 0.12 * S
        for x in (0.25, 0.5, 0.75):
            dr.rectangle([x * S - q / 2, S - pad - q, x * S + q / 2, S - pad], fill=inner if frame == "solid" else col)
    return finish(im, size)


STATE_FRAMES = {
    "done": ["solid", "solid", "solid", "solid_small", "thick", "none", "bracket"],
    "started": ["thin", "thick", "thin", "none"],
    "todo": ["none", "none", "thin"],
    "blocked": ["none"],
}
STATE_MARKS = {
    "blocked": ["Z", "z", "Z", "~", ";", "S", "N"],
}


def family(rng, state, n=8):
    """A task's family: n glyph specs (frame, mark, extra) coherent for the state."""
    marks = STATE_MARKS.get(state, MARKS_ALL[:22])
    base = rng.sample(marks, min(3, len(marks)))
    out = []
    for _ in range(n):
        out.append((rng.choice(STATE_FRAMES[state]), rng.choice(base), rng.choice(EXTRAS if state == "done" else ["none", "none", "corner", "dots"])))
    return out


# ── Circle alphabet: the same method with round frames and marks ─────────
CFRAMES = ["none", "thin", "thick", "disc", "disc_core", "arc", "double"]
CMARKS = ["dot", "dots2", "dots3", "ring", "core", "cross", "tick", "halo", "half", "quarter", "pip", "star", "dash", "bar", "hex", "tri", "o", "O", "°", "•", "◦", "∘", "@", "%", "&", "8"]
CEXTRAS = ["none", "orbit", "sat", "ring_out", "twin"]


def cglyph(frame, mark, extra, col, size=16, mark_col=None):
    im, dr, ss = canvas(size)
    S = size * ss
    pad, w = 1.8 * ss, int(1.7 * ss)
    box = [pad, pad, S - pad, S - pad]
    black = (0, 0, 0, 255)
    inner = mark_col or col
    cx = cy = S / 2
    if frame == "thin":
        dr.ellipse(box, outline=col, width=int(1.1 * ss))
    elif frame == "thick":
        dr.ellipse(box, outline=col, width=int(2.4 * ss))
    elif frame == "disc":
        dr.ellipse(box, fill=col); inner = black
    elif frame == "disc_core":
        dr.ellipse(box, fill=col); q = 0.3 * S; dr.ellipse([cx - q, cy - q, cx + q, cy + q], fill=black); inner = col
    elif frame == "arc":
        dr.arc(box, 200, 340, fill=col, width=int(1.8 * ss)); dr.arc(box, 20, 160, fill=col, width=int(1.8 * ss))
    elif frame == "double":
        dr.ellipse(box, outline=col, width=int(1.1 * ss)); q = 0.3 * S; dr.ellipse([cx - q, cy - q, cx + q, cy + q], outline=col, width=int(1.1 * ss))
    big = frame == "none"
    r = (0.3 if big else 0.16) * S
    if mark == "dot":
        dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=inner)
    elif mark == "dots2":
        for x in (0.35, 0.65): dr.ellipse([x * S - r / 2, cy - r / 2, x * S + r / 2, cy + r / 2], fill=inner)
    elif mark == "dots3":
        for x in (0.28, 0.5, 0.72): dr.ellipse([x * S - r / 2.4, cy - r / 2.4, x * S + r / 2.4, cy + r / 2.4], fill=inner)
    elif mark == "ring":
        dr.ellipse([cx - r, cy - r, cx + r, cy + r], outline=inner, width=int(1.3 * ss))
    elif mark == "core":
        dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=inner); q = r * 0.45; dr.ellipse([cx - q, cy - q, cx + q, cy + q], fill=col if inner == black else black)
    elif mark == "cross":
        t = 1.4 * ss; dr.rectangle([cx - r, cy - t, cx + r, cy + t], fill=inner); dr.rectangle([cx - t, cy - r, cx + t, cy + r], fill=inner)
    elif mark == "tick":
        t = 1.4 * ss; dr.rectangle([cx - t, cy - r, cx + t, cy + r], fill=inner)
    elif mark == "halo":
        dr.ellipse([cx - r, cy - r, cx + r, cy + r], outline=inner, width=int(1.1 * ss)); q = r * 0.35; dr.ellipse([cx - q, cy - q, cx + q, cy + q], fill=inner)
    elif mark == "half":
        dr.pieslice([cx - r, cy - r, cx + r, cy + r], 90, 270, fill=inner)
    elif mark == "quarter":
        dr.pieslice([cx - r, cy - r, cx + r, cy + r], 180, 270, fill=inner)
    elif mark == "pip":
        q = r * 0.5; dr.ellipse([cx - q, cy - q, cx + q, cy + q], fill=inner)
    elif mark == "star":
        for a in (0, 45, 90, 135):
            import math
            dx, dy = math.cos(math.radians(a)) * r, math.sin(math.radians(a)) * r
            dr.line([cx - dx, cy - dy, cx + dx, cy + dy], fill=inner, width=int(1.3 * ss))
    elif mark == "dash":
        t = 1.4 * ss; dr.rectangle([cx - r, cy - t, cx + r, cy + t], fill=inner)
    elif mark == "bar":
        t = 2.2 * ss; dr.rectangle([cx - r, cy - t, cx + r, cy + t], fill=inner)
    elif mark == "hex":
        import math
        pts = [(cx + r * math.cos(math.radians(60 * i)), cy + r * math.sin(math.radians(60 * i))) for i in range(6)]
        dr.polygon(pts, outline=inner, fill=None); dr.line(pts + [pts[0]], fill=inner, width=int(1.2 * ss))
    elif mark == "tri":
        import math
        pts = [(cx + r * math.cos(math.radians(90 + 120 * i)), cy - r * math.sin(math.radians(90 + 120 * i))) for i in range(3)]
        dr.polygon(pts, fill=inner)
    else:
        _mark(dr, S, ss, mark, inner, size=0.62 if not big else 0.92)
    if extra == "orbit":
        q = 0.11 * S; dr.ellipse([S - pad - q * 2, pad, S - pad, pad + q * 2], fill=col)
    elif extra == "sat":
        q = 0.09 * S
        for x, y in ((0.15, 0.5), (0.85, 0.5)): dr.ellipse([x * S - q, y * S - q, x * S + q, y * S + q], fill=col)
    elif extra == "ring_out":
        dr.ellipse([pad * 0.3, pad * 0.3, S - pad * 0.3, S - pad * 0.3], outline=col, width=int(0.8 * ss))
    elif extra == "twin":
        q = 0.11 * S; dr.ellipse([pad, S - pad - q * 2, pad + q * 2, S - pad], fill=col)
    return finish(im, size)


CSTATE_FRAMES = {
    "done": ["disc", "disc", "disc", "disc_core", "thick", "none", "double"],
    "started": ["thin", "thick", "thin", "arc"],
    "todo": ["none", "none", "thin"],
    "blocked": ["none", "arc"],
}
CSTATE_MARKS = {"blocked": ["dots2", "dots3", "pip", "◦", "∘", "°", "dash"]}


def cfamily(rng, state, n=8):
    marks = CSTATE_MARKS.get(state, CMARKS[:20])
    base = rng.sample(marks, min(3, len(marks)))
    return [(rng.choice(CSTATE_FRAMES[state]), rng.choice(base), rng.choice(CEXTRAS if state == "done" else ["none", "none", "orbit", "sat"])) for _ in range(n)]
