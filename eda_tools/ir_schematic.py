"""
CircuitIR-backed schematic renderer for supported MVP circuit types.

The SPICE netlist is optimized for simulation, so it may replace real devices
with behavioral sources. These renderers draw the user-facing circuit from
CircuitIR instead.
"""
from __future__ import annotations

from html import escape
from typing import Any, Dict, Optional


def _role(ir: Dict[str, Any], role: str) -> Optional[Dict[str, Any]]:
    for comp in ir.get("components", []):
        if comp.get("role") == role:
            return comp
    return None


def _value(comp: Optional[Dict[str, Any]], default: float) -> float:
    if comp is None:
        return default
    try:
        return float(comp.get("value", default))
    except (TypeError, ValueError):
        return default


def _fmt_value(value: float, unit: str) -> str:
    if unit == "F":
        if abs(value) >= 1e-3:
            return f"{value:g} F"
        if abs(value) >= 1e-6:
            return f"{value * 1e6:g} uF"
        if abs(value) >= 1e-9:
            return f"{value * 1e9:g} nF"
        return f"{value * 1e12:g} pF"
    if unit == "ohm":
        if abs(value) >= 1_000_000:
            return f"{value / 1_000_000:g} MOhm"
        if abs(value) >= 1_000:
            return f"{value / 1_000:g} kOhm"
        return f"{value:g} Ohm"
    if unit == "V":
        return f"{value:g} V"
    return f"{value:g}"


def generate_ir_schematic_svg(ir: Dict[str, Any]) -> str:
    """Generate a schematic SVG from CircuitIR when a dedicated renderer exists."""
    circuit_type = ir.get("circuit_type")
    if circuit_type == "555_timer_blinker":
        return _render_555_timer(ir)
    if circuit_type == "capacitor_discharge_led":
        return _render_capacitor_discharge_led(ir)
    if circuit_type == "generic_circuit":
        return _render_generic_circuit(ir)
    return ""


def _svg_start(width: int, height: int, title: str) -> list[str]:
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "  .wire { fill: none; stroke: #1266ff; stroke-width: 2.4; stroke-linecap: round; stroke-linejoin: round; }",
        "  .symbol { fill: #fff; stroke: #111; stroke-width: 2; }",
        "  .pin { fill: #111; }",
        "  .label { font-family: Arial, sans-serif; font-size: 14px; fill: #111; }",
        "  .small { font-family: Arial, sans-serif; font-size: 12px; fill: #444; }",
        "  .net { font-family: Arial, sans-serif; font-size: 11px; fill: #1266ff; }",
        "  .title { font-family: Arial, sans-serif; font-size: 18px; font-weight: 700; fill: #111; }",
        "</style>",
        f'<text class="title" x="24" y="32">{escape(title)}</text>',
    ]


def _wire(lines: list[str], points: list[tuple[int, int]]) -> None:
    path = f"M {points[0][0]} {points[0][1]}"
    for x, y in points[1:]:
        path += f" L {x} {y}"
    lines.append(f'<path class="wire" d="{path}" />')


def _junction(lines: list[str], x: int, y: int) -> None:
    lines.append(f'<circle class="pin" cx="{x}" cy="{y}" r="3.5" />')


def _label(lines: list[str], text: str, x: int, y: int, cls: str = "label", anchor: str = "start") -> None:
    lines.append(f'<text class="{cls}" x="{x}" y="{y}" text-anchor="{anchor}">{escape(text)}</text>')


def _resistor(lines: list[str], ref: str, value: str, x: int, y: int, horizontal: bool = True) -> None:
    if horizontal:
        lines.append(f'<rect class="symbol" x="{x}" y="{y - 18}" width="86" height="36" rx="5" />')
        _label(lines, ref, x + 8, y - 4)
        _label(lines, value, x + 8, y + 12, "small")
    else:
        lines.append(f'<rect class="symbol" x="{x - 18}" y="{y}" width="36" height="86" rx="5" />')
        _label(lines, ref, x - 10, y + 32)
        _label(lines, value, x - 18, y + 50, "small")


