"""Manufacturable PCB pipeline: KiCad board file -> Freerouting -> DRC -> Gerber.

The previous "kicad_pcb" artifact was a labeled placeholder (no pads, no
nets). This module writes a REAL board file — footprints with pads bound to
IR nets — then routes it with Freerouting (via Specctra DSN/session, driven
by KiCad's bundled pcbnew Python), runs kicad-cli DRC and exports Gerber +
drill + position files. The output is board-house ready.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

KICAD_BIN = r"G:\Program Files\KiCad\10.0\bin"
KICAD_PYTHON = os.path.join(KICAD_BIN, "python.exe")
KICAD_CLI = os.path.join(KICAD_BIN, "kicad-cli.exe")
FREEROUTING_JAR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tools", "freerouting-1.9.0.jar",  # v2.4.1 needs Java 25; 1.9.0 runs on 21
)

# Default two-layer manufacturing rules (1oz, JLCPCB-class).
MANUFACTURING_RULES = {
    "track_width_mm": 0.25,
    "clearance_mm": 0.2,
    "via_drill_mm": 0.3,
    "via_diameter_mm": 0.6,
    "silkscreen_text_mm": 1.0,
}


def _fmt(v: float) -> str:
    return f"{v:.4f}"


def write_kicad_pcb_file(layout: Dict[str, Any], out_path: str) -> str:
    """Write a complete .kicad_pcb (nets + footprints with live pads + outline).

    Pads are inlined (not resolved from footprint libraries) so the file is
    self-contained: pcbnew, Freerouting's DSN export and kicad-cli all work
    offline. Geometry comes from the preview generator's per-footprint pad
    layout, so board and preview cannot drift apart.
    """
    from kicad.pcb_generator import _geom_for, _pads_local, _FOOTPRINT_GEOM  # noqa: PLC0415

    # Real placement lives on the INNER component list (grid placement fills
    # position there); the outer preview list may carry None positions.
    components = (layout.get("layout") or {}).get("components") or layout.get("components") or []
    dims = layout.get("dimensions") or {"width": 100.0, "height": 80.0}
    rules = MANUFACTURING_RULES

    # --- pin-label -> pin-index resolution ---
    # The IR wires some parts by pin NAME (Q1.B, J3.D+, U3.IO18); board pads
    # are numbered. A component's own node list holds pin i+1's label, so a
    # name connection maps to the pad at that position.
    comp_pin_labels: Dict[str, List[str]] = {}
    for comp in components:
        comp_pin_labels[str(comp.get("name") or "")] = [str(n) for n in (comp.get("nodes") or [])]

    ir_nets = [
        (str(n.get("name") or ""), [str(c) for c in (n.get("connections") or [])])
        for n in ((layout.get("_ir_nets")) or [])
    ] or None

    # --- nets: index 0 reserved for unconnected pads ---
    # Ground aliases merge into one net: an IR net whose connections include
    # '0' is electrically tied to ground (e.g. SHIELD -> [J3.7, 0]) and leaving
    # it separate made DRC report USB-C shield pads shorting two nets.
    def _canonical(nm: str) -> str:
        return "GND" if nm.strip().lower() in {"0", "gnd", "vss", "dgnd", "agnd"} else nm

    net_names: List[str] = []
    net_index: Dict[str, int] = {}
    for comp in components:
        for node in comp.get("nodes") or []:
            nm = _canonical(str(node))
            if nm.startswith("NC$") or nm in net_index:
                continue
            net_index[nm] = len(net_names) + 1
            net_names.append(nm)

    lines: List[str] = []
    lines.append('(kicad_pcb (version 20240108) (generator "CircuitGPT")')
    lines.append('  (general (thickness 1.6))')
    lines.append('  (paper "A4")')
    lines.append(
        '  (layers'
        ' (0 "F.Cu" signal) (31 "B.Cu" signal)'
        ' (36 "B.SilkS" user) (37 "F.SilkS" user)'
        ' (38 "B.Mask" user) (39 "F.Mask" user)'
        ' (44 "Edge.Cuts" user))'
    )
    lines.append('  (net 0 "")')
    for i, name in enumerate(net_names, start=1):
        lines.append(f'  (net {i} "{name}")')

    w = float(dims.get("width") or 100.0)
    h = float(dims.get("height") or 80.0)
    x0, y0 = 5.0, 5.0
    lines.append(
        f'  (gr_rect (start {_fmt(x0)} {_fmt(y0)}) (end {_fmt(x0 + w)} {_fmt(y0 + h)})'
        f' (stroke (width 0.1) (type solid)) (layer "Edge.Cuts"))'
    )

    for comp in components:
        fp = str(comp.get("footprint") or "")
        ref = str(comp.get("name") or comp.get("ref") or "?")
        pos = comp.get("position") or {"x": 0, "y": 0}
        rot = int(comp.get("rotation") or 0) % 360
        cx, cy = float(pos.get("x") or 0), float(pos.get("y") or 0)
        geom = _geom_for(fp)
        pads = _pads_local(geom)
        is_smd = any(k in fp for k in ("SOT-23", "QFN", "SOT-223"))
        attr = "smd" if is_smd else "through_hole"
        lines.append(
            f'  (footprint "{fp}" (layer "F.Cu") (at {_fmt(cx)} {_fmt(cy)} {rot}) (attr {attr})'
        )
        body_w, body_h = geom.get("body", (5.0, 2.5))
        lines.append(f'    (property "Reference" "{ref}" (at 0 {_fmt(-body_h / 2 - 1.2)}) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))')
        lines.append(f'    (property "Value" "{ref}" (at 0 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))')
        for i, (px, py, pw, ph) in enumerate(pads, start=1):
            node = str((comp.get("nodes") or [""] * i)[i - 1]) if i <= len(comp.get("nodes") or []) else ""
            net_no = net_index.get(node, 0)
            net_sexpr = f' (net {net_no} "{node}")' if net_no else ""
            # rotate pad position with the footprint (0/90/180/270)
            rr = rot % 360
            if rr == 90:
                px, py = -py, px
            elif rr == 180:
                px, py = -px, -py
            elif rr == 270:
                px, py = py, -px
            # SMD pads are RECT: a "circle" pad takes max(w,h) as its
            # diameter, which once inflated a 0.28x0.6 QFN pad into a 0.6
            # circle that overlapped its pitch-0.5 neighbour.
            shape = "rect" if is_smd else ("rect" if i == 1 else "circle")
            # NO size clamping: fine-pitch pads (QFN 0.28mm) must stay small,
            # clamping them to 0.5 once left 0.0mm between neighbours.
            size = f"{_fmt(pw)} {_fmt(ph)}"
            if is_smd:
                pad_sexpr = (
                    f'    (pad "{i}" smd {shape} (at {_fmt(px)} {_fmt(py)}) (size {size})'
                    f' (layers "F.Cu" "F.Paste" "F.Mask"){net_sexpr})'
                )
            else:
                drill = rules["via_drill_mm"]
                pad_sexpr = (
                    f'    (pad "{i}" thru_hole {shape}'
                    f' (at {_fmt(px)} {_fmt(py)}) (size {size}) (drill {drill})'
                    f' (layers "*.Cu" "*.Mask"){net_sexpr})'
                )
            lines.append(pad_sexpr)
        lines.append("  )")

    lines.append(")")
    content = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return out_path


# KiCad-python scripts run by this module (kept as strings so the KiCad
# interpreter needs no repo access or venv — only its bundled pcbnew).

_DSN_EXPORT_SCRIPT = r"""
import sys, pcbnew
board = pcbnew.LoadBoard(sys.argv[1])
pcbnew.ExportSpecctraDSN(board, sys.argv[2])
print("dsn ok")
"""

_SES_IMPORT_SCRIPT = r"""
import sys, pcbnew
board = pcbnew.LoadBoard(sys.argv[1])
ok = pcbnew.ImportSpecctraSES(board, sys.argv[2])
pcbnew.SaveBoard(sys.argv[1], board)
print("ses import:", ok)
"""


def _run_kicad_python(script: str, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tf:
        tf.write(script)
        script_path = tf.name
    try:
        return subprocess.run(
            [KICAD_PYTHON, script_path, *args],
            capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace",
        )
    finally:
        os.unlink(script_path)


def route_board(pcb_path: str, timeout_s: int = 600) -> Dict[str, Any]:
    """Route a .kicad_pcb with Freerouting (DSN out -> route -> SES in)."""
    if not os.path.exists(FREEROUTING_JAR):
        return {"status": "unavailable", "detail": f"freerouting.jar not found at {FREEROUTING_JAR}"}
    workdir = os.path.dirname(pcb_path)
    dsn = os.path.join(workdir, "design.dsn")
    ses = os.path.join(workdir, "design.ses")

    exp = _run_kicad_python(_DSN_EXPORT_SCRIPT, pcb_path, dsn)
    if exp.returncode != 0 or not os.path.exists(dsn):
        return {"status": "failed", "stage": "dsn_export", "detail": (exp.stderr or exp.stdout)[-400:]}

    env = dict(os.environ)
    proc = subprocess.run(
        ["java", "-jar", FREEROUTING_JAR, "-de", dsn, "-do", ses, "-mp", "4", "-mt", str(max(timeout_s - 60, 60))],
        capture_output=True, text=True, timeout=timeout_s, env=env,
        encoding="utf-8", errors="replace",
    )
    if not os.path.exists(ses):
        return {"status": "failed", "stage": "routing", "detail": (proc.stdout or "")[-400:] + (proc.stderr or "")[-200:]}

    imp = _run_kicad_python(_SES_IMPORT_SCRIPT, pcb_path, ses)
    if imp.returncode != 0:
        return {"status": "failed", "stage": "ses_import", "detail": (imp.stderr or imp.stdout)[-400:]}
    return {"status": "success", "log_tail": (proc.stdout or "")[-300:]}


def run_drc(pcb_path: str, out_dir: str) -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    report = os.path.join(out_dir, "drc.json")
    proc = subprocess.run(
        [KICAD_CLI, "pcb", "drc", pcb_path, "--output", report, "--format", "json", "--severity-all", "--exit-code-violations"],
        capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace",
    )
    # kicad-cli exits non-zero when violations exist (--exit-code-violations);
    # the JSON report is what matters.
    result: Dict[str, Any] = {"exit_code": proc.returncode, "report_path": report if os.path.exists(report) else None}
    if os.path.exists(report):
        try:
            import json as _json
            with open(report, encoding="utf-8") as f:
                data = _json.load(f)
            violations = data.get("violations") or data.get("drc violations") or []
            unconnected = data.get("unconnected_items") or []
            # lib_footprint_* compares our self-contained inline footprints
            # against KiCad's library copies - informational, not a board defect.
            real = [v for v in violations if not str(v.get("type", "")).startswith("lib_footprint")]
            result["violations"] = len(real)
            result["library_noise"] = len(violations) - len(real)
            result["unconnected"] = len(unconnected)
            result["types"] = sorted({str(v.get("type")) for v in real})[:10]
        except Exception as exc:  # noqa: BLE001
            result["parse_error"] = str(exc)[:200]
    return result


def export_manufacturing_files(pcb_path: str, out_dir: str) -> Dict[str, Any]:
    """Gerbers + drills + positions, zipped for the board house."""
    os.makedirs(out_dir, exist_ok=True)
    gerber_dir = os.path.join(out_dir, "gerbers")
    os.makedirs(gerber_dir, exist_ok=True)
    steps = {
        "gerbers": [KICAD_CLI, "pcb", "export", "gerbers", "-o", gerber_dir + os.sep, pcb_path],
        "drill": [KICAD_CLI, "pcb", "export", "drill", "-o", gerber_dir + os.sep, pcb_path],
        "pos": [KICAD_CLI, "pcb", "export", "pos", "--side", "both", "-o", os.path.join(out_dir, "positions.pos"), pcb_path],
        "svg": [KICAD_CLI, "pcb", "export", "svg", "-o", os.path.join(out_dir, "pcb_routed.svg"), "--layers", "F.Cu,B.Cu,Edge.Cuts,F.SilkS", "--exclude-drawing-sheet", pcb_path],
        "render": [KICAD_CLI, "pcb", "render", "-o", os.path.join(out_dir, "pcb_3d.png"), "--width", "1600", "--height", "1200", "--side", "top", pcb_path],
    }
    results = {}
    for name, cmd in steps.items():
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace")
        results[name] = proc.returncode
    # zip gerbers
    zip_path = os.path.join(out_dir, "gerbers.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in sorted(os.listdir(gerber_dir)):
            zf.write(os.path.join(gerber_dir, fname), fname)
    results["zip"] = zip_path
    results["file_count"] = len(os.listdir(gerber_dir))
    return results


def crop_svg_viewbox(svg: str, pad: float = 2.0) -> str:
    """Crop an exported KiCad SVG (full A4 page) down to board content.

    Uses svg_bbox.content_bbox, which honors the transform stack, so the
    viewBox is rewritten in the same user-coordinate space the renderer uses.
    Attribute rewriting uses FUNCTION replacements - a replacement STRING
    like "\1" once mangled the <svg tag into a control character.
    """
    if not svg:
        return svg
    import re as _re
    from svg_bbox import content_bbox as _bbox

    box = _bbox(svg)
    if box is None:
        return svg
    min_x, min_y, max_x, max_y = box
    w, h = (max_x - min_x) + 2 * pad, (max_y - min_y) + 2 * pad
    min_x -= pad
    min_y -= pad
    vb = f'{min_x:.4f} {min_y:.4f} {w:.4f} {h:.4f}'

    out = _re.sub(
        r'(<svg[^>]*?)\sviewBox="[^"]*"',
        lambda m: m.group(1) + f' viewBox="{vb}"',
        svg, count=1,
    )
    out = _re.sub(
        r'(<svg[^>]*?)\swidth="[^"]*"',
        lambda m: m.group(1) + f' width="{w:.4f}mm"',
        out, count=1,
    )
    out = _re.sub(
        r'(<svg[^>]*?)\sheight="[^"]*"',
        lambda m: m.group(1) + f' height="{h:.4f}mm"',
        out, count=1,
    )
    return out
