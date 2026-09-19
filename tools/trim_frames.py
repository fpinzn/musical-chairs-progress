#!/usr/bin/env python3
"""Trim the ASCII Man frames.bin.gz to the three models the progress page uses.

Usage: python tools/trim_frames.py <ascii-man frames.bin.gz> site/data/frames.bin.gz

Keeps the models behind quality 0 (global Markov), 4 (automata) and 10 (MLP),
re-mapping the 11-slot quality table to 0 -> global, 1..9 -> automata, 10 -> MLP.
Output format is the same as the input, so the page can reuse the viewer's decoder.
"""
import gzip
import struct
import sys

src, dst = sys.argv[1], sys.argv[2]
buf = gzip.open(src, "rb").read()
rows, cols, num_unique, num_frames = struct.unpack_from("<HHHH", buf, 0)
q_to_unique = list(buf[8:19])
table_start = 19
offsets = [struct.unpack_from("<I", buf, table_start + 4 * i)[0] for i in range(num_unique)]
data_start = table_start + 4 * num_unique

def blob(ui):
    pos = data_start + offsets[ui]
    length = struct.unpack_from("<I", buf, pos)[0]
    return buf[pos:pos + 4 + length]

keep = [q_to_unique[0], q_to_unique[4], q_to_unique[10]]
new_q = [0] + [1] * 9 + [2]
blobs = [blob(ui) for ui in keep]
out = bytearray(struct.pack("<HHHH", rows, cols, len(blobs), num_frames))
out += bytes(new_q)
off = 0
for b in blobs:
    out += struct.pack("<I", off)
    off += len(b)
for b in blobs:
    out += b
with gzip.open(dst, "wb", compresslevel=9) as f:
    f.write(bytes(out))
print(f"{rows}x{cols}, {num_frames} frames, kept models {keep} -> {len(out)/1e6:.1f} MB raw")
