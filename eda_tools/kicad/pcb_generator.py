"""
KiCad integration for PCB layout generation.

Produces a preview-grade 2-layer board: grid placement with per-footprint
body sizes, netlist-driven Manhattan tracks and an SVG visualization that
actually draws copper, pads, silkscreen and mounting holes. The output is
a visualization only - real manufacturing needs KiCad DRC (and a router).
"""
import logging
import math
import re
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Subcircuit instances whose model names a chip (NE555, LM393, ...) are ICs
# on the board, not "modules"; anything else behind an X stays a module.
_IC_MODEL_RE = re.compile(
    r"^(?:[a-z]{0,3}555|555|lm\d|tl\d|ne\d|ua7|adc\d|dac\d|atmega|attiny"
    r"|pic1|stm32|esp32|cd40|max\d|ds\d|74)",
    re.I,
)

# Placement / rendering geometry per footprint: body (w, h) in mm and the
# THT pad pattern. pitch is pin-to-pin spacing, row the dual-in-line row
# spacing. Defaults apply to anything unmapped (modules, unknown parts).
_FOOTPRINT_GEOM: Dict[str, Dict[str, Any]] = {
    "R_Axial_DIN0207": dict(body=(10.16, 2.5), pads=2, pitch=10.16, pad=(1.8, 2.2)),
    "C_Disc_D5.0mm": dict(body=(5.0, 2.5), pads=2, pitch=5.0, pad=(1.6, 2.0)),
    "L_Axial_L12.0mm": dict(body=(15.0, 4.5), pads=2, pitch=15.0, pad=(2.0, 2.6)),
    "D_DO-35": dict(body=(7.62, 2.2), pads=2, pitch=7.62, pad=(1.6, 2.0)),
    "TO-92": dict(body=(4.0, 4.6), pads=3, pitch=2.54, pad=(1.5, 1.6)),
    "TestPoint": dict(body=(2.6, 2.6), pads=1, pitch=0.0, pad=(2.0, 2.0)),
    "DIP-8": dict(body=(9.6, 6.7), pads=8, pitch=2.54, row=7.62, pad=(1.6, 1.8), dip=True),
    "DIP-14": dict(body=(19.4, 6.7), pads=14, pitch=2.54, row=7.62, pad=(1.6, 1.8), dip=True),
    "DIP-16": dict(body=(21.9, 6.7), pads=16, pitch=2.54, row=7.62, pad=(1.6, 1.8), dip=True),
    "DIP-20": dict(body=(26.9, 6.7), pads=20, pitch=2.54, row=7.62, pad=(1.6, 1.8), dip=True),
}
_DEFAULT_GEOM = dict(body=(5.0, 2.5), pads=2, pitch=5.0, pad=(1.6, 2.0))

# Rails are drawn as full-width buses, not signal chains.
_GND_RE = re.compile(r"^(0|gnd|vss|agnd|dgnd)$", re.I)
_VCC_RE = re.compile(r"^(vcc|vdd|vbat|\+?(\d+([.]\d+)?)v|avcc|3v3|5v|9v|12v)$", re.I)


def _geom_for(footprint: str) -> Dict[str, Any]:
    """Footprint library name -> geometry dict (longest token match)."""
    for key, geom in _FOOTPRINT_GEOM.items():
        if key in footprint:
            return geom
    return _DEFAULT_GEOM


def _pads_local(geom: Dict[str, Any]) -> List[Tuple[float, float, float, float]]:
    """Pad rectangles in footprint-local coords: (x, y, w, h), body-centered."""
    pads = []
    n = int(geom["pads"])
    pitch = float(geom["pitch"])
    pw, ph = geom["pad"]
    if geom.get("dip"):
        row = float(geom["row"])
        per_side = n // 2
        span = (per_side - 1) * pitch
        for i in range(per_side):
            pads.append((-row / 2, -span / 2 + i * pitch, pw, ph))
            pads.append((row / 2, span / 2 - i * pitch, pw, ph))
    else:
        span = (n - 1) * pitch
        for i in range(n):
            pads.append((-span / 2 + i * pitch, 0.0, pw, ph))
    return pads


def _rotate(x: float, y: float, rotation: int) -> Tuple[float, float]:
    r = int(rotation) % 360
    if r == 90:
        return -y, x
    if r == 180:
        return -x, -y
    if r == 270:
        return y, -x
    return x, y


