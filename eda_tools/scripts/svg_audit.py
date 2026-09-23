"""SVG quality audit for eeschema exports: count real wires, NC flags, labels.

Usage:
    venv/Scripts/python.exe scripts/svg_audit.py file1.svg [file2.svg ...]
"""
from __future__ import annotations

import re
import sys
from collections import Counter

SPLIT = re.compile(r'(<g style="[^>]*stroke:(#[0-9A-Fa-f]{6})[^>]*>)')
PATH_D = re.compile(r'<path[^>]*\bd="([^"]+)"')
PTS = re.compile(r'([-\d.]+)[ ,]([-\d.]+)')


def audit(fn: str) -> None:
    svg = open(fn, encoding="utf-8").read()
    blocks = SPLIT.split(svg)
    from collections import Counter as _C
    colors = _C(blocks[i + 1] for i in range(1, len(blocks), 3))
    print(f"  [debug] style-blocks={len(blocks) // 3} colors={dict(colors)}")
    wires = []
    nc = 0
    labels = []
    for i in range(1, len(blocks), 3):
        color, body = blocks[i + 1], blocks[i + 2]
        if color != "#009600":
            continue
        for d in PATH_D.findall(body):
            pts = [(float(a), float(b)) for a, b in PTS.findall(d)]
            if len(pts) != 2:
                continue
            dx = abs(pts[0][0] - pts[1][0])
            dy = abs(pts[0][1] - pts[1][1])
            if dx > 2 or dy > 2:
                wires.append(pts)
            elif dx > 0.5 and dy > 0.5:
                nc += 1
        labels += [m for m in re.findall(r"<desc>([^<]{1,24})</desc>", body)]
    name = fn.replace("\\", "/").split("/")[-1]
    print(f"{name:20s} long_wires={len(wires):3d} nc_x={nc:3d} labels={len(labels)}")
    lengths = Counter()
    for a, b in wires:
        lengths["h" if abs(a[1] - b[1]) < 0.05 else ("v" if abs(a[0] - b[0]) < 0.05 else "DIAG")] += 1
    print(f"  shapes: {dict(lengths)}")
    netish = sorted(set(l for l in labels if re.fullmatch(r"[A-Za-z0-9_+\-]+", l)))
    print(f"  net-ish labels: {netish}")


if __name__ == "__main__":
    for fn in sys.argv[1:]:
        audit(fn)
