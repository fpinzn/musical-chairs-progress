#!/usr/bin/env python3
"""Export the typed and circle alphabets as white sheets the page tints at draw time.

Usage: python tools/build_alphabets.py

Writes site/glyphs_typed.png, site/glyphs_circles.png and site/data/alphabets.json.
The JSON carries, per style, the glyph pool for each state and each ring
direction, so the page only has to pick an index and tint it.
"""
import json
import sys

from PIL import Image

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import mock_vocab_lib as mv  # noqa: E402

root = __file__.rsplit("/", 2)[0]
WHITE = (255, 255, 255)
SHEET_COLS = 32

# C4 densities: done is mostly bare marks with a minority of solid frames.
TYPED_STATE_FRAMES = {
    "done": ["none", "none", "none", "none", "solid", "solid_small", "thick", "bracket", "thin"],
    "started": ["thin", "thick", "thin", "bracket"],
    "todo": ["none", "none", "none", "thin"],
    "blocked": ["none"],
}
CIRCLE_STATE_FRAMES = {
    "done": ["none", "none", "none", "none", "disc", "disc_core", "thick", "double", "thin"],
    "started": ["thin", "thick", "thin", "arc"],
    "todo": ["none", "none", "none", "thin"],
    "blocked": ["none", "arc"],
}
TYPED_STATE_MARKS = {
    "done": ["sq", "sqs", "*", "/", "\\", "|", "-", "=", ">", "<", ";", "+", "x", ":", "^", "~", "#", "%"],
    "started": ["sqs", "*", "+", "x", ":", "-", "|"],
    "todo": ["/", "\\", "|", "-", "=", ";", ":", ".", "~", "^"],
    "blocked": ["Z", "z", "S", "N", "~", ";"],
}
CIRCLE_STATE_MARKS = {
    "done": ["dot", "dots2", "dots3", "ring", "core", "cross", "tick", "halo", "half", "pip", "star", "dash", "hex", "tri"],
    "started": ["pip", "ring", "cross", "dot", "tick"],
    "todo": ["dots2", "dots3", "dash", "pip", "tick", "°", "◦"],
    "blocked": ["dots2", "dots3", "pip", "◦", "∘", "°"],
}
TYPED_EXTRAS = {"done": mv.EXTRAS, "started": ["none", "none", "corner"], "todo": ["none"], "blocked": ["none"]}
CIRCLE_EXTRAS = {"done": mv.CEXTRAS, "started": ["none", "none", "orbit"], "todo": ["none"], "blocked": ["none"]}


def build(frames, marks, extras, draw, state_frames, state_marks, state_extras, ring_marks):
    specs, index = [], {}

    def idx(f, m, e):
        key = (f, m, e)
        if key not in index:
            index[key] = len(specs)
            specs.append(key)
        return index[key]

    pools = {}
    for st in ("done", "started", "todo", "blocked"):
        pool = []
        for f in state_frames[st]:
            for m in state_marks[st]:
                for e in state_extras[st]:
                    pool.append(idx(f, m, e))
        pools[st] = pool
    ring = {d: [idx("none", m, "none") for m in ms] for d, ms in ring_marks.items()}
    rows = (len(specs) + SHEET_COLS - 1) // SHEET_COLS
    sheet = Image.new("RGBA", (SHEET_COLS * 16, rows * 16), (0, 0, 0, 0))
    for i, (f, m, e) in enumerate(specs):
        sheet.alpha_composite(draw(f, m, e, WHITE), ((i % SHEET_COLS) * 16, (i // SHEET_COLS) * 16))
    return sheet, {"count": len(specs), "pools": pools, "ring": ring}


typed_sheet, typed_meta = build(
    mv.FRAMES, mv.MARKS_ALL, mv.EXTRAS, mv.glyph, TYPED_STATE_FRAMES, TYPED_STATE_MARKS, TYPED_EXTRAS,
    {"0": ["-", "="], "1": ["|"], "2": ["/"], "3": ["\\"], "dot": [".", ":", "*", "+"]})
circle_sheet, circle_meta = build(
    mv.CFRAMES, mv.CMARKS, mv.CEXTRAS, mv.cglyph, CIRCLE_STATE_FRAMES, CIRCLE_STATE_MARKS, CIRCLE_EXTRAS,
    {"0": ["dots2", "dots3", "dash"], "1": ["tick", "pip"], "2": ["pip", "dot"], "3": ["pip", "dot"], "dot": ["pip", "ring"]})
typed_sheet.save(f"{root}/site/glyphs_typed.png")
circle_sheet.save(f"{root}/site/glyphs_circles.png")
json.dump({
    "sheetCols": SHEET_COLS,
    "palette": [list(c) for c in mv.HUES],
    "ivory": list(mv.IVORY),
    "typed": typed_meta,
    "circles": circle_meta,
}, open(f"{root}/site/data/alphabets.json", "w"))
print(f"typed {typed_meta['count']} glyphs, circles {circle_meta['count']} glyphs, palette {len(mv.HUES)}")
for k in ("done", "started", "todo", "blocked"):
    print(f"  {k}: typed {len(typed_meta['pools'][k])} circles {len(circle_meta['pools'][k])}")
