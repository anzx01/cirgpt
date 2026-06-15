"""
CircuitIR-backed schematic renderer for supported MVP circuit types.

The SPICE netlist is optimized for simulation, so it may replace real devices
with behavioral sources. These renderers draw the user-facing circuit from
CircuitIR instead.
"""
from __future__ import annotations

import json
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


def generate_ir_schematic_svg(ir: Dict[str, Any]) -> Any:
    """Generate a schematic SVG from CircuitIR.

    Backward compatible:
    - If the IR has a `subsystems` field (v2 free-form), returns a dict
      ``{"pages": [...], "summary": ..., "layout": "subsystem-paged"}``
      with one SVG page per subsystem plus a final cross-page summary page.
    - Otherwise returns a plain SVG string for legacy callers.
    """
    circuit_type = ir.get("circuit_type")
    if ir.get("subsystems"):
        return _render_subsystem_paged(ir)
    if circuit_type == "555_timer_blinker":
        return _render_555_timer(ir)
    if circuit_type == "capacitor_discharge_led":
        return _render_capacitor_discharge_led(ir)
    if circuit_type == "led_current_limiter":
        return _render_led_limiter(ir)
    if circuit_type == "generic_circuit":
        if _is_sensor_driver_controller(ir):
            return _render_sensor_driver_controller(ir)
        return _render_generic_circuit(ir)
    return ""


def _render_led_limiter(ir: Dict[str, Any]) -> str:
    """Minimal IR-based renderer for the LED current-limiter template."""
    components = [component for component in ir.get("components", []) if isinstance(component, dict)]
    title = str(ir.get("title") or "LED current limiter")
    lines = _svg_start(720, 360, title)

    supply_comp = next((c for c in components if str(c.get("role", "")).lower() == "supply"), None)
    resistor = next((c for c in components if str(c.get("role", "")).lower() == "current_limit"), None)
    led = next((c for c in components if str(c.get("role", "")).lower() == "indicator"), None)

    supply_v = supply_comp.get("value", 5) if supply_comp else 5
    r_val = resistor.get("value", 150) if resistor else 150

    if supply_comp:
        _supply(lines, _ref(supply_comp, "V1"), f"{supply_v:g} V", 110, 110)
    if resistor:
        _resistor(lines, _ref(resistor, "R1"), _component_value(resistor, "150 Ohm"), 230, 150, True)
    if led:
        _led(lines, _ref(led, "D1"), 360, 150)

    if supply_comp and resistor:
        _wire(lines, [(110, 110), (110, 90), (230, 90), (230, 150)])
    if resistor and led:
        _wire(lines, [(316, 150), (360, 150)])
    if led:
        _wire(lines, [(394, 150), (430, 150), (430, 200)])
        _ground(lines, 430, 200)
    if supply_comp:
        _wire(lines, [(110, 200)])
        _ground(lines, 110, 200)

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Subsystem-paged renderer (v2 free-form)
# ---------------------------------------------------------------------------

_SUBSYSTEM_PAGE_GAP = 96
_SUBSYSTEM_PAGE_TITLE_Y = 28
_SUBSYSTEM_PAGE_FOOTER_Y = 540
_SUBSYSTEM_COL_STEP = 220
_SUBSYSTEM_ROW_STEP = 132
_SUBSYSTEM_LEFT = 70
_SUBSYSTEM_TOP = 105

# Subsystem color palette (one per category from the v2 prompt's layered
# decomposition). Used to tint the page banner and group components visually.
_SUBSYSTEM_COLORS = {
    "power_input": "#bbf7d0",
    "protection": "#fed7aa",
    "isolation": "#fde68a",
    "signal_input": "#bfdbfe",
    "signal_chain": "#c7d2fe",
    "control": "#e9d5ff",
    "load_output": "#fecaca",
    "feedback": "#a7f3d0",
    "hmi": "#fbcfe8",
    "communication": "#cffafe",
    "other": "#e5e7eb",
}


