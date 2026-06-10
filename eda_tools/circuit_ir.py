"""
CircuitIR helpers for the KiCad-first MVP.
"""
from __future__ import annotations

import json
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
    if circuit_type == "rc_low_pass_filter":
        return _rc_netlist(ir)
    if circuit_type == "555_timer_blinker":
        return _timer_netlist(ir)
    if circuit_type in {"opamp_inverting", "opamp_non_inverting"}:
        return _opamp_netlist(ir)

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
