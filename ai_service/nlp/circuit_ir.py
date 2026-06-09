"""
Rule-based CircuitIR builder for the KiCad-first MVP.

The IR is intentionally small and explicit: it captures enough structure to
generate SPICE, schematic previews, BOM data, and KiCad placeholder files
without pretending to be a production-grade synthesis engine.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List


SUPPORTED_TYPES = [
    "led_current_limiter",
    "rc_low_pass_filter",
    "555_timer_blinker",
    "opamp_inverting",
    "opamp_non_inverting",
]


def _first_float(pattern: str, text: str, default: float) -> float:
    match = re.search(pattern, text, re.IGNORECASE)
    return float(match.group(1)) if match else default


def _extract_voltage(text: str, default: float) -> float:
    return _first_float(r"(\d+(?:\.\d+)?)\s*(?:v|volt|volts)\b", text, default)


def _extract_current_a(text: str, default: float) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(ma|a)\b", text, re.IGNORECASE)
    if not match:
        return default
    value = float(match.group(1))
    return value / 1000.0 if match.group(2).lower() == "ma" else value


def _extract_frequency_hz(text: str, default: float) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(mhz|khz|hz)\b", text, re.IGNORECASE)
    if not match:
        return default
    multipliers = {"hz": 1.0, "khz": 1000.0, "mhz": 1_000_000.0}
    return float(match.group(1)) * multipliers[match.group(2).lower()]


def _extract_resistance_ohm(text: str, default: float) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(meg|m|k)?\s*(?:ohm|ohms|r)\b", text, re.IGNORECASE)
    if not match:
        return default
    prefix = (match.group(2) or "").lower()
    multipliers = {"": 1.0, "k": 1000.0, "m": 1_000_000.0, "meg": 1_000_000.0}
    return float(match.group(1)) * multipliers[prefix]


def _extract_gain(text: str, default: float) -> float:
    return _first_float(r"(?:gain(?:\s+of)?|x)\s*(-?\d+(?:\.\d+)?)", text, default)


def _component(ref: str, ctype: str, value: float | str, unit: str, nodes: List[str], role: str) -> Dict[str, Any]:
    return {
        "ref": ref,
        "type": ctype,
        "value": value,
        "unit": unit,
        "nodes": nodes,
        "role": role,
    }


def _nets_from_components(components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    nets: Dict[str, List[str]] = {}
    for comp in components:
        for index, node in enumerate(comp["nodes"], start=1):
            nets.setdefault(node, []).append(f"{comp['ref']}.{index}")
    return [
        {"name": name, "connections": connections}
        for name, connections in sorted(nets.items())
    ]


def _base_ir(description: str, circuit_type: str, title: str) -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "supported": True,
        "circuit_type": circuit_type,
        "title": title,
        "description": description,
        "components": [],
        "nets": [],
        "constraints": {},
        "source": {
            "mode": "rules",
            "rationale": [],
        },
        "warnings": [],
    }


def _led_ir(description: str) -> Dict[str, Any]:
    voltage = _extract_voltage(description, 5.0)
    current = _extract_current_a(description, 0.02)
    led_vf = 2.0
    resistor = max((voltage - led_vf) / current, 1.0)

    ir = _base_ir(description, "led_current_limiter", "LED current limiter")
    ir["components"] = [
        _component("V1", "voltage_source", voltage, "V", ["VCC", "0"], "supply"),
        _component("R1", "resistor", round(resistor, 2), "ohm", ["VCC", "LED_A"], "current_limit"),
        _component("D1", "led", led_vf, "Vf", ["LED_A", "0"], "indicator"),
    ]
    ir["constraints"] = {
        "supply_voltage_v": voltage,
        "target_current_a": current,
        "led_forward_voltage_v": led_vf,
    }
    ir["source"]["rationale"].append("Computed LED resistor from (supply - Vf) / target current.")
    ir["nets"] = _nets_from_components(ir["components"])
    return ir


def _rc_filter_ir(description: str) -> Dict[str, Any]:
    cutoff = _extract_frequency_hz(description, 1000.0)
    resistance = _extract_resistance_ohm(description, 10_000.0)
    capacitance = 1.0 / (2.0 * math.pi * resistance * cutoff)

    ir = _base_ir(description, "rc_low_pass_filter", "RC low-pass filter")
    ir["components"] = [
        _component("V1", "signal_source", 1.0, "V", ["IN", "0"], "input_signal"),
        _component("R1", "resistor", round(resistance, 2), "ohm", ["IN", "OUT"], "series_resistor"),
        _component("C1", "capacitor", capacitance, "F", ["OUT", "0"], "shunt_capacitor"),
    ]
    ir["constraints"] = {
        "cutoff_frequency_hz": cutoff,
        "resistance_ohm": resistance,
        "capacitance_f": capacitance,
    }
    ir["source"]["rationale"].append("Computed C from fc = 1 / (2*pi*R*C).")
    ir["nets"] = _nets_from_components(ir["components"])
    return ir


def _timer_555_ir(description: str) -> Dict[str, Any]:
    voltage = _extract_voltage(description, 9.0)
    frequency = _extract_frequency_hz(description, 1.0)
    c_timing = 10e-6
    r1 = 1000.0
    r2 = max((1.44 / (frequency * c_timing) - r1) / 2.0, 100.0)
    led_resistor = max((voltage - 2.0) / 0.015, 100.0)

    ir = _base_ir(description, "555_timer_blinker", "555 timer LED blinker")
    ir["components"] = [
        _component("V1", "voltage_source", voltage, "V", ["VCC", "0"], "supply"),
        _component("U1", "ne555", "NE555", "model", ["0", "TRIG", "OUT", "RESET", "CTRL", "THRESH", "DISCH", "VCC"], "timer"),
        _component("R1", "resistor", round(r1, 2), "ohm", ["VCC", "DISCH"], "timing_ra"),
        _component("R2", "resistor", round(r2, 2), "ohm", ["DISCH", "THRESH"], "timing_rb"),
        _component("C1", "capacitor", c_timing, "F", ["THRESH", "0"], "timing_capacitor"),
        _component("R3", "resistor", round(led_resistor, 2), "ohm", ["OUT", "LED_A"], "led_resistor"),
        _component("D1", "led", 2.0, "Vf", ["LED_A", "0"], "indicator"),
    ]
    ir["constraints"] = {
        "supply_voltage_v": voltage,
        "target_frequency_hz": frequency,
        "timing_capacitance_f": c_timing,
        "behavioral_model": True,
    }
    ir["warnings"].append("555 simulation uses a behavioral pulse source in v1, not a transistor-level NE555 macromodel.")
    ir["source"]["rationale"].append("Computed astable timing values using f = 1.44 / ((R1 + 2*R2) * C).")
    ir["nets"] = _nets_from_components(ir["components"])
    return ir


def _opamp_ir(description: str, non_inverting: bool) -> Dict[str, Any]:
    gain = abs(_extract_gain(description, 10.0))
    supply = _extract_voltage(description, 15.0)
    r_in = 10_000.0
    if non_inverting:
        r_ground = r_in
        r_feedback = max((gain - 1.0) * r_ground, r_ground)
        circuit_type = "opamp_non_inverting"
        title = "Non-inverting op-amp amplifier"
        components = [
            _component("V1", "signal_source", 0.1, "V", ["IN", "0"], "input_signal"),
            _component("U1", "ideal_opamp", "IDEAL", "model", ["IN", "FB", "OUT", "VCC", "VEE"], "amplifier"),
            _component("R1", "resistor", round(r_ground, 2), "ohm", ["FB", "0"], "gain_ground"),
            _component("R2", "resistor", round(r_feedback, 2), "ohm", ["OUT", "FB"], "feedback"),
        ]
    else:
        r_feedback = r_in * gain
        circuit_type = "opamp_inverting"
        title = "Inverting op-amp amplifier"
        components = [
            _component("V1", "signal_source", 0.1, "V", ["IN", "0"], "input_signal"),
            _component("U1", "ideal_opamp", "IDEAL", "model", ["0", "SUM", "OUT", "VCC", "VEE"], "amplifier"),
            _component("R1", "resistor", round(r_in, 2), "ohm", ["IN", "SUM"], "input_resistor"),
            _component("R2", "resistor", round(r_feedback, 2), "ohm", ["OUT", "SUM"], "feedback"),
        ]

    components.extend([
        _component("VCC", "voltage_source", supply, "V", ["VCC", "0"], "positive_supply"),
        _component("VEE", "voltage_source", -supply, "V", ["VEE", "0"], "negative_supply"),
    ])

    ir = _base_ir(description, circuit_type, title)
    ir["components"] = components
    ir["constraints"] = {
        "gain": gain,
        "supply_voltage_v": supply,
        "ideal_opamp_model": True,
    }
    ir["warnings"].append("Op-amp simulation uses an ideal voltage-controlled source in v1.")
    ir["source"]["rationale"].append("Selected resistor ratio from requested closed-loop gain.")
    ir["nets"] = _nets_from_components(ir["components"])
    return ir


def parse_description_to_ir(description: str) -> Dict[str, Any]:
    """Parse a natural-language request into a constrained CircuitIR."""
    text = description.strip()
    lower = text.lower()

    if not text:
        return unsupported_ir(description, "Description is empty.")

    if "555" in lower or "timer" in lower or "blinker" in lower or "blink" in lower:
        return _timer_555_ir(text)
    if "low-pass" in lower or "low pass" in lower or ("filter" in lower and "high" not in lower):
        return _rc_filter_ir(text)
    if "op-amp" in lower or "op amp" in lower or "amplifier" in lower or "gain" in lower:
        non_inverting = "non-inverting" in lower or "non inverting" in lower or "buffer" in lower
        return _opamp_ir(text, non_inverting)
    if "led" in lower:
        return _led_ir(text)

    return unsupported_ir(
        description,
        "Supported v1 circuit types are LED current limiter, RC low-pass filter, 555 timer blinker, and op-amp amplifier.",
    )


def unsupported_ir(description: str, message: str) -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "supported": False,
        "circuit_type": "unsupported",
        "title": "Unsupported circuit request",
        "description": description,
        "components": [],
        "nets": [],
        "constraints": {"supported_circuit_types": SUPPORTED_TYPES},
        "source": {"mode": "rules", "rationale": []},
        "warnings": [message],
    }