def _capacitor(lines: list[str], ref: str, value: str, x: int, y: int, horizontal: bool = False) -> None:
    if horizontal:
        lines.append(f'<line class="symbol" x1="{x + 36}" y1="{y - 22}" x2="{x + 36}" y2="{y + 22}" />')
        lines.append(f'<line class="symbol" x1="{x + 50}" y1="{y - 22}" x2="{x + 50}" y2="{y + 22}" />')
        _label(lines, ref, x + 24, y - 30)
        _label(lines, value, x + 20, y + 38, "small")
    else:
        lines.append(f'<line class="symbol" x1="{x - 24}" y1="{y + 36}" x2="{x + 24}" y2="{y + 36}" />')
        lines.append(f'<line class="symbol" x1="{x - 24}" y1="{y + 50}" x2="{x + 24}" y2="{y + 50}" />')
        _label(lines, ref, x + 34, y + 38)
        _label(lines, value, x + 34, y + 54, "small")


def _ground(lines: list[str], x: int, y: int) -> None:
    lines.append(f'<line class="symbol" x1="{x}" y1="{y}" x2="{x}" y2="{y + 12}" />')
    lines.append(f'<line class="symbol" x1="{x - 16}" y1="{y + 12}" x2="{x + 16}" y2="{y + 12}" />')
    lines.append(f'<line class="symbol" x1="{x - 10}" y1="{y + 18}" x2="{x + 10}" y2="{y + 18}" />')
    lines.append(f'<line class="symbol" x1="{x - 5}" y1="{y + 24}" x2="{x + 5}" y2="{y + 24}" />')


def _supply(lines: list[str], ref: str, value: str, x: int, y: int) -> None:
    lines.append(f'<circle class="symbol" cx="{x}" cy="{y}" r="26" />')
    _label(lines, ref, x - 12, y - 6)
    _label(lines, value, x - 16, y + 12, "small")
    _ground(lines, x, y + 40)


def _led(lines: list[str], ref: str, x: int, y: int) -> None:
    lines.append(f'<polygon class="symbol" points="{x},{y - 22} {x},{y + 22} {x + 34},{y}" />')
    lines.append(f'<line class="symbol" x1="{x + 38}" y1="{y - 24}" x2="{x + 38}" y2="{y + 24}" />')
    lines.append(f'<line class="symbol" x1="{x + 46}" y1="{y - 18}" x2="{x + 60}" y2="{y - 32}" />')
    lines.append(f'<line class="symbol" x1="{x + 56}" y1="{y - 12}" x2="{x + 70}" y2="{y - 26}" />')
    _label(lines, ref, x + 2, y + 42)


def _ic_555(lines: list[str], x: int, y: int) -> Dict[str, tuple[int, int]]:
    width = 180
    height = 220
    lines.append(f'<rect class="symbol" x="{x}" y="{y}" width="{width}" height="{height}" rx="8" />')
    _label(lines, "U1", x + 74, y + 28, "label", "middle")
    _label(lines, "NE555", x + 90, y + 50, "small", "middle")
    pins = {
        "GND": (x, y + 185),
        "TRIG": (x, y + 92),
        "OUT": (x + width, y + 92),
        "RESET": (x + width, y + 52),
        "CTRL": (x, y + 138),
        "THRESH": (x, y + 70),
        "DISCH": (x + width, y + 138),
        "VCC": (x + width, y + 28),
    }
    left_labels = [("THRESH", pins["THRESH"]), ("TRIG", pins["TRIG"]), ("CTRL", pins["CTRL"]), ("GND", pins["GND"])]
    right_labels = [("VCC", pins["VCC"]), ("RESET", pins["RESET"]), ("OUT", pins["OUT"]), ("DISCH", pins["DISCH"])]
    for name, (px, py) in left_labels:
        _wire(lines, [(px - 24, py), (px, py)])
        _junction(lines, px, py)
        _label(lines, name, px + 8, py + 4, "small")
    for name, (px, py) in right_labels:
        _wire(lines, [(px, py), (px + 24, py)])
        _junction(lines, px, py)
        _label(lines, name, px - 54, py + 4, "small")
    return pins


