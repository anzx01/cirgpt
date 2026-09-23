"""Offline probe: pin anchors vs drawn wires in a generated .kicad_sch.

Uses mcp_schematic's own parsers (_pin_positions_from_sch) so the probe sees
exactly what the generator saw.

Usage:
    venv/Scripts/python.exe scripts/pin_wire_probe.py <file.kicad_sch> [REF.PIN ...]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_schematic import _pin_positions_from_sch  # noqa: E402


def main() -> None:
    sch = Path(sys.argv[1])
    text = sch.read_text(encoding="utf-8", errors="replace")
    pins = _pin_positions_from_sch(text)
    wires = [
        tuple(map(float, m.groups()))
        for m in re.finditer(
            r"\(\s*wire\s+\(pts\s*\(xy ([\d.\-]+) ([\d.\-]+)\)\s*\(xy ([\d.\-]+) ([\d.\-]+)\)",
            text,
        )
    ]
    labels = [
        (m.group(1), float(m.group(2)), float(m.group(3)))
        for m in re.finditer(
            r'\(\s*label\s+"([^"]*)"\s*\(at ([\d.\-]+) ([\d.\-]+)', text
        )
    ]
    print(f"pins={len(pins)} wires={len(wires)} labels={len(labels)}")

    watch = sys.argv[2:]
    for (ref, pin), (px, py) in sorted(pins.items()):
        if ref.startswith("#"):
            continue
        tag = ""
        if watch and f"{ref}.{pin}" not in watch:
            continue
        ends = sum(1 for x1, y1, x2, y2 in wires if any(
            abs(a - px) < 0.01 and abs(b - py) < 0.01 for a, b in ((x1, y1), (x2, y2))))
        on_seg = sum(1 for x1, y1, x2, y2 in wires if (
            abs(x1 - x2) < 0.01 and abs(px - x1) < 0.01
            and min(y1, y2) - 0.01 <= py <= max(y1, y2) + 0.01
        ) or (
            abs(y1 - y2) < 0.01 and abs(py - y1) < 0.01
            and min(x1, x2) - 0.01 <= px <= max(x1, x2) + 0.01
        ))
        lab = [n for n, lx, ly in labels if abs(lx - px) < 0.01 and abs(ly - py) < 0.01]
        tag = f"wire_ends={ends} on_seg={on_seg} label={lab}"
        mark = "OK " if (ends or on_seg or lab) else "DEAD"
        print(f"[{mark}] {ref}.{pin} @({px:.2f},{py:.2f}) {tag}")


if __name__ == "__main__":
    main()
