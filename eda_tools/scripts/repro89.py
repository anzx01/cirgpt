"""Reproduce design #89's schematic with current code and audit the wiring.

Run from eda_tools/:
    venv/Scripts/python.exe scripts/repro89.py [design_id]

Loads the design's CircuitIR straight from backend/app.db, runs the MCP
schematic pipeline, saves the SVG next to _debug89/ and prints per-net
routing decisions captured from the log.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
for noisy in ("mcp", "mcp.server", "asyncio"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


def load_ir(design_id: int) -> dict:
    db = ROOT.parent / "backend" / "app.db"
    conn = sqlite3.connect(str(db))
    row = conn.execute(
        "SELECT circuit_ir FROM circuit_designs WHERE id=?", (design_id,)
    ).fetchone()
    if not row or not row[0]:
        raise SystemExit(f"design {design_id} has no circuit_ir")
    ir = row[0]
    return json.loads(ir) if isinstance(ir, str) else ir


def audit_svg(svg: str) -> None:
    blocks = re.split(r'(<g style="[^>]*stroke:(#[0-9A-Fa-f]{6})[^>]*>)', svg)
    wire_segs, nc_flags, labels = [], 0, []
    for i in range(1, len(blocks), 3):
        color, body = blocks[i + 1], blocks[i + 2]
        for d in re.findall(r'<path[^>]*\bd="([^"]+)"', body):
            pts = [(float(a), float(b)) for a, b in re.findall(r'([-\d.]+)[ ,]([-\d.]+)', d)]
            if color == "#009600" and len(pts) == 2:
                dx, dy = abs(pts[0][0] - pts[1][0]), abs(pts[0][1] - pts[1][1])
                if dx > 2 or dy > 2:
                    wire_segs.append(pts)
                elif dx > 0.5 and dy > 0.5:
                    nc_flags += 1
        for m in re.findall(r'<desc>([^<]+)</desc>', body):
            labels.append(m)
    print(f"\nSVG audit: long wires={len(wire_segs)} nc_x={nc_flags} stroked_texts={len(labels)}")
    for s in wire_segs:
        print(f"  wire {s[0]} -> {s[1]}")


async def main() -> None:
    design_id = int(sys.argv[1]) if len(sys.argv) > 1 else 89
    ir = load_ir(design_id)
    import mcp_schematic

    # kicad-cli's first run loads the whole symbol library (>60s on this
    # machine); widen subprocess timeouts so the repro doesn't die on ERC.
    real_run = mcp_schematic.subprocess.run

    def patient_run(cmd, **kw):
        if "kicad-cli" in str(cmd):
            kw["timeout"] = max(kw.get("timeout", 0), 240)
        return real_run(cmd, **kw)

    mcp_schematic.subprocess.run = patient_run
    generate_kicad_artifacts_via_mcp = mcp_schematic.generate_kicad_artifacts_via_mcp

    result = await generate_kicad_artifacts_via_mcp(ir)
    out = ROOT.parent / "_debug89"
    out.mkdir(exist_ok=True)
    svg = result.get("svg") or ""
    (out / f"repro{design_id}.svg").write_text(svg, encoding="utf-8")
    erc = result.get("erc") or {}
    print(f"\nrepro{design_id}.svg saved ({len(svg)} chars)")
    print("erc:", json.dumps(erc.get("summary") or erc, ensure_ascii=False)[:300])
    skipped = result.get("skipped_components") or []
    if skipped:
        print("skipped:", skipped)
    audit_svg(svg)


if __name__ == "__main__":
    asyncio.run(main())