def _render_555_timer(ir: Dict[str, Any]) -> str:
    supply = _fmt_value(_value(_role(ir, "supply"), 9.0), "V")
    r1 = _fmt_value(_value(_role(ir, "timing_ra"), 1_000.0), "ohm")
    r2 = _fmt_value(_value(_role(ir, "timing_rb"), 71_500.0), "ohm")
    c1 = _fmt_value(_value(_role(ir, "timing_capacitor"), 10e-6), "F")
    c2 = _fmt_value(_value(_role(ir, "control_capacitor"), 10e-9), "F")
    rled = _fmt_value(_value(_role(ir, "led_resistor"), 470.0), "ohm")

    lines = _svg_start(980, 620, "555 timer LED blinker")
    pins = _ic_555(lines, 380, 180)

    _supply(lines, "V1", supply, 105, 115)
    _wire(lines, [(105, 89), (105, 70), (760, 70), (760, 208), (584, 208)])
    _label(lines, "VCC", 118, 64, "net")
    _wire(lines, [(584, 232), (760, 232), (760, 70)])
    _label(lines, "RESET tied high", 768, 226, "small")

    _resistor(lines, "R1", r1, 230, 70, True)
    _wire(lines, [(105, 70), (230, 70)])
    _wire(lines, [(316, 70), (650, 70), (650, 318), (584, 318)])
    _label(lines, "DISCH", 592, 310, "net")

    _resistor(lines, "R2", r2, 640, 360, False)
    _wire(lines, [(650, 318), (640, 318), (640, 360)])
    _wire(lines, [(640, 446), (270, 446), (270, 250), (356, 250)])
    _wire(lines, [(270, 250), (270, 272), (356, 272)])
    _label(lines, "THRESH/TRIG", 278, 242, "net")

    _capacitor(lines, "C1", c1, 270, 470, False)
    _wire(lines, [(270, 446), (270, 506)])
    _ground(lines, 270, 520)

    _capacitor(lines, "C2", c2, 300, 318, False)
    _wire(lines, [(356, 318), (300, 318), (300, 354)])
    _ground(lines, 300, 368)
    _label(lines, "CTRL", 306, 312, "net")

    _wire(lines, [(356, 365), (330, 365), (330, 470)])
    _ground(lines, 330, 470)

    _resistor(lines, "R3", rled, 650, 272, True)
    _wire(lines, [(584, 272), (650, 272)])
    _led(lines, "D1 LED", 780, 272)
    _wire(lines, [(736, 272), (780, 272)])
    _wire(lines, [(818, 272), (870, 272), (870, 420)])
    _ground(lines, 870, 420)

    lines.append("</svg>")
    return "\n".join(lines)


def _switch(lines: list[str], ref: str, x: int, y: int) -> None:
    lines.append(f'<line class="symbol" x1="{x}" y1="{y}" x2="{x + 30}" y2="{y}" />')
    lines.append(f'<line class="symbol" x1="{x + 60}" y1="{y}" x2="{x + 90}" y2="{y}" />')
    lines.append(f'<line class="symbol" x1="{x + 32}" y1="{y}" x2="{x + 62}" y2="{y - 22}" />')
    _junction(lines, x + 30, y)
    _junction(lines, x + 60, y)
    _label(lines, ref, x + 30, y - 34)
    _label(lines, "pushbutton", x + 16, y + 22, "small")


def _render_capacitor_discharge_led(ir: Dict[str, Any]) -> str:
    supply = _fmt_value(_value(_role(ir, "supply"), 5.0), "V")
    rchg = _fmt_value(_value(_role(ir, "charge_resistor"), 47.0), "ohm")
    c1 = _fmt_value(_value(_role(ir, "storage_capacitor"), 100e-6), "F")
    rdis = _fmt_value(_value(_role(ir, "discharge_resistor"), 10_000.0), "ohm")
    rled = _fmt_value(_value(_role(ir, "led_resistor"), 300.0), "ohm")

    lines = _svg_start(900, 500, "Capacitor discharge LED fade")
    _supply(lines, "V1", supply, 100, 120)
    _wire(lines, [(100, 94), (100, 80), (210, 80)])
    _label(lines, "VCC", 112, 72, "net")
    _switch(lines, "S1", 210, 80)
    _wire(lines, [(300, 80), (345, 80)])
    _resistor(lines, "RCHG", rchg, 345, 80, True)
    _wire(lines, [(431, 80), (520, 80), (520, 145)])
    _junction(lines, 520, 80)
    _label(lines, "CAP", 532, 76, "net")

    _capacitor(lines, "C1", c1, 520, 145, False)
    _wire(lines, [(520, 80), (520, 181)])
    _ground(lines, 520, 196)

    _resistor(lines, "RDIS", rdis, 610, 132, False)
    _wire(lines, [(520, 80), (610, 80), (610, 132)])
    _wire(lines, [(610, 218), (610, 240)])
    _ground(lines, 610, 240)

    _resistor(lines, "RLED", rled, 610, 80, True)
    _wire(lines, [(696, 80), (755, 80)])
    _led(lines, "D1 LED", 755, 80)
    _wire(lines, [(793, 80), (835, 80), (835, 240)])
    _ground(lines, 835, 240)
    _label(lines, "LED fades as CAP discharges", 610, 44, "small")

    lines.append("</svg>")
    return "\n".join(lines)