def _subsystem_color(name: str) -> str:
    key = (name or "").lower().strip()
    for token, color in _SUBSYSTEM_COLORS.items():
        if token in key:
            return color
    return _SUBSYSTEM_COLORS["other"]


def _assign_components_to_subsystems(ir: Dict[str, Any]) -> Dict[str, list[Dict[str, Any]]]:
    """Group components by their `subsystem` field, falling back to role/column."""
    components = [c for c in ir.get("components", []) if isinstance(c, dict)]
    subsystems = ir.get("subsystems") or []
    grouped: Dict[str, list[Dict[str, Any]]] = {}

    # Pre-seed known subsystem names so the order is stable.
    for sub in subsystems:
        if isinstance(sub, dict) and sub.get("name"):
            grouped.setdefault(str(sub["name"]), [])

    # First pass: explicit subsystem field.
    explicit = {str(c.get("ref")): str(c.get("subsystem")) for c in components if c.get("subsystem")}

    # Second pass: cross-check against subsystems[].component_refs.
    for sub in subsystems:
        if not isinstance(sub, dict):
            continue
        name = str(sub.get("name") or "other")
        refs = set(sub.get("component_refs") or [])
        for comp in components:
            ref = str(comp.get("ref") or "")
            if not ref:
                continue
            if ref in explicit and explicit[ref] == name:
                grouped.setdefault(name, []).append(comp)
            elif ref in refs and (ref not in explicit):
                grouped.setdefault(name, []).append(comp)

    # Third pass: anything not assigned yet goes into a fallback bucket.
    assigned_refs = {c.get("ref") for group in grouped.values() for c in group}
    for comp in components:
        if comp.get("ref") in assigned_refs:
            continue
        if comp.get("subsystem"):
            target = str(comp["subsystem"])
        else:
            target = _infer_subsystem_from_role(comp)
        grouped.setdefault(target, []).append(comp)

    return {name: grouped[name] for name in grouped if grouped[name]}


def _infer_subsystem_from_role(component: Dict[str, Any]) -> str:
    role = str(component.get("role") or "").lower()
    ctype = str(component.get("type") or "").lower()
    text = f"{role} {ctype}"
    if any(t in text for t in ("supply", "power", "regulator", "reference")):
        return "power_input"
    if any(t in text for t in ("protection", "fuse", "tvs", "gdt", "clamp")):
        return "protection"
    if any(t in text for t in ("isolation", "isolated", "optocoupler")):
        return "isolation"
    if any(t in text for t in ("sensor", "antenna", "input_signal", "signal_input", "connector", "bias")):
        return "signal_input"
    if any(t in text for t in ("amplifier", "filter", "adc", "dac", "driver", "signal_chain")):
        return "signal_chain"
    if any(t in text for t in ("controller", "microcontroller", "comparator", "logic", "mcu", "dsp")):
        return "control"
    if any(t in text for t in ("load", "motor", "pump", "fan", "solenoid", "valve", "relay_contact", "low_side_switch", "high_side_switch", "h_bridge")):
        return "load_output"
    if any(t in text for t in ("feedback", "current_shunt", "rtd", "thermistor")):
        return "feedback"
    if any(t in text for t in ("indicator", "led", "button", "switch", "display", "encoder", "buzzer", "hmi")):
        return "hmi"
    if any(t in text for t in ("communication", "uart", "spi", "i2c", "can", "rs485", "ethernet", "usb", "wireless", "antenna", "bluetooth", "wifi")):
        return "communication"
    return "other"


def _subsystem_metadata(ir: Dict[str, Any], name: str) -> Dict[str, Any]:
    for sub in ir.get("subsystems") or []:
        if isinstance(sub, dict) and str(sub.get("name") or "").strip().lower() == name.strip().lower():
            return {
                "name": name,
                "purpose": str(sub.get("purpose") or ""),
                "component_refs": list(sub.get("component_refs") or []),
            }
    return {"name": name, "purpose": "", "component_refs": []}


