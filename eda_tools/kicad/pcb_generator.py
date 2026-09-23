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
from typing import Dict, List, Any, Optional, Set, Tuple

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
    # Registry real parts (footprint strings come from _REAL_PARTS)
    "QFN-32": dict(body=(4.0, 4.0), pads=32, pitch=0.5, pad=(0.45, 0.28), quad=True),
    "SOT-223": dict(body=(6.5, 3.5), pads=4, pitch=2.3, pad=(1.0, 1.7), sot223=True),
    "USB_C_Receptacle_HRO": dict(
        body=(8.94, 7.35), pads=16, pitch=1.0, row=5.5, pad=(0.8, 1.2), dualrow=True
    ),
}
_DEFAULT_GEOM = dict(body=(5.0, 2.5), pads=2, pitch=5.0, pad=(1.6, 2.0))

# Rails are drawn as full-width buses, not signal chains.
_GND_RE = re.compile(r"^(0|gnd|vss|agnd|dgnd)$", re.I)
_VCC_RE = re.compile(r"^(vcc|vdd|vbat|\+?(\d+([.]\d+)?)v|avcc|3v3|5v|9v|12v|vbus)$", re.I)


def _geom_for(footprint: str) -> Dict[str, Any]:
    """Footprint library name -> geometry dict (longest token match)."""
    m = re.search(r"PinHeader_1x(\d+)", footprint or "")
    if m:
        n = int(m.group(1))
        return dict(body=(2.54, (n - 1) * 2.54 + 2.0), pads=n, pitch=2.54, pad=(1.8, 1.8))
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
    elif geom.get("quad"):
        # QFN perimeter, KiCad numbering: left top->bottom (1..per), bottom
        # left->right (per+1..2per), right bottom->top (2per+1..3per), top
        # right->left (3per+1..n). Pad index k must be pin k+1 so the
        # per-pad net list maps straight onto these positions.
        per = n // 4
        span = (per - 1) * pitch
        off = span / 2
        e = float(geom["body"][0]) / 2 + 0.2
        for i in range(per):
            pads.append((-e, -off + i * pitch, ph, pw))      # left 1..per
        for i in range(per):
            pads.append((-off + i * pitch, e, pw, ph))        # bottom per+1..
        for i in range(per):
            pads.append((e, off - i * pitch, ph, pw))         # right 2per+1..
        for i in range(per):
            pads.append((off - i * pitch, -e, pw, ph))        # top 3per+1..
    elif geom.get("sot223"):
        # AMS1117 SOT-223: pad 1 = GND, pad 2 = VO (the big tab), pad 3 = VI.
        # Three leads on the bottom edge, tab on top; pad order must match the
        # registry's pin numbering so netlist pad k lands on physical pad k.
        bh = float(geom["body"][1])
        pads.append((-pitch, bh / 2 - 0.6, pw, ph))           # pin 1
        pads.append((0.0, -bh / 2 + 0.6, 3.2, ph))            # pin 2 = tab
        pads.append((pitch, bh / 2 - 0.6, pw, ph))            # pin 3
    elif geom.get("dualrow"):
        # USB-C receptacle: A-row pads first (A1..), then the B row — the
        # per-pad net list is ordered by natural pin sort, A* before B*.
        row = float(geom["row"])
        per_row = n // 2
        span = (per_row - 1) * pitch
        for i in range(per_row):
            pads.append((-row / 2, -span / 2 + i * pitch, pw, ph))   # A row
        for i in range(per_row):
            pads.append((row / 2, -span / 2 + i * pitch, pw, ph))    # B row
    else:
        span = (n - 1) * pitch
        for i in range(n):
            pads.append((-span / 2 + i * pitch, 0.0, pw, ph))
    return pads


def _body_rects(
    components: List[Dict[str, Any]], clearance: float = 0.0
) -> List[Tuple[str, float, float, float, float]]:
    """(name, x1, y1, x2, y2) keep-out rectangles around component bodies.

    Zero clearance by design: THT pads sit exactly on their body edge, and
    a vertical lane that merely touches body edges is a legal (and usual)
    escape route - only the interior counts as piercing."""
    rects = []
    for comp in components:
        bw, bh = _geom_for(comp.get("footprint", "")).get("body", (5.0, 2.5))
        cx, cy = comp["position"]["x"], comp["position"]["y"]
        rects.append(
            (str(comp.get("name", "?")),
             cx - bw / 2 - clearance, cy - bh / 2 - clearance,
             cx + bw / 2 + clearance, cy + bh / 2 + clearance)
        )
    return rects