def _render_generic_circuit(ir: Dict[str, Any]) -> str:
    components = [component for component in ir.get("components", []) if isinstance(component, dict)]
    if not components:
        return ""

    placements = _generic_component_positions(components)
    width = max(980, max(x + w for x, _y, w, _h in placements.values()) + 80)
    height = max(520, max(y + h for _x, y, _w, h in placements.values()) + 95)

    title = str(ir.get("title") or "Generic circuit draft")
    lines = _svg_start(width, height, title)
    _label(lines, "LLM parsed CircuitIR schematic draft. Verify topology, values, and ratings before building.", 24, 58, "small")

    pin_map: Dict[str, list[tuple[int, int]]] = {}
    component_pins: Dict[str, list[Dict[str, Any]]] = {}
    for component in components:
        ref = str(component.get("ref") or "?")
        x, y, w, h = placements[ref]
        pins = _generic_symbol_pins(component, x, y, w, h)
        component_pins[ref] = pins
        for pin in pins:
            pin_map.setdefault(str(pin["net"]), []).append((pin["x"], pin["y"]))

    _render_generic_wires(lines, pin_map, width, height)

    for component in components:
        ref = str(component.get("ref") or "?")
        x, y, w, h = placements[ref]
        _draw_generic_symbol(lines, component, x, y, w, h, component_pins[ref])

    lines.append("</svg>")
    return "\n".join(lines)


def _generic_component_positions(components: list[Dict[str, Any]]) -> Dict[str, tuple[int, int, int, int]]:
    columns: list[list[Dict[str, Any]]] = [[] for _ in range(5)]
    for component in components:
        columns[_generic_column(component)].append(component)

    positions: Dict[str, tuple[int, int, int, int]] = {}
    left = 70
    top = 125
    col_step = 220
    row_step = 132
    for col_index, column in enumerate(columns):
        x = left + col_index * col_step
        for row_index, component in enumerate(column):
            ref = str(component.get("ref") or f"X{col_index}{row_index}")
            w, h = _generic_symbol_size(component)
            positions[ref] = (x, top + row_index * row_step, w, h)
    return positions


def _generic_symbol_size(component: Dict[str, Any]) -> tuple[int, int]:
    kind = _generic_symbol_kind(component)
    sizes = {
        "source": (90, 100),
        "resistor": (130, 58),
        "capacitor": (120, 64),
        "diode": (122, 62),
        "transistor": (130, 104),
        "opamp": (146, 108),
        "ic": (150, 122),
        "connector": (118, 90),
        "motor": (118, 82),
        "switch": (120, 62),
    }
    return sizes.get(kind, (130, 76))


def _generic_symbol_kind(component: Dict[str, Any]) -> str:
    ref = str(component.get("ref") or "").upper()
    role = str(component.get("role") or "").lower()
    ctype = str(component.get("type") or "").lower()
    text = f"{role} {ctype}"
    if ref.startswith("V") or "voltage" in text or "supply" in text:
        return "source"
    if ref.startswith("R") or "resistor" in text:
        return "resistor"
    if ref.startswith("C") or "capacitor" in text:
        return "capacitor"
    if ref.startswith("D") or "diode" in text or "led" in text:
        return "diode"
    if ref.startswith("Q") or any(token in text for token in ("mosfet", "transistor", "nmos", "pmos", "bjt")):
        return "transistor"
    if "comparator" in text or "opamp" in text or "op-amp" in text:
        return "opamp"
    if ref.startswith("J") or "connector" in text or "terminal" in text:
        return "connector"
    if ref.startswith("M") or any(token in text for token in ("motor", "pump", "fan", "solenoid", "valve")):
        return "motor"
    if ref.startswith("S") or "switch" in text:
        return "switch"
    if ref.startswith("U") or any(token in text for token in ("controller", "microcontroller", "timer", "ic", "sensor")):
        return "ic"
    return "ic"


