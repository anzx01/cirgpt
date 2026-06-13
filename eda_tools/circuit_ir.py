"""
CircuitIR helpers for the KiCad-first MVP.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, Optional


def _component(ir: Dict[str, Any], ref: str) -> Optional[Dict[str, Any]]:
    for comp in ir.get("components", []):
        if comp.get("ref") == ref:
            return comp
    return None


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


def _spice_value(value: float, unit: str = "") -> str:
    abs_value = abs(value)
    sign = "-" if value < 0 else ""
    if unit == "F":
        if abs_value >= 1e-3:
            return f"{value:g}"
        if abs_value >= 1e-6:
            return f"{sign}{abs_value * 1e6:g}u"
        if abs_value >= 1e-9:
            return f"{sign}{abs_value * 1e9:g}n"
        return f"{sign}{abs_value * 1e12:g}p"
    if unit == "ohm":
        if abs_value >= 1_000_000:
            return f"{sign}{abs_value / 1_000_000:g}Meg"
        if abs_value >= 1_000:
            return f"{sign}{abs_value / 1_000:g}k"
    return f"{value:g}"


def generate_spice_netlist(ir: Dict[str, Any]) -> str:
    """Generate a SPICE netlist from v1 CircuitIR."""
    if not ir.get("supported", False):
        raise ValueError("Unsupported CircuitIR cannot be converted to SPICE")

    circuit_type = ir.get("circuit_type")
    if circuit_type == "led_current_limiter":
        return _led_netlist(ir)
    if circuit_type == "capacitor_discharge_led":
        return _capacitor_discharge_led_netlist(ir)
    if circuit_type == "rc_low_pass_filter":
        return _rc_netlist(ir)
    if circuit_type == "555_timer_blinker":
        return _timer_netlist(ir)
    if circuit_type in {"opamp_inverting", "opamp_non_inverting"}:
        return _opamp_netlist(ir)
    if circuit_type == "generic_circuit":
        return _generic_netlist(ir)

    raise ValueError(f"Unsupported CircuitIR type: {circuit_type}")


def _header(ir: Dict[str, Any]) -> list[str]:
    return [
        f"* {ir.get('title', 'CircuitGPT design')}",
        "* Generated from CircuitIR v1",
        "",
    ]


def _led_netlist(ir: Dict[str, Any]) -> str:
    supply = _value(_role(ir, "supply"), 5.0)
    resistor = _value(_role(ir, "current_limit"), 150.0)
    lines = _header(ir)
    lines.extend([
        f"V1 VCC 0 DC {supply:g}",
        f"R1 VCC LED_A {_spice_value(resistor, 'ohm')}",
        "D1 LED_A 0 LED",
        ".model LED D(Is=1e-12 Rs=10 N=1.8 Cjo=10p Vj=2.0)",
        ".op",
        ".tran 1m 100m",
        ".end",
    ])
    return "\n".join(lines)


def _capacitor_discharge_led_netlist(ir: Dict[str, Any]) -> str:
    supply = _value(_role(ir, "supply"), 5.0)
    charge_resistor = _value(_role(ir, "charge_resistor"), 47.0)
    discharge_resistor = _value(_role(ir, "discharge_resistor"), 10_000.0)
    capacitor = _value(_role(ir, "storage_capacitor"), 100e-6)
    rled = _value(_role(ir, "led_resistor"), 330.0)

    constraints = ir.get("constraints", {})
    tau = float(constraints.get("time_constant_s", discharge_resistor * capacitor))
    press_time = float(constraints.get("button_press_s", max(0.2, min(tau * 0.5, 1.0))))
    duration = max(press_time + tau * 5.0, 2.0)
    step = max(min(tau / 100.0, 0.01), 1e-4)
    switch_threshold = max(supply / 2.0, 0.1)

    lines = _header(ir)
    lines.extend([
        "* Momentary charge, then RC discharge LED fade preview",
        f"V1 VCC 0 DC {supply:g}",
        f"VCTRL CTRL 0 PULSE(0 {supply:g} 0 1m 1m {press_time:g} {duration:g})",
        "S1 VCC CHARGE CTRL 0 SW_PUSH",
        f".model SW_PUSH SW(Ron=0.1 Roff=100Meg Vt={switch_threshold:g} Vh=0.2)",
        f"RCHG CHARGE CAP {_spice_value(charge_resistor, 'ohm')}",
        f"C1 CAP 0 {_spice_value(capacitor, 'F')} IC=0",
        f"RDIS CAP 0 {_spice_value(discharge_resistor, 'ohm')}",
        f"RLED CAP LED_A {_spice_value(rled, 'ohm')}",
        "D1 LED_A 0 LED",
        ".model LED D(Is=1e-12 Rs=10 N=1.8 Cjo=10p Vj=2.0)",
        f".tran {step:g} {duration:g} uic",
        ".end",
    ])
    return "\n".join(lines)


def _rc_netlist(ir: Dict[str, Any]) -> str:
    resistor = _value(_role(ir, "series_resistor"), 10_000.0)
    capacitor = _value(_role(ir, "shunt_capacitor"), 15.9e-9)
    lines = _header(ir)
    lines.extend([
        "V1 IN 0 AC 1 SIN(0 1 1000)",
        f"R1 IN OUT {_spice_value(resistor, 'ohm')}",
        f"C1 OUT 0 {_spice_value(capacitor, 'F')}",
        ".ac dec 20 10 100k",
        ".tran 10u 5m",
        ".end",
    ])
    return "\n".join(lines)


def _timer_netlist(ir: Dict[str, Any]) -> str:
    supply = _value(_role(ir, "supply"), 9.0)
    r1 = _value(_role(ir, "timing_ra"), 1_000.0)
    r2 = _value(_role(ir, "timing_rb"), 71_500.0)
    c1 = _value(_role(ir, "timing_capacitor"), 10e-6)
    rled = _value(_role(ir, "led_resistor"), 470.0)
    frequency = float(ir.get("constraints", {}).get("target_frequency_hz", 1.0))
    period = 1.0 / max(frequency, 0.001)
    half = period / 2.0
    duration = max(period * 3.0, 0.2)
    step = max(period / 200.0, 1e-4)

    lines = _header(ir)
    lines.extend([
        f"V1 VCC 0 DC {supply:g}",
        f"R1 VCC DISCH {_spice_value(r1, 'ohm')}",
        f"R2 DISCH THRESH {_spice_value(r2, 'ohm')}",
        f"C1 THRESH 0 {_spice_value(c1, 'F')}",
        f"VOSC OUT 0 PULSE(0 {supply:g} 0 1m 1m {half:g} {period:g})",
        f"R3 OUT LED_A {_spice_value(rled, 'ohm')}",
        "D1 LED_A 0 LED",
        ".model LED D(Is=1e-12 Rs=10 N=1.8 Cjo=10p Vj=2.0)",
        f".tran {step:g} {duration:g}",
        ".end",
    ])
    return "\n".join(lines)


def _opamp_netlist(ir: Dict[str, Any]) -> str:
    gain = abs(float(ir.get("constraints", {}).get("gain", 10.0)))
    is_inverting = ir.get("circuit_type") == "opamp_inverting"
    supply = abs(float(ir.get("constraints", {}).get("supply_voltage_v", 15.0)))
    r_input = _value(_role(ir, "input_resistor"), 10_000.0)
    r_feedback = _value(_role(ir, "feedback"), r_input * gain)

    lines = _header(ir)
    lines.extend([
        "* Real op-amp circuit using subcircuit model",
        f"* Gain = {'-' if is_inverting else '+'}{gain}",
        "",
        "Vin IN 0 AC 1 SIN(0 0.1 1000)",
        f"VCC VCC 0 DC {supply:g}",
        f"VEE VEE 0 DC -{supply:g}",
        "",
    ])

    if is_inverting:
        # Inverting configuration
        lines.extend([
            "* Inverting op-amp configuration",
            f"R1 IN SUMMING {_spice_value(r_input, 'ohm')}",
            f"R2 OUTPUT SUMMING {_spice_value(r_feedback, 'ohm')}",
            "R3 SUMMING 0 10Meg",
            "",
            "* Op-amp subcircuit: inp inm out vcc vee",
            "XU1 0 SUMMING OUTPUT VCC VEE OPAMP_IDEAL",
            "",
            "RLOAD OUTPUT 0 100k",
        ])
    else:
        # Non-inverting configuration
        lines.extend([
            "* Non-inverting op-amp configuration",
            f"R1 SUMMING 0 {_spice_value(r_input, 'ohm')}",
            f"R2 OUTPUT SUMMING {_spice_value(r_feedback, 'ohm')}",
            "",
            "* Op-amp subcircuit: inp inm out vcc vee",
            "XU1 IN SUMMING OUTPUT VCC VEE OPAMP_IDEAL",
            "",
            "RLOAD OUTPUT 0 100k",
        ])

    # Add op-amp subcircuit model
    lines.extend([
        "",
        "* Ideal op-amp subcircuit model (simplified UA741)",
        ".subckt OPAMP_IDEAL inp inm out vcc vee",
        "  Rin inp inm 2Meg",
        "  Egain out 0 inp inm 200k",
        "  Rout out 0 75",
        ".ends",
        "",
        ".tran 10u 5m",
        ".ac dec 20 10 100k",
        ".end",
    ])
    return "\n".join(lines)


def _generic_netlist(ir: Dict[str, Any]) -> str:
    lines = _header(ir)
    lines.extend([
        "* CIRGPT_GENERIC_CIRCUIT",
        "* CIRGPT_SIMULATION: not_available",
        "* Connectivity netlist for an arbitrary natural-language circuit draft.",
        "* It is intended for schematic/BOM/PCB preview, not direct ngspice simulation.",
        "",
    ])

    used_refs: set[str] = set()
    counters: Dict[str, int] = {}
    for component in ir.get("components", []):
        line = _generic_component_line(component, counters, used_refs)
        if line:
            lines.append(line)

    nets = ir.get("nets") or []
    if nets:
        lines.extend(["", "* Nets"])
        for net in nets:
            if not isinstance(net, dict):
                continue
            name = _safe_node(net.get("name", "NET"))
            connections = ", ".join(str(item) for item in net.get("connections", []))
            lines.append(f"* {name}: {connections}")

    lines.append(".end")
    return "\n".join(lines)


def _generic_component_line(
    component: Dict[str, Any],
    counters: Dict[str, int],
    used_refs: set[str],
) -> str:
    if not isinstance(component, dict):
        return ""

    ctype = str(component.get("type", "module")).lower()
    nodes = [_safe_node(node) for node in component.get("nodes", []) if node is not None]
    if not nodes:
        return ""

    prefix = _generic_prefix(ctype)
    ref = _safe_ref(str(component.get("ref") or ""), prefix, counters, used_refs)
    value = _generic_component_value(component)

    if prefix == "V":
        n1, n2 = _pad_nodes(nodes, 2)
        return f"{ref} {n1} {n2} DC {value}"
    if prefix in {"R", "C", "L"}:
        n1, n2 = _pad_nodes(nodes, 2)
        return f"{ref} {n1} {n2} {value}"
    if prefix == "D":
        n1, n2 = _pad_nodes(nodes, 2)
        if "led" in ctype and "led" not in value.lower():
            value = "LED"
        return f"{ref} {n1} {n2} {value}"
    if prefix == "Q":
        n1, n2, n3 = _pad_nodes(nodes, 3)
        return f"{ref} {n1} {n2} {n3} {value}"
    if prefix == "S":
        n1, n2, n3, n4 = _pad_nodes(nodes, 4)
        return f"{ref} {n1} {n2} {n3} {n4} {value}"

    return f"{ref} {' '.join(nodes)} {value}"


def _generic_prefix(component_type: str) -> str:
    if "voltage" in component_type or component_type in {"supply", "power_source"}:
        return "V"
    if "resistor" in component_type:
        return "R"
    if "capacitor" in component_type:
        return "C"
    if "inductor" in component_type:
        return "L"
    if "led" in component_type or "diode" in component_type:
        return "D"
    if any(token in component_type for token in ("transistor", "mosfet", "nmos", "pmos", "bjt")):
        return "Q"
    if "switch" in component_type:
        return "S"
    if "motor" in component_type or "pump" in component_type or "fan" in component_type:
        return "M"
    if "relay" in component_type:
        return "K"
    if "connector" in component_type or "terminal" in component_type:
        return "J"
    if any(token in component_type for token in ("ic", "controller", "comparator", "opamp", "timer", "microcontroller", "sensor")):
        return "U"
    return "X"


def _safe_ref(ref: str, prefix: str, counters: Dict[str, int], used_refs: set[str]) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", ref.strip())
    if not cleaned or not cleaned[0].isalpha():
        cleaned = ""

    if cleaned and cleaned[0].upper() == prefix and cleaned.upper() not in used_refs:
        used_refs.add(cleaned.upper())
        return cleaned

    while True:
        counters[prefix] = counters.get(prefix, 0) + 1
        candidate = f"{prefix}{counters[prefix]}"
        if candidate.upper() not in used_refs:
            used_refs.add(candidate.upper())
            return candidate


def _safe_node(node: Any) -> str:
    text = str(node).strip()
    if text.lower() in {"gnd", "ground", "earth"}:
        return "0"
    text = re.sub(r"[^A-Za-z0-9_+-]", "_", text)
    return text or "NET"


def _pad_nodes(nodes: list[str], count: int) -> list[str]:
    padded = list(nodes[:count])
    while len(padded) < count:
        padded.append("0")
    return padded


def _generic_component_value(component: Dict[str, Any]) -> str:
    value = component.get("value", "")
    unit = str(component.get("unit") or "")
    if isinstance(value, (int, float)) and unit in {"ohm", "F"}:
        return _spice_value(float(value), unit)
    if isinstance(value, (int, float)):
        return f"{float(value):g}"

    text = str(value or component.get("type") or "GENERIC")
    text = re.sub(r"\s+", "_", text.strip())
    text = re.sub(r"[^A-Za-z0-9_.+-]", "_", text)
    return text or "GENERIC"


def generate_kicad_pcb_preview(ir: Dict[str, Any]) -> str:
    """Return an experimental, clearly labeled KiCad PCB placeholder file."""
    component_lines = []
    x = 20
    y = 20
    for comp in ir.get("components", []):
        component_lines.append(
            f'  (footprint "CircuitGPT:Placeholder" (layer "F.Cu") '
            f'(at {x} {y}) (property "Reference" "{comp.get("ref", "?")}") '
            f'(property "Value" "{comp.get("value", "")}"))'
        )
        x += 18
        if x > 110:
            x = 20
            y += 18

    payload = {
        "notice": "Experimental preview only. Run KiCad ERC/DRC before manufacturing.",
        "circuit_type": ir.get("circuit_type"),
    }
    return "\n".join([
        '(kicad_pcb (version 20240108) (generator "CircuitGPT KiCad-first MVP")',
        '  (general (thickness 1.6))',
        '  (paper "A4")',
        '  (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (44 "Edge.Cuts" user))',
        f"  (gr_text {json.dumps(json.dumps(payload))} (at 20 10) (layer \"F.SilkS\"))",
        *component_lines,
        ")",
    ])


def artifact_metadata(ids: Iterable[str]) -> Dict[str, Dict[str, str]]:
    names = {
        "netlist": ("circuit.spice", "text/plain"),
        "schematic_svg": ("schematic.svg", "image/svg+xml"),
        "bom_csv": ("bom.csv", "text/csv"),
        "validation_json": ("validation.json", "application/json"),
        "kicad_pcb": ("preview.kicad_pcb", "application/octet-stream"),
    }
    return {
        artifact_id: {"filename": names[artifact_id][0], "media_type": names[artifact_id][1]}
        for artifact_id in ids
        if artifact_id in names
    }