def _render_subsystem_page(
    ir: Dict[str, Any],
    subsystem_name: str,
    components: list[Dict[str, Any]],
    page_index: int,
    total_pages: int,
    width: int = 1180,
    height: int = 620,
) -> Dict[str, Any]:
    """Render one subsystem into its own SVG page."""
    title = f"{ir.get('title') or 'Circuit'} — {subsystem_name}"
    lines = _svg_start(width, height, title)
    meta = _subsystem_metadata(ir, subsystem_name)

    # Banner
    color = _subsystem_color(subsystem_name)
    lines.append(
        f'<rect x="0" y="0" width="{width}" height="44" fill="{color}" opacity="0.85" />'
    )
    _label(lines, f"Page {page_index + 1} / {total_pages}  ·  {subsystem_name}", 24, 28, "label")
    if meta.get("purpose"):
        _label(lines, meta["purpose"], width - 24, 28, "small", "end")
    _label(lines, "Subsystem view (v2 free-form)", 24, 58, "small")

    if not components:
        _label(lines, "No components were assigned to this subsystem.", 24, 120, "small")
        lines.append("</svg>")
        return {"subsystem": subsystem_name, "svg": "\n".join(lines), "components": []}

    # Reuse the generic column layout but bounded to this subsystem's refs.
    placement = _subsystem_positions(components)
    pin_map: Dict[str, list[tuple[int, int]]] = {}
    component_pins: Dict[str, list[Dict[str, Any]]] = {}
    for comp in components:
        ref = str(comp.get("ref") or "?")
        x, y, w, h = placement[ref]
        pins = _generic_symbol_pins(comp, x, y, w, h)
        component_pins[ref] = pins
        for pin in pins:
            pin_map.setdefault(str(pin["net"]), []).append((pin["x"], pin["y"]))

    _render_generic_wires(lines, pin_map, width, height)

    for comp in components:
        ref = str(comp.get("ref") or "?")
        x, y, w, h = placement[ref]
        _draw_generic_symbol(lines, comp, x, y, w, h, component_pins[ref])

    # Footer
    _label(lines, f"{len(components)} component(s) on this page", 24, height - 18, "small")
    lines.append("</svg>")
    return {
        "subsystem": subsystem_name,
        "purpose": meta.get("purpose", ""),
        "svg": "\n".join(lines),
        "components": [str(c.get("ref") or "") for c in components],
    }


def _subsystem_positions(components: list[Dict[str, Any]]) -> Dict[str, tuple[int, int, int, int]]:
    columns: list[list[Dict[str, Any]]] = [[] for _ in range(5)]
    for component in components:
        columns[_generic_column(component)].append(component)

    positions: Dict[str, tuple[int, int, int, int]] = {}
    for col_index, column in enumerate(columns):
        x = _SUBSYSTEM_LEFT + col_index * _SUBSYSTEM_COL_STEP
        for row_index, component in enumerate(column):
            ref = str(component.get("ref") or f"X{col_index}{row_index}")
            w, h = _generic_symbol_size(component)
            positions[ref] = (x, _SUBSYSTEM_TOP + row_index * _SUBSYSTEM_ROW_STEP, w, h)
    return positions


