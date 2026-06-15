"""
Offline smoke test for the subsystem-paged renderer in eda_tools.ir_schematic.

Run with:
    cd eda_tools
    python -m tests.test_subsystem_paged_render

The test does not touch KiCad or SKiDL. It feeds a hand-crafted v2 free-form
CircuitIR (with subsystems) and a legacy IR (without subsystems) into
generate_ir_schematic_svg(), then asserts the expected shape of the output.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ir_schematic import generate_ir_schematic_svg  # noqa: E402


SAMPLE_V2_IR = {
    "schema_version": "1.0",
    "supported": True,
    "circuit_type": "track_circuit_tester_receiver",
    "title": "Track circuit tester receiver front end",
    "description": "25 Hz phase-sensitive track circuit receiver",
    "domain": "railway",
    "compliance_standards": ["EN 50129", "TB/T 3202"],
    "operating_envelope": {"temp_min_c": -25, "temp_max_c": 70, "ip_rating": "IP54"},
    "open_questions": ["Confirm maximum sustained field voltage"],
    "components": [
        {"ref": "V1", "type": "voltage_source", "value": 12, "unit": "V",
         "nodes": ["VCC", "0"], "role": "supply", "subsystem": "power_input"},
        {"ref": "F1", "type": "fuse", "value": "500mA", "unit": "model",
         "nodes": ["VCC", "VDD"], "role": "protection", "subsystem": "protection"},
        {"ref": "U1", "type": "isolated_amplifier", "value": "ISO224", "unit": "model",
         "nodes": ["INA", "OUTA", "VDD", "0"], "role": "isolation", "subsystem": "isolation"},
        {"ref": "R1", "type": "resistor", "value": 10000, "unit": "ohm",
         "nodes": ["INA", "0"], "role": "amplifier", "subsystem": "signal_chain"},
        {"ref": "C1", "type": "capacitor", "value": 1e-7, "unit": "F",
         "nodes": ["INA", "0"], "role": "filter", "subsystem": "signal_chain"},
        {"ref": "U2", "type": "microcontroller", "value": "STM32H7", "unit": "model",
         "nodes": ["OUTA", "VCC", "0"], "role": "controller", "subsystem": "control"},
        {"ref": "M1", "type": "motor", "value": "pump", "unit": "model",
         "nodes": ["VCC", "OUTB"], "role": "load", "subsystem": "load_output"},
        {"ref": "D1", "type": "led", "value": 2, "unit": "Vf",
         "nodes": ["OUTC", "0"], "role": "indicator", "subsystem": "hmi"},
    ],
    "nets": [
        {"name": "VCC", "connections": ["V1.1", "F1.1", "U1.3", "U2.2", "M1.1"]},
        {"name": "VDD", "connections": ["F1.2", "U1.3"]},
        {"name": "0", "connections": ["V1.2", "U1.4", "R1.2", "C1.2", "U2.3", "D1.2"]},
        {"name": "INA", "connections": ["U1.1", "R1.1", "C1.1"]},
        {"name": "OUTA", "connections": ["U1.2", "U2.1"]},
    ],
    "subsystems": [
        {"name": "power_input", "purpose": "DC supply", "component_refs": ["V1"]},
        {"name": "protection", "purpose": "Fuse", "component_refs": ["F1"]},
        {"name": "isolation", "purpose": "5 kV barrier", "component_refs": ["U1"]},
        {"name": "signal_chain", "purpose": "Filter + buffer", "component_refs": ["R1", "C1"]},
        {"name": "control", "purpose": "MCU", "component_refs": ["U2"]},
        {"name": "load_output", "purpose": "Pump driver", "component_refs": ["M1"]},
        {"name": "hmi", "purpose": "Indicator LED", "component_refs": ["D1"]},
    ],
    "source": {"mode": "deepseek", "prompt_version": "v2_freeform", "model": "deepseek-v4-flash"},
    "warnings": [],
}

LEGACY_IR = {
    "schema_version": "1.0",
    "supported": True,
    "circuit_type": "led_current_limiter",
    "title": "LED limiter",
    "description": "5 V LED",
    "components": [
        {"ref": "V1", "type": "voltage_source", "value": 5, "unit": "V",
         "nodes": ["VCC", "0"], "role": "supply"},
        {"ref": "R1", "type": "resistor", "value": 150, "unit": "ohm",
         "nodes": ["VCC", "LED_A"], "role": "current_limit"},
        {"ref": "D1", "type": "led", "value": 2, "unit": "Vf",
         "nodes": ["LED_A", "0"], "role": "indicator"},
    ],
    "nets": [],
    "source": {"mode": "rules"},
    "warnings": [],
}


def _print_summary(label: str, value) -> None:
    if isinstance(value, dict):
        keys = list(value.keys())
        page_count = len(value.get("pages") or [])
        print(f"OK   {label} -> dict, keys={keys}, pages={page_count}")
    else:
        print(f"OK   {label} -> str ({len(value)} chars)")


def main() -> int:
    failures = 0

    try:
        result = generate_ir_schematic_svg(SAMPLE_V2_IR)
    except Exception as exc:  # noqa: BLE001
        print("FAIL v2 render raised:", exc)
        traceback.print_exc()
        return 1

    if not isinstance(result, dict):
        print("FAIL v2 expected dict, got", type(result).__name__)
        failures += 1
    else:
        _print_summary("v2 subsystem-paged", result)
        if result.get("layout") != "subsystem-paged":
            print("FAIL v2 layout tag missing or wrong")
            failures += 1
        pages = result.get("pages") or []
        if len(pages) < 2:
            print("FAIL v2 expected at least 2 pages (subsystems + overview)")
            failures += 1
        last = pages[-1] if pages else {}
        if last.get("subsystem") != "_overview":
            print("FAIL v2 final page should be _overview")
            failures += 1
        if not any(page.get("svg", "").startswith("<?xml") for page in pages):
            print("FAIL v2 pages should each contain an SVG body")
            failures += 1
        summary = result.get("summary") or {}
        if summary.get("prompt_version") != "v2_freeform":
            print("FAIL v2 summary.prompt_version should be 'v2_freeform'")
            failures += 1
        if summary.get("total_components", 0) != len(SAMPLE_V2_IR["components"]):
            print(f"FAIL v2 total_components={summary.get('total_components')} "
                  f"expected {len(SAMPLE_V2_IR['components'])}")
            failures += 1

    try:
        legacy = generate_ir_schematic_svg(LEGACY_IR)
    except Exception as exc:  # noqa: BLE001
        print("FAIL legacy render raised:", exc)
        traceback.print_exc()
        return 1
    if not isinstance(legacy, str):
        print("FAIL legacy expected str, got", type(legacy).__name__)
        failures += 1
    elif "<svg" not in legacy:
        print("FAIL legacy output is not SVG")
        failures += 1
    else:
        _print_summary("legacy led_current_limiter", legacy)

    if failures:
        print(f"\n{failures} failure(s).")
        return 1
    print("\nAll subsystem-paged smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