class PCBGenerator:
    """Generate PCB layouts using KiCad"""

    def __init__(self):
        """Initialize PCB generator"""
        logger.info("Initializing PCB generator")

    def generate_pcb_layout(self, netlist: str) -> Dict[str, Any]:
        """
        Generate PCB layout from netlist

        Args:
            netlist: SPICE netlist

        Returns:
            PCB layout data
        """
        logger.info("Generating PCB layout")

        try:
            components = self._parse_components_from_netlist(netlist)
            layout_data = self._create_simple_layout(components)

            board_outline = layout_data.get("board_outline", {})
            board_width = board_outline.get("width", 100)
            board_height = board_outline.get("height", 80)

            logger.info("✓ PCB layout generated")
            return {
                "status": "success",
                "components": components,
                "layout": layout_data,
                "layers": 2,  # Double-sided PCB
                "dimensions": {
                    "width": board_width,
                    "height": board_height
                }
            }

        except Exception as e:
            logger.error(f"Error generating PCB: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def _parse_components_from_netlist(self, netlist: str) -> List[Dict[str, Any]]:
        """
        Parse components from netlist, keeping each element's nodes so
        tracks can follow real connectivity instead of proximity guesses.
        """
        components = []
        lines = netlist.strip().split('\n')

        subckt_depth = 0
        for line in lines:
            line = line.strip()
            if not line or line.startswith('*') or line.startswith('+'):
                continue
            low = line.lower()
            if low.startswith('.subckt'):
                subckt_depth += 1
                continue
            if subckt_depth:
                # behavioural macro-model internals (B/S/RDIV helpers inside
                # a .subckt) are simulation scaffolding, not board parts
                if low.startswith('.ends'):
                    subckt_depth -= 1
                continue
            if line.startswith('.'):
                continue

            parts = line.split()
            if len(parts) >= 3:
                comp_name = parts[0]
                nodes = parts[1:-1]
                value = parts[-1]

                comp_type = comp_name[0].upper()
                if comp_type == "X" and _IC_MODEL_RE.match(value):
                    comp_type = "U"
                # mirror the BOM's value-based rule so LED1 (L prefix, LED
                # value) doesn't land on an inductor footprint
                if comp_type == "L" and "led" in value.lower():
                    comp_type = "D"

                component = {
                    "name": comp_name,
                    "type": comp_type,
                    "value": value,
                    "footprint": self._get_footprint(comp_type, value, len(nodes)),
                    "nodes": nodes,
                    "position": {"x": 0, "y": 0}  # Will be calculated
                }
                components.append(component)

        return components

    def _get_footprint(self, comp_type: str, value: str, pins: int = 0) -> str:
        """
        Get KiCad footprint for component

        Args:
            comp_type: Component type
            value: Component value
            pins: Pin count of the parsed element (selects DIP size for ICs)

        Returns:
            Footprint name
        """
        if comp_type == "U":
            if pins and pins > 8:
                if pins <= 14:
                    return "Package_DIP:DIP-14_W7.62mm"
                if pins <= 16:
                    return "Package_DIP:DIP-16_W7.62mm"
                if pins <= 20:
                    return "Package_DIP:DIP-20_W7.62mm"
            return "Package_DIP:DIP-8_W7.62mm"
        footprints = {
            "R": "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal",
            "C": "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm",
            "L": "Inductor_THT:L_Axial_L12.0mm_D4.5mm_P15.00mm",
            "D": "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal",
            "Q": "Package_TO_SOT_THT:TO-92",
            "V": "TestPoint:TestPoint_THT_Pad_D2.0mm_Drill1.0mm"
        }
        return footprints.get(comp_type, "Unknown")

    def _create_simple_layout(self, components: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create PCB layout: size-aware grid placement + netlist-driven tracks

        Args:
            components: List of components

        Returns:
            Layout data
        """
        logger.info("Using grid PCB placement algorithm")

        sorted_components = self._sort_components_by_priority(components)
        placed_components = self._grid_placement(sorted_components)

        board_width, board_height = self._calculate_board_dimensions(placed_components)
        board_outline = {
            "type": "rectangle",
            "width": board_width,
            "height": board_height
        }

        tracks = self._generate_intelligent_tracks(placed_components)

        # Mounting holes only fit a reasonably sized board
        holes = []
        if board_width >= 45 and board_height >= 35:
            inset = 5.0
            for hx, hy in (
                (inset, inset),
                (board_width - inset, inset),
                (inset, board_height - inset),
                (board_width - inset, board_height - inset),
            ):
                holes.append({"x": hx, "y": hy, "diameter": 3.2})

        return {
            "components": placed_components,
            "tracks": tracks,
            "board_outline": board_outline,
            "mounting_holes": holes
        }

    def _sort_components_by_priority(self, components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort components by placement priority: ICs first so they anchor
        the grid, then semiconductors, passives last.
        """
        priority = {
            "U": 1,  # ICs first
            "Q": 2,  # Transistors
            "D": 3,  # Diodes (polarized)
            "C": 4,  # Capacitors
            "L": 5,  # Inductors
            "R": 6   # Resistors last
        }

        def get_priority(comp):
            comp_type = comp.get("type", "R")
            return priority.get(comp_type, 99)

        return sorted(components, key=get_priority)

    def _grid_placement(self, components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Place components on a size-aware grid that fills the board.

        Each component occupies a cell of footprint body + clearance; the
        column count is chosen so the board aspect stays near 1.3. This
        replaces the old concentric-circle placement that clumped every
        part around the board center.
        """
        if not components:
            return []

        clearance = 7.0  # mm around each body for routing room
        cells = []
        for comp in components:
            bw, bh = _geom_for(comp.get("footprint", "")).get("body", (5.0, 2.5))
            cells.append((max(bw + clearance, 5.0), max(bh + clearance, 5.0)))

        n = len(components)
        best_plan = None
        for cols in range(1, n + 1):
            rows = math.ceil(n / cols)
            col_w = [0.0] * cols
            row_h = [0.0] * rows
            for i, (cw, ch) in enumerate(cells):
                c, r = i % cols, i // cols
                col_w[c] = max(col_w[c], cw)
                row_h[r] = max(row_h[r], ch)
            width, height = sum(col_w), sum(row_h)
            aspect = width / max(height, 1e-6)
            score = abs(math.log(aspect / 1.3))
            if best_plan is None or score < best_plan[0]:
                best_plan = (score, cols, col_w, row_h)

        _, cols, col_w, row_h = best_plan
        margin = 10.0  # mm board edge margin

        placed = []
        for i, comp in enumerate(components):
            c, r = i % cols, i // cols
            x = margin + sum(col_w[:c]) + col_w[c] / 2
            y = margin + sum(row_h[:r]) + row_h[r] / 2
            placed.append({
                "name": comp["name"],
                "footprint": comp["footprint"],
                "nodes": comp.get("nodes", []),
                "position": {"x": round(x, 2), "y": round(y, 2)},
                "rotation": 0,
                "layer": "F.Cu"
            })
        return placed

    def _calculate_board_dimensions(self, components: List[Dict[str, Any]]) -> tuple:
        """
        Board size from placed component bounds plus edge margin.
        """
        if not components:
            return 60, 40

        max_x = max_y = 0.0
        for comp in components:
            bw, bh = _geom_for(comp.get("footprint", "")).get("body", (5.0, 2.5))
            max_x = max(max_x, comp["position"]["x"] + bw / 2)
            max_y = max(max_y, comp["position"]["y"] + bh / 2)

        margin = 10.0
        return round(max_x + margin), round(max_y + margin)

    def _generate_intelligent_tracks(self, components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Tracks follow the netlist: shared-node components chain together,
        rail nodes drop to full-width VCC (top) / GND (bottom) buses.
        """
        nets: Dict[str, List[Dict[str, Any]]] = {}
        for comp in components:
            for node in comp.get("nodes", []):
                nets.setdefault(node, []).append(comp)

        board_w = max(c["position"]["x"] for c in components) + 10 \
            if components else 60
        board_h = max(c["position"]["y"] for c in components) + 10 \
            if components else 40

        tracks: List[Dict[str, Any]] = []

        def bus(y: float, net: str) -> None:
            # 8mm inset clears the corner mounting holes (5mm inset, 1.6mm radius)
            tracks.append({
                "start": {"x": 8.0, "y": y},
                "end": {"x": board_w - 8.0, "y": y},
                "mid_point": None,
                "width": 1.0,
                "layer": "F.Cu",
                "net": net,
                "type": "bus",
            })

        has_vcc = any(_VCC_RE.match(n) for n in nets if len(nets[n]) >= 2)
        has_gnd = any(_GND_RE.match(n) for n in nets if len(nets[n]) >= 2)
        vcc_y, gnd_y = 5.0, board_h - 5.0
        if has_vcc:
            bus(vcc_y, "VCC")
        if has_gnd:
            bus(gnd_y, "GND")

        for node, members in nets.items():
            if len(members) < 2:
                continue
            if _GND_RE.match(node):
                target_y = gnd_y
            elif _VCC_RE.match(node):
                target_y = vcc_y
            else:
                # signal net: chain members sorted along x to keep the
                # Manhattan path short
                ordered = sorted(members, key=lambda m: m["position"]["x"])
                for a, b in zip(ordered, ordered[1:]):
                    tracks.append(self._create_manhattan_track(
                        a["position"], b["position"], node
                    ))
                continue

            # rail: drop each member straight down/up to its bus
            for m in members:
                p = m["position"]
                if abs(p["y"] - target_y) < 1.0:
                    continue
                tracks.append({
                    "start": {"x": p["x"], "y": p["y"]},
                    "end": {"x": p["x"], "y": target_y},
                    "mid_point": None,
                    "width": 0.4,
                    "layer": "F.Cu",
                    "net": "VCC" if target_y == vcc_y else "GND",
                    "type": "power",
                })

        logger.info(f"Generated {len(tracks)} tracks")
        return tracks

    def _create_manhattan_track(
        self, pos1: Dict, pos2: Dict, net: str
    ) -> Dict[str, Any]:
        """
        Create Manhattan routing track (horizontal + vertical segments)
        """
        dx = abs(pos2["x"] - pos1["x"])
        dy = abs(pos2["y"] - pos1["y"])

        # Route along the dominant axis first for a natural L shape
        mid_x = pos1["x"] if dx < dy else pos2["x"]
        mid_y = pos2["y"] if dx < dy else pos1["y"]

        return {
            "start": {"x": pos1["x"], "y": pos1["y"]},
            "end": {"x": pos2["x"], "y": pos2["y"]},
            "mid_point": {"x": mid_x, "y": mid_y},
            "width": 0.5,  # mm
            "layer": "F.Cu",
            "net": net,
            "length": round(dx + dy, 2),
            "type": "signal"
        }

    def generate_gerber_files(self, layout: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate Gerber file data

        Args:
            layout: PCB layout data

        Returns:
            Dictionary of Gerber file contents
        """
        # For MVP, generate placeholder Gerber data
        # In production, use KiCad to generate actual Gerber files

        logger.info("Generating Gerber files")

        return {
            "F_Cu": "Front copper layer Gerber data",
            "B_Cu": "Back copper layer Gerber data",
            "F_SilkS": "Front silkscreen Gerber data",
            "B_SilkS": "Back silkscreen Gerber data",
            "F_Mask": "Front soldermask Gerber data",
            "B_Mask": "Back soldermask Gerber data",
            "Edge_Cuts": "Board outline Gerber data"
        }

    def generate_pcb_visualization(self, layout: Dict[str, Any]) -> str:
        """
        Render the PCB as a top-view SVG: soldermask board, copper tracks,
        gold THT pads with drills, component bodies/courtyards, silkscreen
        references and mounting holes. Every element comes from the layout
        data - nothing is faked here.
        """
        S = 8  # px per mm
        dims = layout.get("dimensions", {})
        width = float(dims.get("width", 100))
        height = float(dims.get("height", 80))
        W, H = width * S, height * S

        p: List[str] = []
        p.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" '
            f'height="{H:.0f}" viewBox="0 0 {W:.0f} {H:.0f}" '
            f'font-family="Consolas, Menlo, monospace">'
        )

        # substrate
        p.append(
            f'<rect x="0" y="0" width="{W:.0f}" height="{H:.0f}" rx="{2*S}" '
            f'fill="#0e5a2c" stroke="#073d1e" stroke-width="{0.4*S}"/>'
        )
        # subtle copper pour hint inside the edge
        p.append(
            f'<rect x="{0.8*S}" y="{0.8*S}" width="{W-1.6*S:.2f}" '
            f'height="{H-1.6*S:.2f}" rx="{1.4*S}" fill="#126633"/>'
        )

        # tracks (under the parts)
        for tr in layout.get("layout", {}).get("tracks", []):
            pts = [tr["start"], tr.get("mid_point"), tr["end"]]
            pts = [(pt["x"] * S, pt["y"] * S) for pt in pts if pt]
            if len(pts) < 2:
                continue
            kind = tr.get("type", "signal")
            color = "#d9a441" if kind != "power" else "#c89032"
            w = max(float(tr.get("width", 0.5)), 0.25) * S
            poly = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
            p.append(
                f'<polyline points="{poly}" fill="none" stroke="{color}" '
                f'stroke-width="{w:.2f}" stroke-linecap="round" '
                f'stroke-linejoin="round"/>'
            )

        # components: courtyard + body + pads + silkscreen ref
        for comp in layout.get("layout", {}).get("components", []):
            pos = comp.get("position", {})
            rot = int(comp.get("rotation", 0))
            geom = _geom_for(comp.get("footprint", ""))
            bw, bh = geom["body"]
            cx, cy = pos.get("x", 0) * S, pos.get("y", 0) * S
            bwpx, bhpx = bw * S, bh * S

            # courtyard / silkscreen outline
            p.append(
                f'<rect x="{cx-bwpx/2-1.0*S:.2f}" y="{cy-bhpx/2-1.0*S:.2f}" '
                f'width="{bwpx+2.0*S:.2f}" height="{bhpx+2.0*S:.2f}" '
                f'fill="none" stroke="#e8f0e8" stroke-width="{0.15*S:.2f}" '
                f'stroke-dasharray="none" opacity="0.9"/>'
            )

            # body
            if geom.get("dip"):
                p.append(
                    f'<rect x="{cx-bwpx/2:.2f}" y="{cy-bhpx/2:.2f}" '
                    f'width="{bwpx:.2f}" height="{bhpx:.2f}" rx="{0.4*S}" '
                    f'fill="#22221f" stroke="#111" stroke-width="{0.1*S:.2f}"/>'
                )
                # pin-1 notch: half circle biting into the left edge
                r_n = bhpx / 4
                p.append(
                    f'<path d="M {cx-bwpx/2:.2f},{cy-r_n:.2f} '
                    f'a {r_n:.2f},{r_n:.2f} 0 0 0 0,{2*r_n:.2f} Z" '
                    f'fill="#0e5a2c"/>'
                )
                p.append(
                    f'<circle cx="{cx-bwpx/2+1.0*S:.2f}" cy="{cy-bhpx/2+1.2*S:.2f}" '
                    f'r="{0.3*S:.2f}" fill="#e8f0e8"/>'
                )
            else:
                p.append(
                    f'<rect x="{cx-bwpx/2:.2f}" y="{cy-bhpx/2:.2f}" '
                    f'width="{bwpx:.2f}" height="{bhpx:.2f}" rx="{0.3*S}" '
                    f'fill="#2e2c28" stroke="#1b1a17" stroke-width="{0.1*S:.2f}"/>'
                )

            # pads with drill holes
            for lx, ly, pw, ph in _pads_local(geom):
                rx_, ry_ = _rotate(lx, ly, rot)
                px_, py_ = cx + rx_ * S, cy + ry_ * S
                pwpx, phpx = pw * S, ph * S
                # pads rotate with the footprint
                if rot % 180:
                    pwpx, phpx = phpx, pwpx
                p.append(
                    f'<rect x="{px_-pwpx/2:.2f}" y="{py_-phpx/2:.2f}" '
                    f'width="{pwpx:.2f}" height="{phpx:.2f}" rx="{pwpx/4:.2f}" '
                    f'fill="#e6c265" stroke="#8a6d1f" stroke-width="{0.08*S:.2f}"/>'
                )
                p.append(
                    f'<circle cx="{px_:.2f}" cy="{py_:.2f}" r="{0.45*S:.2f}" fill="#14120e"/>'
                )

            # reference designator
            ref = str(comp.get("name", "?"))
            p.append(
                f'<text x="{cx-bwpx/2:.2f}" y="{cy-bhpx/2-1.4*S:.2f}" '
                f'font-size="{2.2*S}" fill="#e8f0e8" font-weight="bold">{ref}</text>'
            )

        # mounting holes: gold ring + dark bore
        for hole in layout.get("layout", {}).get("mounting_holes", []):
            hx, hy = hole["x"] * S, hole["y"] * S
            r_out = hole.get("diameter", 3.2) / 2 * S
            p.append(
                f'<circle cx="{hx:.2f}" cy="{hy:.2f}" r="{r_out:.2f}" '
                f'fill="#e6c265" stroke="#8a6d1f" stroke-width="{0.1*S:.2f}"/>'
            )
            p.append(
                f'<circle cx="{hx:.2f}" cy="{hy:.2f}" r="{r_out*0.55:.2f}" fill="#0c2247"/>'
            )

        p.append('</svg>')
        return '\n'.join(p)


def generate_pcb(netlist: str) -> Dict[str, Any]:
    """
    Generate PCB layout from netlist

    Args:
        netlist: SPICE netlist

    Returns:
        PCB layout data
    """
    generator = PCBGenerator()
    layout = generator.generate_pcb_layout(netlist)

    if layout.get("status") == "success":
        # Generate visualization
        pcb_svg = generator.generate_pcb_visualization(layout)
        layout["visualization"] = pcb_svg
    return layout