def _render_cross_subsystem_summary(
    ir: Dict[str, Any],
    page_assignments: Dict[str, list[str]],
    total_pages: int,
    width: int = 1180,
    height: int = 620,
) -> str:
    """Final summary page listing every subsystem and the components it owns."""
    lines = _svg_start(width, height, f"{ir.get('title') or 'Circuit'} — overview")
    lines.append(
        f'<rect x="0" y="0" width="{width}" height="44" fill="#bfdbfe" opacity="0.85" />'
    )
    _label(lines, f"Page {total_pages} / {total_pages}  ·  Overview", 24, 28, "label")
    _label(lines, "All subsystems in this CircuitIR", width - 24, 28, "small", "end")

    cursor_y = 80
    for name, refs in page_assignments.items():
        meta = _subsystem_metadata(ir, name)
        color = _subsystem_color(name)
        lines.append(
            f'<rect x="24" y="{cursor_y - 6}" width="16" height="16" fill="{color}" stroke="#111" />'
        )
        _label(lines, name, 50, cursor_y + 6, "label")
        if meta.get("purpose"):
            _label(lines, meta["purpose"], 200, cursor_y + 6, "small")
        ref_text = ", ".join(refs) if refs else "(empty)"
        _label(lines, ref_text, 24, cursor_y + 28, "small")
        cursor_y += 56

    # Optional rich metadata at the bottom.
    metadata_fields = [
        ("domain", "Domain"),
        ("compliance_standards", "Compliance standards"),
        ("operating_envelope", "Operating envelope"),
    ]
    if any(ir.get(field) for field, _ in metadata_fields):
        cursor_y += 24
        _label(lines, "Metadata", 24, cursor_y, "label")
        cursor_y += 24
        for field, label in metadata_fields:
            value = ir.get(field)
            if not value:
                continue
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            _label(lines, f"{label}: {_short_text(str(text), 96)}", 24, cursor_y, "small")
            cursor_y += 18

    # Open questions, if any, always belong on the summary page.
    open_questions = ir.get("open_questions") or []
    if open_questions:
        cursor_y += 18
        _label(lines, "Open questions (please confirm before PCB layout)", 24, cursor_y, "label")
        cursor_y += 20
        for question in open_questions[:8]:
            _label(lines, f"• {_short_text(str(question), 110)}", 24, cursor_y, "small")
            cursor_y += 18

    lines.append("</svg>")
    return "\n".join(lines)


def _render_subsystem_paged(ir: Dict[str, Any]) -> Dict[str, Any]:
    grouped = _assign_components_to_subsystems(ir)
    page_assignments: Dict[str, list[str]] = {
        name: [str(c.get("ref") or "") for c in comps]
        for name, comps in grouped.items()
    }

    # Stable ordering: keep the order declared in subsystems[] first, then any
    # inferred bucket in insertion order.
    declared = [
        str(sub.get("name"))
        for sub in (ir.get("subsystems") or [])
        if isinstance(sub, dict) and sub.get("name")
    ]
    ordered_names: list[str] = []
    for name in declared:
        if name in grouped and name not in ordered_names:
            ordered_names.append(name)
    for name in grouped:
        if name not in ordered_names:
            ordered_names.append(name)

    total_pages = len(ordered_names) + 1  # +1 for the summary page
    pages: list[Dict[str, Any]] = []
    for index, name in enumerate(ordered_names):
        page = _render_subsystem_page(ir, name, grouped[name], index, total_pages)
        pages.append(page)

    summary_svg = _render_cross_subsystem_summary(ir, page_assignments, total_pages)
    pages.append({
        "subsystem": "_overview",
        "purpose": "Cross-subsystem summary and metadata",
        "svg": summary_svg,
        "components": [],
    })

    return {
        "layout": "subsystem-paged",
        "circuit_type": ir.get("circuit_type"),
        "subsystem_order": ordered_names,
        "component_to_subsystem": {
            ref: name
            for name, refs in page_assignments.items()
            for ref in refs
        },
        "pages": pages,
        "summary": {
            "page_count": len(pages),
            "subsystem_count": len(ordered_names),
            "total_components": sum(len(p.get("components") or []) for p in pages[:-1]),
            "prompt_version": (ir.get("source") or {}).get("prompt_version"),
        },
    }


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


def _is_sensor_driver_controller(ir: Dict[str, Any]) -> bool:
    components = ir.get("components", [])
    text = " ".join(
        f"{component.get('ref', '')} {component.get('type', '')} {component.get('role', '')}"
        for component in components
        if isinstance(component, dict)
    ).lower()
    has_sensor = "sensor" in text
    has_controller = any(token in text for token in ("comparator", "microcontroller", "controller", "opamp"))
    has_driver = any(token in text for token in ("mosfet", "transistor", "nmos", "pmos", "relay", "driver"))
    has_load = any(token in text for token in ("pump", "solenoid", "valve", "motor", "fan", "load"))
    return has_sensor and has_controller and has_driver and has_load