def _generic_symbol_pins(component: Dict[str, Any], x: int, y: int, w: int, h: int) -> list[Dict[str, Any]]:
    nodes = [str(node) for node in component.get("nodes", []) or []]
    kind = _generic_symbol_kind(component)
    if not nodes:
        return []

    if kind == "source":
        top = next((node for node in nodes if _is_power_net(node)), nodes[0])
        bottom = next((node for node in nodes if _is_ground_net(node)), nodes[1] if len(nodes) > 1 else "0")
        return [
            {"net": top, "x": x + w // 2, "y": y, "label": "+"},
            {"net": bottom, "x": x + w // 2, "y": y + h, "label": "-"},
        ]

    if kind in {"resistor", "capacitor", "diode", "motor", "switch"}:
        first = nodes[0]
        second = nodes[1] if len(nodes) > 1 else "0"
        return [
            {"net": first, "x": x, "y": y + h // 2, "label": "1"},
            {"net": second, "x": x + w, "y": y + h // 2, "label": "2"},
        ]

    if kind == "transistor":
        padded = (nodes + ["0", "0"])[:3]
        return [
            {"net": padded[0], "x": x + w // 2, "y": y, "label": "D/C"},
            {"net": padded[1], "x": x, "y": y + h // 2, "label": "G/B"},
            {"net": padded[2], "x": x + w // 2, "y": y + h, "label": "S/E"},
        ]

    if kind == "opamp":
        padded = (nodes + ["0", "0", "OUT", "VCC", "0"])[:5]
        return [
            {"net": padded[0], "x": x, "y": y + 34, "label": "+"},
            {"net": padded[1], "x": x, "y": y + h - 34, "label": "-"},
            {"net": padded[2], "x": x + w, "y": y + h // 2, "label": "OUT"},
            {"net": padded[3], "x": x + w // 2, "y": y, "label": "V+"},
            {"net": padded[4], "x": x + w // 2, "y": y + h, "label": "V-"},
        ]

    pins: list[Dict[str, Any]] = []
    for index, node in enumerate(nodes):
        side_left = index % 2 == 0
        side_index = index // 2
        side_count = (len(nodes) + (1 if side_left else 0)) // 2
        pin_y = y + int((side_index + 1) * h / (side_count + 1))
        pins.append({
            "net": node,
            "x": x if side_left else x + w,
            "y": pin_y,
            "label": str(index + 1),
        })
    return pins


def _render_generic_wires(
    lines: list[str],
    pin_map: Dict[str, list[tuple[int, int]]],
    width: int,
    height: int,
) -> None:
    vcc_y = 82
    gnd_y = height - 54
    rail_left = 38
    rail_right = width - 38

    if any(_is_power_net(net) for net in pin_map):
        _wire(lines, [(rail_left, vcc_y), (rail_right, vcc_y)])
        _label(lines, "VCC", rail_left + 8, vcc_y - 10, "net")
    if any(_is_ground_net(net) for net in pin_map):
        _wire(lines, [(rail_left, gnd_y), (rail_right, gnd_y)])
        _label(lines, "0 / GND", rail_left + 8, gnd_y - 10, "net")

    for net, raw_points in sorted(pin_map.items()):
        points = [point for index, point in enumerate(raw_points) if point not in raw_points[:index]]
        if not points:
            continue

        if _is_power_net(net):
            for x, y in points:
                _wire(lines, [(x, vcc_y), (x, y)])
                _junction(lines, x, y)
            continue

        if _is_ground_net(net):
            for x, y in points:
                _wire(lines, [(x, y), (x, gnd_y)])
                _junction(lines, x, y)
            continue

        if len(points) < 2:
            continue

        base = points[0]
        for index, point in enumerate(points[1:], start=1):
            mid_x = int((base[0] + point[0]) / 2)
            _wire(lines, [base, (mid_x, base[1]), (mid_x, point[1]), point])
            if index == 1:
                _label(lines, _short_text(str(net), 18), mid_x + 4, min(base[1], point[1]) - 6, "net")
        for x, y in points:
            _junction(lines, x, y)


def _draw_generic_symbol(
    lines: list[str],
    component: Dict[str, Any],
    x: int,
    y: int,
    w: int,
    h: int,
    pins: list[Dict[str, Any]],
) -> None:
    kind = _generic_symbol_kind(component)
    ref = str(component.get("ref") or "?")
    value = _short_text(_generic_value_text(component) or str(component.get("type") or ""), 22)

    if kind == "source":
        cx = x + w // 2
        cy = y + h // 2
        lines.append(f'<circle class="symbol" cx="{cx}" cy="{cy}" r="28" />')
        _wire(lines, [(cx, y), (cx, cy - 28)])
        _wire(lines, [(cx, cy + 28), (cx, y + h)])
        _label(lines, "+", cx - 5, cy - 10)
        _label(lines, "-", cx - 4, cy + 18)
        _label(lines, ref, x + 4, y + 20)
        _label(lines, value, x + 2, y + h + 18, "small")
    elif kind == "resistor":
        cy = y + h // 2
        _wire(lines, [(x, cy), (x + 20, cy)])
        lines.append(f'<rect class="symbol" x="{x + 20}" y="{cy - 18}" width="{w - 40}" height="36" rx="2" />')
        _wire(lines, [(x + w - 20, cy), (x + w, cy)])
        _label(lines, ref, x + 32, cy - 24)
        _label(lines, value, x + 32, cy + 34, "small")
    elif kind == "capacitor":
        cy = y + h // 2
        left_plate = x + w // 2 - 8
        right_plate = x + w // 2 + 8
        _wire(lines, [(x, cy), (left_plate, cy)])
        _wire(lines, [(right_plate, cy), (x + w, cy)])
        lines.append(f'<line class="symbol" x1="{left_plate}" y1="{cy - 24}" x2="{left_plate}" y2="{cy + 24}" />')
        lines.append(f'<line class="symbol" x1="{right_plate}" y1="{cy - 24}" x2="{right_plate}" y2="{cy + 24}" />')
        _label(lines, ref, x + 30, cy - 30)
        _label(lines, value, x + 26, cy + 38, "small")
    elif kind == "diode":
        cy = y + h // 2
        tri_left = x + 34
        tri_right = x + 72
        _wire(lines, [(x, cy), (tri_left, cy)])
        lines.append(f'<polygon class="symbol" points="{tri_left},{cy - 22} {tri_left},{cy + 22} {tri_right},{cy}" />')
        lines.append(f'<line class="symbol" x1="{tri_right + 6}" y1="{cy - 24}" x2="{tri_right + 6}" y2="{cy + 24}" />')
        _wire(lines, [(tri_right + 6, cy), (x + w, cy)])
        if "led" in str(component.get("type", "")).lower() or ref.upper().startswith("LED"):
            lines.append(f'<line class="symbol" x1="{tri_right + 18}" y1="{cy - 18}" x2="{tri_right + 32}" y2="{cy - 32}" />')
            lines.append(f'<line class="symbol" x1="{tri_right + 28}" y1="{cy - 12}" x2="{tri_right + 42}" y2="{cy - 26}" />')
        _label(lines, ref, x + 32, cy - 30)
        _label(lines, value, x + 28, cy + 38, "small")
    elif kind == "transistor":
        cx = x + w // 2
        gate_x = x + 32
        _wire(lines, [(cx, y), (cx, y + 24)])
        _wire(lines, [(cx, y + h - 24), (cx, y + h)])
        lines.append(f'<line class="symbol" x1="{cx}" y1="{y + 24}" x2="{cx}" y2="{y + h - 24}" />')
        lines.append(f'<line class="symbol" x1="{gate_x}" y1="{y + 26}" x2="{gate_x}" y2="{y + h - 26}" />')
        _wire(lines, [(x, y + h // 2), (gate_x, y + h // 2)])
        lines.append(f'<line class="symbol" x1="{gate_x + 16}" y1="{y + 34}" x2="{cx - 8}" y2="{y + 34}" />')
        lines.append(f'<line class="symbol" x1="{gate_x + 16}" y1="{y + h - 34}" x2="{cx - 8}" y2="{y + h - 34}" />')
        _label(lines, ref, x + 54, y + 48)
        _label(lines, value, x + 42, y + 66, "small")
    elif kind == "opamp":
        points = f"{x + 20},{y + 14} {x + 20},{y + h - 14} {x + w - 18},{y + h // 2}"
        lines.append(f'<polygon class="symbol" points="{points}" />')
        _wire(lines, [(x, y + 34), (x + 20, y + 34)])
        _wire(lines, [(x, y + h - 34), (x + 20, y + h - 34)])
        _wire(lines, [(x + w - 18, y + h // 2), (x + w, y + h // 2)])
        _wire(lines, [(x + w // 2, y), (x + w // 2, y + 22)])
        _wire(lines, [(x + w // 2, y + h - 22), (x + w // 2, y + h)])
        _label(lines, "+", x + 26, y + 39)
        _label(lines, "-", x + 28, y + h - 29)
        _label(lines, ref, x + 58, y + h // 2 - 8)
        _label(lines, value, x + 52, y + h // 2 + 12, "small")
    elif kind == "motor":
        cx = x + w // 2
        cy = y + h // 2
        _wire(lines, [(x, cy), (cx - 31, cy)])
        _wire(lines, [(cx + 31, cy), (x + w, cy)])
        lines.append(f'<circle class="symbol" cx="{cx}" cy="{cy}" r="31" />')
        _label(lines, "M", cx - 7, cy + 5)
        _label(lines, ref, x + 34, y - 8)
        _label(lines, value, x + 20, y + h + 18, "small")
    elif kind == "switch":
        cy = y + h // 2
        _wire(lines, [(x, cy), (x + 34, cy)])
        _wire(lines, [(x + w - 34, cy), (x + w, cy)])
        lines.append(f'<line class="symbol" x1="{x + 36}" y1="{cy}" x2="{x + w - 38}" y2="{cy - 24}" />')
        _junction(lines, x + 34, cy)
        _junction(lines, x + w - 34, cy)
        _label(lines, ref, x + 40, cy - 32)
        _label(lines, value, x + 24, cy + 32, "small")
    else:
        lines.append(f'<rect class="symbol" x="{x + 18}" y="{y + 10}" width="{w - 36}" height="{h - 20}" rx="3" />')
        for pin in pins:
            px = pin["x"]
            py = pin["y"]
            if px <= x:
                _wire(lines, [(x, py), (x + 18, py)])
                _label(lines, pin["label"], x + 22, py + 4, "small")
            elif px >= x + w:
                _wire(lines, [(x + w - 18, py), (x + w, py)])
                _label(lines, pin["label"], x + w - 38, py + 4, "small")
        _label(lines, ref, x + w // 2, y + 34, "label", "middle")
        _label(lines, value, x + w // 2, y + 54, "small", "middle")

    for pin in pins:
        _junction(lines, pin["x"], pin["y"])


def _generic_column(component: Dict[str, Any]) -> int:
    role = str(component.get("role") or "").lower()
    ctype = str(component.get("type") or "").lower()
    text = f"{role} {ctype}"

    if any(token in text for token in ("supply", "power", "voltage")):
        return 0
    if any(token in text for token in ("input", "sensor", "bias", "filter", "threshold")):
        return 1
    if any(token in text for token in ("controller", "control", "comparator", "opamp", "timer", "microcontroller", "ic")):
        return 2
    if any(token in text for token in ("driver", "switch", "mosfet", "transistor", "flyback", "clamp", "gate")):
        return 3
    if any(token in text for token in ("load", "output", "pump", "motor", "fan", "indicator", "actuator", "led")):
        return 4
    return 2


def _generic_value_text(component: Dict[str, Any]) -> str:
    value = component.get("value", "")
    unit = str(component.get("unit") or "")
    if isinstance(value, (int, float)):
        if unit in {"ohm", "F", "V"}:
            return _fmt_value(float(value), unit)
        if unit:
            return f"{value:g} {unit}"
        return f"{value:g}"
    if unit and unit not in {"model", "module", "terminal"}:
        return f"{value} {unit}"
    return str(value)


def _is_power_net(net: str) -> bool:
    upper = str(net).upper()
    return upper in {"VCC", "VDD", "VIN", "+V", "VBAT", "SUPPLY"}


def _is_ground_net(net: str) -> bool:
    upper = str(net).upper()
    return upper in {"0", "GND", "GROUND", "VSS"}


def _short_text(text: str, limit: int) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)] + "..."
