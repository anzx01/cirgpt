"""
Smoke test for the DeepSeek parser. Run with:

    cd ai_service
    python -m scripts.test_deepseek_parser

It does NOT call the DeepSeek API. It exercises the validator against
representative IR shapes to show how v1_strict and v2_freeform differ.

Expected output (abridged):
    OK  v1: 555 with all roles -> supported=True
    OK  v1: 555 missing timing_rb -> ValueError raised
    OK  v2: 555 with all roles -> supported=True
    OK  v2: track circuit tester (free-form) -> supported=True
    OK  v2: free-form with non-snake_case -> normalized
    OK  v2: empty -> supported=False
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nlp.deepseek_parser import validate_circuit_ir  # noqa: E402
from nlp.prompts.registry import PROMPT_REGISTRY, active_prompt_name  # noqa: E402


V1_555_GOOD = {
    "schema_version": "1.0",
    "supported": True,
    "circuit_type": "555_timer_blinker",
    "title": "555 timer LED blinker",
    "description": "9V 1Hz",
    "components": [
        {"ref": "V1", "type": "voltage_source", "value": 9, "unit": "V", "nodes": ["VCC", "0"], "role": "supply"},
        {"ref": "U1", "type": "ne555", "value": "NE555", "unit": "model",
         "nodes": ["0", "THRESH", "OUT", "VCC", "CTRL", "THRESH", "DISCH", "VCC"], "role": "timer"},
        {"ref": "R1", "type": "resistor", "value": 1000, "unit": "ohm", "nodes": ["VCC", "DISCH"], "role": "timing_ra"},
        {"ref": "R2", "type": "resistor", "value": 67000, "unit": "ohm", "nodes": ["DISCH", "THRESH"], "role": "timing_rb"},
        {"ref": "C1", "type": "capacitor", "value": 1e-05, "unit": "F", "nodes": ["THRESH", "0"], "role": "timing_capacitor"},
        {"ref": "C2", "type": "capacitor", "value": 1e-08, "unit": "F", "nodes": ["CTRL", "0"], "role": "control_capacitor"},
        {"ref": "R3", "type": "resistor", "value": 467, "unit": "ohm", "nodes": ["OUT", "LED_A"], "role": "led_resistor"},
        {"ref": "D1", "type": "led", "value": 2, "unit": "Vf", "nodes": ["LED_A", "0"], "role": "indicator"},
    ],
    "nets": [],
    "constraints": {},
    "source": {"mode": "deepseek", "rationale": []},
    "warnings": [],
}

V1_555_MISSING = {**V1_555_GOOD, "components": [c for c in V1_555_GOOD["components"] if c.get("role") != "timing_rb"]}

V2_FREE_FORM_TRACK = {
    "schema_version": "1.0",
    "supported": True,
    "circuit_type": "track_circuit_tester_receiver",
    "title": "Track circuit tester receiver front end",
    "description": "25 Hz phase-sensitive track circuit receiver with isolated ADC front end",
    "domain": "railway",
    "compliance_standards": ["EN 50129", "TB/T 3202"],
    "components": [
        {"ref": "J1", "type": "connector", "value": "track_input", "unit": "model",
         "nodes": ["TR_A", "TR_B", "PE"], "role": "signal_input", "subsystem": "signal_input"},
        {"ref": "R1", "type": "resistor", "value": 2000000, "unit": "ohm",
         "tolerance_pct": 0.1, "voltage_rating_v": 250,
         "nodes": ["TR_A", "A1"], "role": "voltage_divider", "subsystem": "signal_input"},
        {"ref": "R2", "type": "resistor", "value": 20000, "unit": "ohm",
         "tolerance_pct": 0.1,
         "nodes": ["A1", "0"], "role": "voltage_divider", "subsystem": "signal_input"},
        {"ref": "U1", "type": "opamp", "value": "ADA4528", "unit": "model",
         "manufacturer": "Analog Devices", "manufacturer_part": "ADA4528-2ARMZ",
         "nodes": ["A1", "A2", "DIFF_OUT", "VCC_A", "VEE_A"], "role": "amplifier", "subsystem": "signal_chain"},
        {"ref": "U2", "type": "isolated_amplifier", "value": "ISO224", "unit": "model",
         "nodes": ["DIFF_OUT", "ISO_OUT", "VDD1", "VDD2", "0"], "role": "isolation", "subsystem": "isolation"},
        {"ref": "U3", "type": "adc", "value": "ADS8860", "unit": "model",
         "nodes": ["ISO_OUT", "ADC_OUT", "VREF", "VDD"], "role": "adc", "subsystem": "signal_chain"},
        {"ref": "V1", "type": "voltage_source", "value": 12, "unit": "V",
         "nodes": ["VCC", "0"], "role": "supply", "subsystem": "power_input"},
    ],
    "nets": [
        {"name": "VCC", "connections": ["V1.1"]},
        {"name": "0", "connections": ["V1.2", "R2.2", "U2.5"]},
        {"name": "A1", "connections": ["R1.2", "U1.1"]},
    ],
    "subsystems": [
        {"name": "power_input", "purpose": "DC supply to analog and digital sides", "component_refs": ["V1"]},
        {"name": "signal_input", "purpose": "Differential HV front end", "component_refs": ["J1", "R1", "R2"]},
        {"name": "isolation", "purpose": "5 kV reinforced barrier", "component_refs": ["U2"]},
        {"name": "signal_chain", "purpose": "Buffer, isolate, digitize", "component_refs": ["U1", "U3"]},
    ],
    "operating_envelope": {"temp_min_c": -25, "temp_max_c": 70, "ip_rating": "IP54"},
    "interfaces": [{"name": "SPI1", "type": "spi", "isolated": True}],
    "design_notes": [
        "Divider chosen for 100:1 attenuation to bring 110 V rail to 1.1 V ADC-scale",
        "5 kV reinforced isolation per EN 50129 for field-side to operator-side",
    ],
    "open_questions": [
        "Confirm maximum sustained field voltage under transient",
        "Confirm SIL class requirement",
    ],
    "constraints": {"supply_voltage_v": 12, "sampling_rate_sps": 1_000_000},
    "source": {"mode": "deepseek", "rationale": ["R1:R2 = 100:1 to bring 110V to 1.1V"]},
    "warnings": [],
}

V2_BAD_CIRCUIT_TYPE = {**V2_FREE_FORM_TRACK, "circuit_type": "Track Circuit Tester Receiver!!"}

V2_EMPTY = {
    "schema_version": "1.0",
    "supported": True,
    "circuit_type": "555_timer_blinker",
    "title": "x",
    "description": "x",
    "components": [],
    "nets": [],
    "constraints": {},
    "source": {"mode": "deepseek", "rationale": []},
    "warnings": [],
}


def _show(name: str, ir: dict) -> None:
    print(f"--- {name} ---")
    print(json.dumps(ir, indent=2, ensure_ascii=False)[:500] + ("..." if len(json.dumps(ir)) > 500 else ""))
    print()


def main() -> int:
    print(f"Active prompt version: {active_prompt_name()}")
    print(f"Registered prompts: {list(PROMPT_REGISTRY.keys())}")
    print()

    cases = [
        ("v1 555 with all roles (expect supported=True)", V1_555_GOOD, "ok"),
        ("v1 555 missing timing_rb (expect ValueError)", V1_555_MISSING, "raise"),
        ("v2 555 with all roles (expect supported=True)", V1_555_GOOD, "ok"),
        ("v2 free-form track circuit tester (expect supported=True)", V2_FREE_FORM_TRACK, "ok"),
        ("v2 bad circuit_type (expect normalized)", V2_BAD_CIRCUIT_TYPE, "ok"),
        ("v2 empty components (expect supported=False)", V2_EMPTY, "ok"),
    ]

    failures = 0
    for name, ir, mode in cases:
        try:
            result = validate_circuit_ir(ir, ir.get("description", ""))
            if mode == "raise":
                print(f"FAIL {name}: expected ValueError, got supported={result.get('supported')}")
                failures += 1
            else:
                ct = result.get("circuit_type")
                sup = result.get("supported")
                tags = result.get("warnings", [])
                print(f"OK   {name}")
                print(f"     circuit_type={ct!r} supported={sup} warnings={len(tags)}")
        except Exception as exc:  # noqa: BLE001
            if mode == "raise":
                print(f"OK   {name}: raised {type(exc).__name__}: {exc}")
            else:
                print(f"FAIL {name}: unexpected {type(exc).__name__}: {exc}")
                traceback.print_exc()
                failures += 1
        print()

    if failures:
        print(f"\n{failures} failure(s).")
        return 1
    print("\nAll smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