def _render_sensor_driver_controller(ir: Dict[str, Any]) -> str:
    comps = [component for component in ir.get("components", []) if isinstance(component, dict)]
    title = str(ir.get("title") or "Sensor driver controller")
    lines = _svg_start(1180, 720, title)
    _label(lines, "LLM parsed CircuitIR schematic draft. Verify topology, values, and ratings before building.", 24, 58, "small")

    supply = _find_component(comps, roles=("supply", "positive_supply"), types=("voltage_source",))
    sensor = _find_component(comps, roles=("sensor", "sensor_connector"), types=("sensor", "soil"))
    pullup = _find_component(comps, roles=("pullup", "sensor_pullup", "input_bias"), types=("resistor",))
    filt = _find_component(comps, roles=("filter", "sensor_filter"), types=("capacitor",))
    controller = _find_component(comps, roles=("threshold", "controller", "comparator"), types=("comparator", "opamp", "controller"))
    threshold_parts = [
        component for component in comps
        if component.get("ref") not in {pullup.get("ref") if pullup else None}
        and "threshold" in str(component.get("role", "")).lower()
        and str(component.get("type", "")).lower() == "resistor"
    ]
    r_top = threshold_parts[0] if threshold_parts else _find_component(comps, roles=("threshold_high", "threshold_ra"), types=("resistor",))
    r_bottom = threshold_parts[1] if len(threshold_parts) > 1 else _find_component(comps, roles=("threshold_low", "threshold_rb"), types=("resistor",))
    driver = _find_component(comps, roles=("driver", "mosfet_driver", "low_side_switch"), types=("nmos", "mosfet", "transistor"))
    flyback = _find_component(comps, roles=("flyback", "flyback_diode"), types=("diode",))
    load = _find_component(comps, roles=("pump", "load", "actuator"), types=("pump", "motor", "solenoid", "valve"))
    indicator = _find_component(comps, roles=("indicator",), types=("led",))
    led_res = _find_component(comps, roles=("led_resistor", "indicator_resistor"), types=("resistor",), exclude={pullup.get("ref") if pullup else "", r_top.get("ref") if r_top else "", r_bottom.get("ref") if r_bottom else ""})

    _supply(lines, _ref(supply, "V1"), _component_value(supply, "5 V"), 95, 155)
    _power_marker(lines, "VCC", 95, 105)

    sense_node = (330, 230)
    sensor_x, sensor_y = 210, 160
    lines.append(f'<rect class="symbol" x="{sensor_x}" y="{sensor_y}" width="130" height="64" rx="4" />')
    lines.append(f'<path class="symbol" d="M {sensor_x + 24} {sensor_y + 34} C {sensor_x + 42} {sensor_y + 14}, {sensor_x + 58} {sensor_y + 54}, {sensor_x + 76} {sensor_y + 34} S {sensor_x + 108} {sensor_y + 34}, {sensor_x + 118} {sensor_y + 34}" />')
    _label(lines, _ref(sensor, "SENSOR"), sensor_x + 65, sensor_y + 18, "label", "middle")
    _label(lines, _short_text(str(sensor.get("type") if sensor else "sensor"), 22), sensor_x + 65, sensor_y + 86, "small", "middle")
    _wire(lines, [(sensor_x + 130, sensor_y + 32), sense_node])
    _wire(lines, [(sensor_x + 70, sensor_y + 64), (sensor_x + 70, sensor_y + 82)])
    _ground(lines, sensor_x + 70, sensor_y + 82)
    _junction(lines, *sense_node)

    if pullup:
        _resistor(lines, _ref(pullup, "RPU"), _component_value(pullup, "10 kOhm"), 360, 118, False)
        _power_marker(lines, "VCC", 360, 112)
        _wire(lines, [(360, 204), (360, sense_node[1]), sense_node])

    if filt:
        _capacitor(lines, _ref(filt, "CFILT"), _component_value(filt, "100 nF"), 300, 250, False)
        _wire(lines, [sense_node, (300, 250), (300, 286)])
        _ground(lines, 300, 300)

    comp_x, comp_y = 460, 245
    _draw_opamp_symbol(lines, _ref(controller, "U1"), _component_value(controller, "comparator"), comp_x, comp_y)
    _wire(lines, [sense_node, (comp_x, comp_y + 34)])

    thresh_node = (390, 430)
    if r_top:
        _resistor(lines, _ref(r_top, "RTH1"), _component_value(r_top, "10 kOhm"), 390, 330, False)
        _power_marker(lines, "VCC", 390, 324)
        _wire(lines, [(390, 416), thresh_node])
    if r_bottom:
        _resistor(lines, _ref(r_bottom, "RTH2"), _component_value(r_bottom, "10 kOhm"), 390, 455, False)
        _wire(lines, [thresh_node, (390, 455)])
        _wire(lines, [(390, 541), (390, 560)])
        _ground(lines, 390, 560)
    _wire(lines, [thresh_node, (430, thresh_node[1]), (430, comp_y + 74), (comp_x, comp_y + 74)])
    _label(lines, "THRESH", thresh_node[0] - 50, thresh_node[1] - 8, "net")

    out = (comp_x + 146, comp_y + 54)
    gate = (740, 300)
    _wire(lines, [out, (660, out[1]), (660, gate[1]), gate])
    _label(lines, "CTRL", 640, gate[1] - 10, "net")

    _draw_nmos_symbol(lines, _ref(driver, "Q1"), _component_value(driver, "NMOS"), 740, 245)
    _wire(lines, [(805, 245), (805, 190), (960, 190)])
    _label(lines, "PUMP_DRV", 825, 180, "net")
    _wire(lines, [(805, 349), (805, 380)])
    _ground(lines, 805, 380)

    _draw_motor_symbol(lines, _ref(load, "LOAD"), _component_value(load, "pump"), 960, 150)
    _power_marker(lines, "VCC", 1040, 150)
    _wire(lines, [(960, 190), (925, 190), (925, 245), (805, 245)])

    if flyback:
        _draw_diode_vertical(lines, _ref(flyback, "D1"), _component_value(flyback, "diode"), 910, 150, 250)
        _wire(lines, [(910, 150), (1040, 150)])
        _wire(lines, [(910, 250), (925, 250), (925, 190)])

    if indicator and led_res:
        _resistor(lines, _ref(led_res, "RLED"), _component_value(led_res, "330 Ohm"), 720, 475, True)
        _led(lines, _ref(indicator, "LED"), 585, 475)
        _power_marker(lines, "VCC", 585, 475)
        _wire(lines, [(623, 475), (720, 475)])
        _wire(lines, [(806, 475), (840, 475), (840, gate[1]), gate])

    lines.append("</svg>")
    return "\n".join(lines)


