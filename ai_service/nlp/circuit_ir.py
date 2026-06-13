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
    "capacitor_discharge_led",
    "rc_low_pass_filter",
    "555_timer_blinker",
    "opamp_inverting",
    "opamp_non_inverting",
    "generic_circuit",
]


def _first_float(pattern: str, text: str, default: float) -> float:
    match = re.search(pattern, text, re.IGNORECASE)
    return float(match.group(1)) if match else default


def _extract_voltage(text: str, default: float) -> float:
    return _first_float(r"(\d+(?:\.\d+)?)\s*(?:v|volt|volts)(?![a-zA-Z])", text, default)


def _extract_current_a(text: str, default: float) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(ma|a)(?![a-zA-Z])", text, re.IGNORECASE)
    if not match:
        return default
    value = float(match.group(1))
    return value / 1000.0 if match.group(2).lower() == "ma" else value


def _extract_frequency_hz(text: str, default: float) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(mhz|khz|hz)(?![a-zA-Z])", text, re.IGNORECASE)
    if not match:
        return default
    multipliers = {"hz": 1.0, "khz": 1000.0, "mhz": 1_000_000.0}
    return float(match.group(1)) * multipliers[match.group(2).lower()]


def _extract_resistance_ohm(text: str, default: float) -> float:
    patterns = [
        r"(\d+(?:\.\d+)?)\s*(meg|m|k)?\s*(?:ohm|ohms|r|Ω|欧|电阻)(?![a-zA-Z])",
        r"(\d+(?:\.\d+)?)\s*(meg|m|k)\s*(?=$|[^a-zA-Z])",
    ]
    match = None
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            break
    if not match:
        return default
    prefix = (match.group(2) or "").lower()
    multipliers = {"": 1.0, "k": 1000.0, "m": 1_000_000.0, "meg": 1_000_000.0}
    return float(match.group(1)) * multipliers[prefix]


def _extract_capacitance_f(text: str, default: float) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(pf|nf|uf|mf|f)(?![a-zA-Z])", text, re.IGNORECASE)
    if not match:
        return default
    multipliers = {
        "pf": 1e-12,
        "nf": 1e-9,
        "uf": 1e-6,
        "mf": 1e-3,
        "f": 1.0,
    }
    return float(match.group(1)) * multipliers[match.group(2).lower()]


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


def _capacitor_discharge_led_ir(description: str) -> Dict[str, Any]:
    voltage = _extract_voltage(description, 5.0)
    capacitance = _extract_capacitance_f(description, 100e-6)
    discharge_resistor = _extract_resistance_ohm(description, 10_000.0)
    charge_resistor = 47.0
    led_resistor = max((voltage - 2.0) / 0.01, 100.0)
    time_constant = discharge_resistor * capacitance

    ir = _base_ir(description, "capacitor_discharge_led", "Capacitor discharge LED fade")
    ir["components"] = [
        _component("V1", "voltage_source", voltage, "V", ["VCC", "0"], "supply"),
        _component("VCTRL", "control_source", "PULSE", "model", ["CTRL", "0"], "switch_control"),
        _component("S1", "switch", "momentary", "model", ["VCC", "CHARGE", "CTRL", "0"], "charge_switch"),
        _component("RCHG", "resistor", charge_resistor, "ohm", ["CHARGE", "CAP"], "charge_resistor"),
        _component("C1", "capacitor", capacitance, "F", ["CAP", "0"], "storage_capacitor"),
        _component("RDIS", "resistor", round(discharge_resistor, 2), "ohm", ["CAP", "0"], "discharge_resistor"),
        _component("RLED", "resistor", round(led_resistor, 2), "ohm", ["CAP", "LED_A"], "led_resistor"),
        _component("D1", "led", 2.0, "Vf", ["LED_A", "0"], "indicator"),
    ]
    ir["constraints"] = {
        "supply_voltage_v": voltage,
        "capacitance_f": capacitance,
        "discharge_resistance_ohm": discharge_resistor,
        "time_constant_s": time_constant,
        "button_press_s": max(0.2, min(time_constant * 0.5, 1.0)),
    }
    ir["source"]["rationale"].append("Modeled a momentary charge switch followed by RC discharge through a bleed resistor and LED branch.")
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
        _component("U1", "ne555", "NE555", "model", ["0", "THRESH", "OUT", "VCC", "CTRL", "THRESH", "DISCH", "VCC"], "timer"),
        _component("R1", "resistor", round(r1, 2), "ohm", ["VCC", "DISCH"], "timing_ra"),
        _component("R2", "resistor", round(r2, 2), "ohm", ["DISCH", "THRESH"], "timing_rb"),
        _component("C1", "capacitor", c_timing, "F", ["THRESH", "0"], "timing_capacitor"),
        _component("C2", "capacitor", 10e-9, "F", ["CTRL", "0"], "control_capacitor"),
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


