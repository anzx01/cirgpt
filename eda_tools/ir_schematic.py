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