def _find_component(
    components: list[Dict[str, Any]],
    roles: tuple[str, ...] = (),
    types: tuple[str, ...] = (),
    exclude: set[str] | None = None,
) -> Optional[Dict[str, Any]]:
    exclude = exclude or set()
    for component in components:
        if str(component.get("ref", "")) in exclude:
            continue
        role = str(component.get("role", "")).lower()
        ctype = str(component.get("type", "")).lower()
        if roles and any(role_name in role for role_name in roles):
            return component
        if types and any(type_name in ctype for type_name in types):
            return component
    return None


def _ref(component: Optional[Dict[str, Any]], default: str) -> str:
    return str(component.get("ref") if component else default)


def _component_value(component: Optional[Dict[str, Any]], default: str) -> str:
    if not component:
        return default
    value = _generic_value_text(component)
    return _short_text(value or _generic_fallback_value(component) or default, 24)


def _draw_opamp_symbol(lines: list[str], ref: str, value: str, x: int, y: int) -> None:
    w, h = 146, 108
    points = f"{x + 20},{y + 14} {x + 20},{y + h - 14} {x + w - 18},{y + h // 2}"
    lines.append(f'<polygon class="symbol" points="{points}" />')
    _wire(lines, [(x, y + 34), (x + 20, y + 34)])
    _wire(lines, [(x, y + h - 34), (x + 20, y + h - 34)])
    _wire(lines, [(x + w - 18, y + h // 2), (x + w, y + h // 2)])
    _power_marker(lines, "VCC", x + w // 2, y)
    _wire(lines, [(x + w // 2, y + h - 22), (x + w // 2, y + h)])
    _ground(lines, x + w // 2, y + h)
    _label(lines, "+", x + 26, y + 39)
    _label(lines, "-", x + 28, y + h - 29)
    _label(lines, ref, x + 58, y + h // 2 - 8)
    _label(lines, value, x + 52, y + h // 2 + 12, "small")


def _draw_nmos_symbol(lines: list[str], ref: str, value: str, x: int, y: int) -> None:
    w, h = 130, 104
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


def _draw_motor_symbol(lines: list[str], ref: str, value: str, x: int, y: int) -> None:
    cx = x + 40
    cy = y + 40
    _wire(lines, [(x, cy), (cx - 31, cy)])
    _wire(lines, [(cx + 31, cy), (x + 105, cy)])
    lines.append(f'<circle class="symbol" cx="{cx}" cy="{cy}" r="31" />')
    _label(lines, "M", cx - 7, cy + 5)
    _label(lines, ref, x + 16, y - 8)
    _label(lines, value, x + 8, y + 92, "small")


def _draw_diode_vertical(lines: list[str], ref: str, value: str, x: int, y1: int, y2: int) -> None:
    mid = (y1 + y2) // 2
    _wire(lines, [(x, y1), (x, mid - 28)])
    lines.append(f'<polygon class="symbol" points="{x - 22},{mid - 28} {x + 22},{mid - 28} {x},{mid + 10}" />')
    lines.append(f'<line class="symbol" x1="{x - 24}" y1="{mid + 16}" x2="{x + 24}" y2="{mid + 16}" />')
    _wire(lines, [(x, mid + 16), (x, y2)])
    _label(lines, ref, x + 28, mid - 8)
    _label(lines, value, x + 28, mid + 10, "small")


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
        "sensor": (132, 78),
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
    if ref.startswith("R") or "resistor" in text:
        return "resistor"
    if ref.startswith("C") or "capacitor" in text:
        return "capacitor"
    if ref.startswith("D") or "diode" in text or "led" in text:
        return "diode"
    if ref.startswith("Q") or any(token in text for token in ("mosfet", "transistor", "nmos", "pmos", "bjt")):
        return "transistor"
    if ref.startswith("V") or ctype in {"voltage_source", "power_source"} or role in {"supply", "positive_supply", "negative_supply"}:
        return "source"
    if "comparator" in text or "opamp" in text or "op-amp" in text:
        return "opamp"
    if ref.startswith("M") or any(token in text for token in ("motor", "pump", "fan", "solenoid", "valve", "load", "actuator")):
        return "motor"
    if "sensor" in text:
        return "sensor"
    if ref.startswith("J") or "connector" in text or "terminal" in text:
        return "connector"
    if ref.startswith("SW") or "switch" in text:
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
        gate = nodes[0]
        source = next((node for node in nodes[1:] if _is_ground_net(node)), nodes[1] if len(nodes) > 1 else "0")
        drain = next((node for node in nodes[1:] if node != source), nodes[2] if len(nodes) > 2 else "0")
        return [
            {"net": drain, "x": x + w // 2, "y": y, "label": "D/C"},
            {"net": gate, "x": x, "y": y + h // 2, "label": "G/B"},
            {"net": source, "x": x + w // 2, "y": y + h, "label": "S/E"},
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
    for net, raw_points in sorted(pin_map.items()):
        points = [point for index, point in enumerate(raw_points) if point not in raw_points[:index]]
        if not points:
            continue

        if _is_power_net(net):
            for x, y in points:
                _power_marker(lines, str(net), x, y)
                _junction(lines, x, y)
            continue

        if _is_ground_net(net):
            for x, y in points:
                _wire(lines, [(x, y), (x, y + 16)])
                _ground(lines, x, y + 16)
                _junction(lines, x, y)
            continue

        if len(points) < 2:
            continue

        routed = sorted(points, key=lambda point: (point[0], point[1]))
        for index in range(len(routed) - 1):
            start = routed[index]
            end = routed[index + 1]
            mid_x = int((start[0] + end[0]) / 2)
            _wire(lines, [start, (mid_x, start[1]), (mid_x, end[1]), end])
            if index == 0:
                _label(lines, _short_text(str(net), 18), mid_x + 4, min(start[1], end[1]) - 6, "net")
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
    value = _short_text(_generic_value_text(component) or _generic_fallback_value(component), 22)

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
    elif kind == "sensor":
        cy = y + h // 2
        _wire(lines, [(x, cy), (x + 18, cy)])
        _wire(lines, [(x + w - 18, cy), (x + w, cy)])
        lines.append(f'<rect class="symbol" x="{x + 18}" y="{y + 12}" width="{w - 36}" height="{h - 24}" rx="3" />')
        lines.append(f'<path class="symbol" d="M {x + 34} {cy} C {x + 46} {cy - 18}, {x + 58} {cy + 18}, {x + 70} {cy} S {x + 94} {cy}, {x + 106} {cy}" />')
        _label(lines, ref, x + w // 2, y + 28, "label", "middle")
        _label(lines, value, x + w // 2, y + h + 16, "small", "middle")
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
    kind = _generic_symbol_kind(component)

    if kind == "source":
        return 0
    if any(token in text for token in ("input", "sensor", "bias", "filter", "threshold")):
        return 1
    if any(token in text for token in ("controller", "control", "comparator", "opamp", "timer", "microcontroller", "ic")):
        return 2
    if any(token in text for token in ("driver", "switch", "mosfet", "transistor", "flyback", "clamp", "gate")):
        return 3
    if any(token in text for token in ("load", "output", "pump", "motor", "fan", "indicator", "actuator", "led", "solenoid", "valve")):
        return 4
    return 2


def _generic_value_text(component: Dict[str, Any]) -> str:
    value = component.get("value", "")
    unit = str(component.get("unit") or "")
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        if unit in {"ohm", "F", "V"}:
            return _fmt_value(float(value), unit)
        if unit:
            return f"{value:g} {unit}"
        return f"{value:g}"
    if unit and unit not in {"model", "module", "terminal"}:
        return f"{value} {unit}"
    return str(value)


def _generic_fallback_value(component: Dict[str, Any]) -> str:
    ctype = str(component.get("type") or "")
    role = str(component.get("role") or "")
    if ctype.lower() in {"connector", "module", "terminal"} and role:
        return role
    return ctype


def _is_power_net(net: str) -> bool:
    upper = str(net).upper()
    return upper in {"VCC", "VDD", "VIN", "+V", "VBAT", "SUPPLY"}


def _is_ground_net(net: str) -> bool:
    upper = str(net).upper()
    return upper in {"0", "GND", "GROUND", "VSS"}


def _power_marker(lines: list[str], net: str, x: int, y: int) -> None:
    stem_top = max(112, y - 24)
    _wire(lines, [(x, y), (x, stem_top)])
    lines.append(f'<path class="symbol" d="M {x - 12} {stem_top} L {x} {stem_top - 16} L {x + 12} {stem_top}" />')
    _label(lines, net, x, stem_top - 24, "net", "middle")


def _short_text(text: str, limit: int) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)] + "..."
