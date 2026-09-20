#!/usr/bin/env python3
"""Merge single-model frames files (MODEL_ONLY runs) into the page's 3-model file.

Usage: python tools/merge_frames.py global.bin.gz automata.bin.gz mlp.bin.gz out.bin.gz
Quality table: 0 -> global, 1..9 -> automata, 10 -> mlp.
"""
import gzip, struct, sys
parts = [gzip.open(p, "rb").read() for p in sys.argv[1:4]]
rows, cols, _, nf = struct.unpack_from("<HHHH", parts[0], 0)
blobs = []
for b in parts:
    r, c, nu, f = struct.unpack_from("<HHHH", b, 0)
    assert (r, c, f, nu) == (rows, cols, nf, 1), (r, c, f, nu)
    ds = 19 + 4
    length = struct.unpack_from("<I", b, ds)[0]
    blobs.append(b[ds:ds + 4 + length])
out = bytearray(struct.pack("<HHHH", rows, cols, 3, nf)) + bytes([0] + [1] * 9 + [2])
off = 0
for bl in blobs:
    out += struct.pack("<I", off); off += len(bl)
for bl in blobs:
    out += bl
with gzip.open(sys.argv[4], "wb", compresslevel=9) as f:
    f.write(bytes(out))
print(f"merged {rows}x{cols} x {nf} frames -> {sys.argv[4]}")
