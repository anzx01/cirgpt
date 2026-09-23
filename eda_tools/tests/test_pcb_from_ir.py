"""
Offline tests: the PCB preview is built from the CircuitIR (physical view),
never from the SPICE netlist — whose registry parts are engineering models
(ideal V/I sources) that must not appear as board parts.

Run with:
    cd eda_tools
    python -m tests.test_pcb_from_ir
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kicad.pcb_generator import generate_pcb  # noqa: E402

IR = {
    "components": [
        {"ref": "J1", "type": "usb_c_power_connector",
         "model": "USB_C_Receptacle_USB2.0",
         "nodes": ["VBUS", "CC1", "CC2", "D+", "D-", "GND", "SHIELD"]},
        {"ref": "U1", "type": "ldo_ams1117", "model": "AMS1117-3.3",
         "nodes": ["VI", "VO", "GND"]},
        {"ref": "U2", "type": "mcu_module_esp32c3", "model": "ESP32-C3",
         "nodes": ["3V3", "GND", "EN", "IO2"]},
        {"ref": "R1", "type": "resistor", "value": "5.1k", "nodes": ["CC1", "0"]},
        {"ref": "D1", "type": "led", "value": "red", "nodes": ["IO2", "R4.1"]},
        {"ref": "R4", "type": "resistor", "value": "330", "nodes": ["R4.1", "0"]},
    ],
    "nets": [
        {"name": "VBUS", "connections": ["J1.VBUS", "U1.VI"]},
        {"name": "3V3", "connections": ["U1.VO", "U2.3V3"]},
        {"name": "0", "connections": ["J1.GND", "U1.GND", "U2.GND", "R1.2", "R4.2"]},
        {"name": "CC1", "connections": ["J1.CC1", "R1.1"]},
        {"name": "IO2", "connections": ["U2.IO2", "D1.1"]},
        {"name": "LED_CATHODE", "connections": ["D1.2", "R4.1"]},
    ],
}


def test_board_uses_real_parts_not_engineering_models():
    # the netlist view literally contains SPICE stand-ins; the board must not
    layout = generate_pcb(
        "V1 VBUS 0 DC 5\nV2 3V3 0 DC 3.3\nI1 0 3V3 DC 0.05", circuit_ir=IR
    )
    names = {c["name"] for c in layout["components"]}
    assert {"J1", "U1", "U2", "R1", "D1", "R4"} <= names, names
    assert not any(n[0] in "VI" and n[1:].isdigit() for n in names), names


def test_registry_footprints_and_pad_nets():
    layout = generate_pcb("", circuit_ir=IR)
    comps = {c["name"]: c for c in layout["components"]}
    assert comps["J1"]["footprint"].startswith("Connector_USB:USB_C_Receptacle_HRO")
    assert comps["U1"]["footprint"].startswith("Package_TO_SOT_SMD:SOT-223")
    assert comps["U2"]["footprint"].startswith("Package_DFN_QFN:QFN-32")
    # AMS1117 pads by registry numbering: 1=GND, 2=VO (tab), 3=VI
    assert comps["U1"]["nodes"] == ["0", "3V3", "VBUS"], comps["U1"]["nodes"]
    # unrouted pads get unique NC names so no phantom nets appear
    u2_nc = [n for n in comps["U2"]["nodes"] if n.startswith("NC$")]
    assert len(u2_nc) >= 8  # spare GPIOs on the 32-pad footprint


def test_multiple_power_rails_get_separate_buses():
    layout = generate_pcb("", circuit_ir=IR)
    tracks = layout["layout"]["tracks"]
    buses = {(t["net"], round(t["start"]["y"], 2)) for t in tracks if t.get("type") == "bus"}
    rail_nets = {n for n, _y in buses}
    assert "3V3" in rail_nets and "VBUS" in rail_nets, buses
    ys = sorted(y for n, y in buses if n in ("3V3", "VBUS"))
    assert ys[0] != ys[1], "distinct rails must never share one bus"


def main() -> int:
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"ERROR {name}: {type(exc).__name__}: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