def _channel_xs(
    bodies: List[Tuple[str, float, float, float, float]],
) -> List[float]:
    """Mid-lines of the horizontal gaps between component columns."""
    spans = sorted((bx1, bx2) for _n, bx1, _by1, bx2, _by2 in bodies)
    merged: List[List[float]] = []
    for x1, x2 in spans:
        if merged and x1 <= merged[-1][1] + 0.01:
            merged[-1][1] = max(merged[-1][1], x2)
        else:
            merged.append([x1, x2])
    xs: List[float] = []
    prev = 0.0
    for x1, x2 in merged:
        if x1 - prev > 1.0:
            xs.append(round((prev + x1) / 2, 2))
        prev = x2
    xs.append(round(prev + 3.0, 2))
    return xs


def _row_channels(
    bodies: List[Tuple[str, float, float, float, float]], board_h: float
) -> List[float]:
    """Mid-lines of the vertical gaps between component rows."""
    spans = sorted((by1, by2) for _n, _bx1, by1, _bx2, by2 in bodies)
    merged: List[List[float]] = []
    for y1, y2 in spans:
        if merged and y1 <= merged[-1][1] + 0.01:
            merged[-1][1] = max(merged[-1][1], y2)
        else:
            merged.append([y1, y2])
    chans: List[float] = []
    prev = 0.0
    for y1, y2 in merged:
        if y1 - prev > 1.0:
            chans.append(round((prev + y1) / 2, 2))
        prev = y2
    if board_h - prev > 1.0:
        chans.append(round((prev + board_h) / 2, 2))
    return chans


def _seg_hits_body(x1: float, y1: float, x2: float, y2: float, rect) -> bool:
    """Does an axis-aligned segment pass through the rectangle's interior?"""
    _n, bx1, by1, bx2, by2 = rect
    eps = 0.01
    if abs(y1 - y2) < eps:  # horizontal
        if not (by1 + eps < y1 < by2 - eps):
            return False
        return max(x1, x2) > bx1 + eps and min(x1, x2) < bx2 - eps
    if abs(x1 - x2) < eps:  # vertical
        if not (bx1 + eps < x1 < bx2 - eps):
            return False
        return max(y1, y2) > by1 + eps and min(y1, y2) < by2 - eps
    return False