def _has_any(text: str, keywords: List[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _mentions_led(text: str) -> bool:
    return bool(re.search(r"\bleds?\b", text)) or "light emitting diode" in text


def _automatic_watering_controller_ir(description: str) -> Dict[str, Any]:
    voltage = _extract_voltage(description, 12.0)

    ir = _base_ir(description, "generic_circuit", "Automatic plant watering controller")
    ir["components"] = [
        _component("V1", "voltage_source", voltage, "V", ["VCC", "0"], "supply"),
        _component("J1", "connector", "soil_moisture_sensor", "module", ["VCC", "SENSE", "0"], "sensor_connector"),
        _component("R1", "resistor", 10_000.0, "ohm", ["VCC", "SENSE"], "sensor_pullup"),
        _component("C1", "capacitor", 100e-9, "F", ["SENSE", "0"], "sensor_filter"),
        _component("R2", "resistor", 47_000.0, "ohm", ["VCC", "THRESH"], "threshold_high"),
        _component("R3", "resistor", 47_000.0, "ohm", ["THRESH", "0"], "threshold_low"),
        _component("U1", "comparator", "LM393", "model", ["SENSE", "THRESH", "CTRL", "VCC", "0"], "controller"),
        _component("R4", "resistor", 10_000.0, "ohm", ["VCC", "CTRL"], "control_pullup"),
        _component("R5", "resistor", 220.0, "ohm", ["CTRL", "GATE"], "gate_resistor"),
        _component("R6", "resistor", 100_000.0, "ohm", ["GATE", "0"], "gate_pulldown"),
        _component("Q1", "nmos", "logic_level_nmos", "model", ["PUMP_NEG", "GATE", "0"], "low_side_switch"),
        _component("M1", "motor", "12V_water_pump", "model", ["VCC", "PUMP_NEG"], "pump"),
        _component("D1", "diode", "1N5819", "model", ["PUMP_NEG", "VCC"], "flyback_diode"),
        _component("R7", "resistor", 1000.0, "ohm", ["CTRL", "LED_A"], "indicator_resistor"),
        _component("D2", "led", 2.0, "Vf", ["LED_A", "0"], "indicator"),
        _component("J2", "connector", "pump_output", "terminal", ["VCC", "PUMP_NEG"], "actuator_connector"),
    ]
    ir["constraints"] = {
        "supply_voltage_v": voltage,
        "conceptual_only": True,
        "simulation_available": False,
        "actuator": "water_pump",
    }
    ir["source"]["rationale"].extend([
        "Mapped the request to a sensor-threshold-controller-actuator circuit.",
        "Used a soil moisture sensor input, comparator threshold stage, and low-side MOSFET pump driver with flyback protection.",
    ])
    ir["warnings"].extend([
        "Generic circuit draft: review component ratings, isolation, waterproofing, and pump current before building.",
        "Simulation is not available for this mixed sensor/controller/actuator draft.",
    ])
    ir["nets"] = _nets_from_components(ir["components"])
    return ir


def _generic_control_circuit_ir(description: str) -> Dict[str, Any]:
    lower = description.lower()
    voltage = _extract_voltage(description, 12.0 if _has_any(lower, ["motor", "pump", "fan"]) else 5.0)
    title = description.strip()
    if not title or len(title) > 72:
        title = "Natural-language circuit draft"

    ir = _base_ir(description, "generic_circuit", title)
    ir["components"] = [
        _component("V1", "voltage_source", voltage, "V", ["VCC", "0"], "supply"),
        _component("J1", "connector", "input_sensor_or_signal", "terminal", ["VCC", "IN", "0"], "input_connector"),
        _component("R1", "resistor", 10_000.0, "ohm", ["VCC", "IN"], "input_bias"),
        _component("C1", "capacitor", 100e-9, "F", ["IN", "0"], "input_filter"),
        _component("U1", "controller_ic", "generic_controller", "model", ["IN", "CTRL", "VCC", "0"], "controller"),
        _component("R2", "resistor", 330.0, "ohm", ["CTRL", "GATE"], "driver_resistor"),
        _component("R3", "resistor", 100_000.0, "ohm", ["GATE", "0"], "driver_pulldown"),
        _component("Q1", "nmos", "logic_level_nmos", "model", ["LOAD_NEG", "GATE", "0"], "low_side_switch"),
        _component("J2", "connector", "load_output", "terminal", ["VCC", "LOAD_NEG"], "load_connector"),
        _component("D1", "diode", "1N5819", "model", ["LOAD_NEG", "VCC"], "flyback_or_clamp"),
        _component("R4", "resistor", 1000.0, "ohm", ["CTRL", "LED_A"], "indicator_resistor"),
        _component("D2", "led", 2.0, "Vf", ["LED_A", "0"], "indicator"),
    ]
    ir["constraints"] = {
        "supply_voltage_v": voltage,
        "conceptual_only": True,
        "simulation_available": False,
    }
    ir["source"]["rationale"].extend([
        "Created a generic input-controller-driver-load topology because the request does not match a fixed template.",
        "Kept the draft component-level so it can be inspected, edited, and turned into a detailed design.",
    ])
    ir["warnings"].extend([
        "Generic circuit draft: verify topology, values, device ratings, and safety requirements before use.",
        "Simulation is not available for arbitrary mixed-signal drafts.",
    ])
    ir["nets"] = _nets_from_components(ir["components"])
    return ir


def _generic_circuit_ir(description: str) -> Dict[str, Any]:
    lower = description.lower()
    watering_keywords = [
        "watering",
        "irrigation",
        "plant",
        "soil",
        "moisture",
        "water pump",
        "\u6d47\u82b1",
        "\u704c\u6e89",
        "\u571f\u58e4",
        "\u6e7f\u5ea6",
        "\u6c34\u6cf5",
    ]
    if _has_any(lower, watering_keywords):
        return _automatic_watering_controller_ir(description)
    return _generic_control_circuit_ir(description)


def parse_description_to_ir(description: str) -> Dict[str, Any]:
    """Parse a natural-language request into a constrained CircuitIR."""
    text = description.strip()
    lower = text.lower()
    has_capacitor = (
        "capacitor" in lower
        or "capacitance" in lower
        or "电容" in lower
        or re.search(r"\d+(?:\.\d+)?\s*(pf|nf|uf|mf|f)(?![a-zA-Z])", lower)
    )
    has_discharge_behavior = (
        "discharge" in lower
        or "fade" in lower
        or "delay" in lower
        or "放电" in lower
        or "逐渐" in lower
        or "延时" in lower
        or "熄灭" in lower
    )

    if not text:
        return unsupported_ir(description, "Description is empty.")

    if "555" in lower or "timer" in lower or "blinker" in lower or "blink" in lower:
        return _timer_555_ir(text)
    if has_capacitor and (has_discharge_behavior or _mentions_led(lower)):
        return _capacitor_discharge_led_ir(text)
    if "low-pass" in lower or "low pass" in lower or ("filter" in lower and "high" not in lower):
        return _rc_filter_ir(text)
    if "op-amp" in lower or "op amp" in lower or "amplifier" in lower or "gain" in lower:
        non_inverting = "non-inverting" in lower or "non inverting" in lower or "buffer" in lower
        return _opamp_ir(text, non_inverting)
    if _mentions_led(lower):
        return _led_ir(text)

    return _generic_circuit_ir(text)


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