def _segments_clear(
    segs: List[Tuple[float, float, float, float]],
    bodies: List[Tuple[str, float, float, float, float]],
    exclude: Tuple[str, ...],
) -> bool:
    return not any(
        _seg_hits_body(*seg, rect)
        for seg in segs
        for rect in bodies
        if rect[0] not in exclude
    )


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

    def generate_pcb_layout(
        self, netlist: str, circuit_ir: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate PCB layout from a netlist or, preferably, a CircuitIR.

        The SPICE netlist is a SIMULATION view: registry parts are replaced
        by engineering models (ideal sources / load current sources), so a
        board built from it would show V1/I1 instead of the real USB-C,
        LDO and MCU. When a CircuitIR is available it is the single source
        of truth for the physical view.

        Args:
            netlist: SPICE netlist (fallback when no CircuitIR exists)
            circuit_ir: CircuitIR with components + nets

        Returns:
            PCB layout data
        """
        logger.info("Generating PCB layout")

        try:
            if circuit_ir and circuit_ir.get("components"):
                components = _components_from_ir(circuit_ir)
            else:
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
        return _footprint_for(comp_type, value, pins)

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

        Track endpoints are the real pad centres (component position plus
        the footprint's local pad offset; netlist node order is pad order),
        not component centres - pads sit half a pitch away from them.
        """
        nets: Dict[str, List[Dict[str, Any]]] = {}
        pad_of: Dict[Tuple[str, str], Dict[str, float]] = {}
        for comp in components:
            geom = _geom_for(comp.get("footprint", ""))
            local_pads = _pads_local(geom)
            pos = comp.get("position", {"x": 0, "y": 0})
            rot = int(comp.get("rotation", 0))
            for k, node in enumerate(comp.get("nodes", [])):
                if k < len(local_pads):
                    lx, ly = _rotate(local_pads[k][0], local_pads[k][1], rot)
                    x, y = pos["x"] + lx, pos["y"] + ly
                else:
                    x, y = pos["x"], pos["y"]
                pad_of.setdefault((comp["name"], node), {"x": x, "y": y})
                nets.setdefault(node, []).append(comp)

        board_w = max(c["position"]["x"] for c in components) + 10 \
            if components else 60
        board_h = max(c["position"]["y"] for c in components) + 10 \
            if components else 40

        tracks: List[Dict[str, Any]] = []
        bodies = _body_rects(components)
        row_channels = _row_channels(bodies, board_h)

        def bus(y: float, net: str) -> None:
            # 8mm inset clears the corner mounting holes (5mm inset, 1.6mm radius)
            tracks.append({
                "start": {"x": 8.0, "y": y},
                "end": {"x": board_w - 8.0, "y": y},
                "mid_point": None,
                "l_points": [],
                "width": 1.0,
                "layer": "F.Cu",
                "net": net,
                "type": "bus",
            })

        # Each rail net gets its OWN bus: a board with both VBUS (5 V) and
        # 3V3 must never merge them onto one VCC bus - that is a visible
        # short. GND stays at the bottom; positive rails stack from the top.
        rail_names = sorted(
            {n for n in nets if len(nets[n]) >= 2 and _GND_RE.match(n)},
            key=str,
        ) + sorted(
            {n for n in nets if len(nets[n]) >= 2 and not _GND_RE.match(n) and _VCC_RE.match(n)},
            key=str,
        )
        gnd_y = board_h - 5.0
        rail_bus_y: Dict[str, float] = {}
        pos_i = 0
        for rail in rail_names:
            if _GND_RE.match(rail):
                rail_bus_y[rail] = gnd_y
            else:
                rail_bus_y[rail] = 5.0 + pos_i * 3.0
                pos_i += 1
        for rail, y in rail_bus_y.items():
            bus(y, rail)

        for node, members in nets.items():
            if len(members) < 2:
                continue
            if node in rail_bus_y:
                target_y = rail_bus_y[node]
                bus_net = node
            else:
                # signal net: chain members sorted along x to keep the
                # Manhattan path short, steering clear of other components'
                # bodies (tracks over parts read as shorts even when
                # electrically fine)
                ordered = sorted(members, key=lambda m: m["position"]["x"])
                for a, b in zip(ordered, ordered[1:]):
                    tracks.append(self._create_manhattan_track(
                        pad_of.get((a["name"], node), a["position"]),
                        pad_of.get((b["name"], node), b["position"]),
                        node,
                        bodies=bodies,
                        exclude=(a["name"], b["name"]),
                        row_channels=row_channels,
                        centers={c["name"]: (c["position"]["x"], c["position"]["y"]) for c in components},
                        col_channels=_channel_xs(bodies),
                    ))
                continue

            # rail: drop each member to its bus - straight when the lane is
            # clear, otherwise dogleg out to a clear channel first
            for m in members:
                p = pad_of.get((m["name"], node), m["position"])
                if abs(p["y"] - target_y) < 1.0:
                    continue
                drop = {
                    "start": {"x": p["x"], "y": p["y"]},
                    "end": {"x": p["x"], "y": target_y},
                    "mid_point": None,
                    "l_points": [],
                    "width": 0.4,
                    "layer": "F.Cu",
                    "net": bus_net,
                    "type": "power",
                }
                if not _segments_clear(
                    [(p["x"], p["y"], p["x"], target_y)], bodies, (m["name"],)
                ):
                    for ch_x in sorted(_channel_xs(bodies), key=lambda c: abs(c - p["x"])):
                        segs = [
                            (p["x"], p["y"], ch_x, p["y"]),
                            (ch_x, p["y"], ch_x, target_y),
                        ]
                        if _segments_clear(segs, bodies, (m["name"],)):
                            drop = {
                                "start": {"x": p["x"], "y": p["y"]},
                                "end": {"x": ch_x, "y": target_y},
                                "mid_point": None,
                                "l_points": [{"x": ch_x, "y": p["y"]}],
                                "width": 0.4,
                                "layer": "F.Cu",
                                "net": bus_net,
                                "type": "power",
                            }
                            break
                tracks.append(drop)

        logger.info(f"Generated {len(tracks)} tracks")
        return tracks

    def _create_manhattan_track(
        self, pos1: Dict, pos2: Dict, net: str,
        bodies: Optional[List[Tuple[str, float, float, float, float]]] = None,
        exclude: Tuple[str, ...] = (),
        row_channels: Optional[List[float]] = None,
        centers: Optional[Dict[str, Tuple[float, float]]] = None,
        col_channels: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """
        Create a Manhattan track between two pads.

        The preferred shape is the highway: each pad exits AWAY from its
        own component into a column channel, the run crosses on a row
        channel, and the far pad is entered from its own outward channel -
        nothing ever crosses a component body. L and simple Z shapes are
        fallbacks; the first fully clear candidate wins.
        """
        x1, y1 = pos1["x"], pos1["y"]
        x2, y2 = pos2["x"], pos2["y"]

        def segs_of(points: List[Tuple[float, float]]) -> List[Tuple[float, float, float, float]]:
            return [(a[0], a[1], b[0], b[1]) for a, b in zip(points, points[1:])]

        def length_of(points: List[Tuple[float, float]]) -> float:
            return round(sum(
                abs(b[0] - a[0]) + abs(b[1] - a[1])
                for a, b in zip(points, points[1:])
            ), 2)

        def clear(points: List[Tuple[float, float]]) -> bool:
            if bodies is None:
                return True
            return _segments_clear(segs_of(points), bodies, ())

        candidates: List[List[Tuple[float, float]]] = []

        # highway: outward exits into column channels, cross on a row channel
        if bodies and row_channels and col_channels and centers:
            ca = centers.get(exclude[0]) if len(exclude) > 0 else None
            cb = centers.get(exclude[1]) if len(exclude) > 1 else None

            def outward(ch_x: float, pad_x: float, center) -> bool:
                if center is None:
                    return True
                return (ch_x - pad_x) * (pad_x - center[0]) > 0

            ga = [c for c in col_channels if outward(c, x1, ca)]
            gb = [c for c in col_channels if outward(c, x2, cb)]
            for a_ch in sorted(ga or col_channels, key=lambda c: abs(c - x1))[:2]:
                for b_ch in sorted(gb or col_channels, key=lambda c: abs(c - x2))[:2]:
                    for ch_y in sorted(
                        row_channels, key=lambda c: abs(c - (y1 + y2) / 2)
                    )[:2]:
                        candidates.append([
                            (x1, y1), (a_ch, y1), (a_ch, ch_y),
                            (b_ch, ch_y), (b_ch, y2), (x2, y2),
                        ])

        candidates.extend([
            [(x1, y1), (x2, y1), (x2, y2)],
            [(x1, y1), (x1, y2), (x2, y2)],
        ])
        # dominant-axis L first for a natural shape
        if abs(y2 - y1) > abs(x2 - x1):
            candidates[2], candidates[3] = candidates[3], candidates[2]
        # Z detours through the row gaps (nearest channel first)
        if bodies and row_channels:
            for ch_y in sorted(
                row_channels, key=lambda c: abs(c - (y1 + y2) / 2)
            ):
                candidates.append([(x1, y1), (x1, ch_y), (x2, ch_y), (x2, y2)])

        chosen = next((c for c in candidates if clear(c)), candidates[0])
        mids = [{"x": px, "y": py} for px, py in chosen[1:-1]]
        return {
            "start": {"x": x1, "y": y1},
            "end": {"x": x2, "y": y2},
            "mid_point": mids[0] if len(mids) == 1 else None,
            "l_points": mids,
            "width": 0.5,  # mm
            "layer": "F.Cu",
            "net": net,
            "length": length_of(chosen),
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
            mids = tr.get("l_points")
            if not mids and tr.get("mid_point"):
                mids = [tr["mid_point"]]
            pts = [tr["start"]] + (mids or []) + [tr["end"]]
            pts = [(pt["x"] * S, pt["y"] * S) for pt in pts if pt]
            # drop consecutive duplicates (degenerate zero-length segments)
            pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
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


def generate_pcb(
    netlist: str, circuit_ir: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate PCB layout from a netlist or CircuitIR (preferred).

    Args:
        netlist: SPICE netlist (simulation view; fallback only)
        circuit_ir: CircuitIR — the physical source of truth

    Returns:
        PCB layout data
    """
    generator = PCBGenerator()
    layout = generator.generate_pcb_layout(netlist, circuit_ir=circuit_ir)

    if layout.get("status") == "success":
        # Generate visualization
        pcb_svg = generator.generate_pcb_visualization(layout)
        layout["visualization"] = pcb_svg
    return layout


# ---------------------------------------------------------------------------
# CircuitIR -> board components
#
# The IR describes the PHYSICAL circuit (real refs, real parts); the SPICE
# netlist derived from it replaces registry parts with engineering models
# (V/I sources). The board must be built from the IR, never from that netlist.
# ---------------------------------------------------------------------------

def _pin_sort_key(pin: str):
    """Natural pin order: numbers numeric-first, letter pins A* before B*."""
    s = str(pin)
    if s.isdigit():
        return (0, 0, int(s), "")
    m = re.match(r"([A-Za-z]+)(\d*)", s)
    if m:
        return (0, 1, int(m.group(2) or 0), m.group(1))
    return (1, 0, 0, s)


def _footprint_for(comp_type: str, value: str, pins: int = 0) -> str:
    """KiCad footprint for a component letter type; pin count picks DIP size
    and header width."""
    if comp_type == "U":
        if pins and pins > 8:
            if pins <= 14:
                return "Package_DIP:DIP-14_W7.62mm"
            if pins <= 16:
                return "Package_DIP:DIP-16_W7.62mm"
            if pins <= 20:
                return "Package_DIP:DIP-20_W7.62mm"
        return "Package_DIP:DIP-8_W7.62mm"
    if comp_type == "J":
        n = max(pins or 2, 2)
        return f"Connector_PinHeader_2.54mm:PinHeader_1x{n:02d}_P2.54mm_Vertical"
    footprints = {
        "R": "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal",
        "C": "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm",
        "L": "Inductor_THT:L_Axial_L12.0mm_D4.5mm_P15.00mm",
        "D": "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal",
        "Q": "Package_TO_SOT_THT:TO-92",
        "V": "TestPoint:TestPoint_THT_Pad_D2.0mm_Drill1.0mm"
    }
    return footprints.get(comp_type, "Unknown")


_IR_TYPE_LETTER = {
    "resistor": "R",
    "capacitor": "C",
    "inductor": "L",
    "led": "D",
    "diode": "D",
    "transistor": "Q",
    "connector": "J",
    "switch": "S",
    "voltage_source": "V",
    "battery": "V",
    "signal_source": "V",
}


def _components_from_ir(circuit_ir: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Board component list from a CircuitIR: one entry per real part.

    Per-component ``nodes`` is the per-pad net list (pad k+1 -> nodes[k]);
    pads with no IR net get a unique NC name so they never alias each other
    into phantom nets.
    """
    # local import: mcp_schematic lives at the eda_tools root and pulls no
    # heavy deps at module level
    from mcp_schematic import _REAL_PARTS, _real_part_key, _expand_real_part_connections

    ir, _drops = _expand_real_part_connections(circuit_ir)
    pin_net: Dict[str, Dict[str, str]] = {}
    for net in ir.get("nets") or []:
        if not isinstance(net, dict):
            continue
        nm = str(net.get("name") or "")
        for conn in net.get("connections") or []:
            ref, _, pin = str(conn).rpartition(".")
            if ref and pin:
                pin_net.setdefault(ref, {})[pin] = nm

    components: List[Dict[str, Any]] = []
    for comp in ir.get("components") or []:
        if not isinstance(comp, dict):
            continue
        ref = str(comp.get("ref") or comp.get("name") or "X?")
        value = str(comp.get("value") or comp.get("model") or "")
        key = _real_part_key(comp)
        if key is not None:
            part = _REAL_PARTS[key]
            pins = sorted(
                {p for group in part["pins"].values() for p in group},
                key=_pin_sort_key,
            )
            nets = pin_net.get(ref, {})
            nodes = [nets.get(p, f"NC${ref}.{p}") for p in pins]
            components.append({
                "name": ref,
                "type": "U",
                "value": part["value_label"],
                "footprint": part["footprint"],
                "nodes": nodes,
                "position": {"x": 0, "y": 0},
            })
            continue

        t = str(comp.get("type") or "").lower().strip()
        letter = _IR_TYPE_LETTER.get(t, "U")
        n_pins = max(len(comp.get("nodes") or []), 2)
        nets = pin_net.get(ref, {})
        pin_count = max(
            [int(p) for p in nets if str(p).isdigit()] + [n_pins]
        )
        nodes = [nets.get(str(k), f"NC${ref}.{k}") for k in range(1, pin_count + 1)]
        components.append({
            "name": ref,
            "type": letter,
            "value": value,
            "footprint": _footprint_for(letter, value, pin_count),
            "nodes": nodes,
            "position": {"x": 0, "y": 0},
        })
    return components
