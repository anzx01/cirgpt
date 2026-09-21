"""Unit tests for power_on.py pure logic (no ngspice needed)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from power_on import _driver_excluded  # noqa: E402

# 555 blinker shape: the LED hangs off the timer's OUT net through R3.
BLINKER = {
    "components": [
        {"ref": "U1", "type": "ne555", "nodes": ["0", "THRESH", "OUT", "VCC", "CTRL", "THRESH", "DISCH", "VCC"]},
        {"ref": "R3", "type": "resistor", "nodes": ["OUT", "LED_A"]},
        {"ref": "D1", "type": "led", "nodes": ["LED_A", "0"]},
        {"ref": "V1", "type": "voltage_source", "nodes": ["VCC", "0"]},
    ],
}

LED_ACT = {"ref": "D1", "type": "led", "nodes": ["LED_A", "0"]}


def test_blinker_led_blocked_by_excluded_timer():
    got = _driver_excluded(BLINKER, LED_ACT, {"U1"})
    # walk: LED_A -> R3 -> OUT -> U1 (excluded); VCC never reached because
    # OUT's only other member is the excluded timer
    assert got == "U1", got


def test_included_timer_counts_as_driver():
    assert _driver_excluded(BLINKER, LED_ACT, set()) is None


def test_comparator_drive_survives_unrelated_exclusion():
    ir = {
        "components": [
            {"ref": "U2", "type": "comparator", "nodes": ["A", "B", "OUT", "VCC", "0"]},
            {"ref": "D1", "type": "led", "nodes": ["OUT", "0"]},
            {"ref": "U9", "type": "mcu", "nodes": ["X", "Y"]},
        ],
    }
    act = {"ref": "D1", "type": "led", "nodes": ["OUT", "0"]}
    assert _driver_excluded(ir, act, {"U9"}) is None


def test_led_directly_on_excluded_mcu_pin():
    ir = {
        "components": [
            {"ref": "U9", "type": "mcu", "nodes": ["IO1", "0"]},
            {"ref": "D1", "type": "led", "nodes": ["IO1", "0"]},
        ],
    }
    act = {"ref": "D1", "type": "led", "nodes": ["IO1", "0"]}
    assert _driver_excluded(ir, act, {"U9"}) == "U9"


def test_supply_through_resistor_drives():
    ir = {
        "components": [
            {"ref": "V1", "type": "voltage_source", "nodes": ["VCC", "0"]},
            {"ref": "R1", "type": "resistor", "nodes": ["VCC", "N1"]},
            {"ref": "D1", "type": "led", "nodes": ["N1", "0"]},
        ],
    }
    act = {"ref": "D1", "type": "led", "nodes": ["N1", "0"]}
    assert _driver_excluded(ir, act, set()) is None


def test_all_passive_chain_with_no_driver_is_not_excluded_fault():
    # nothing excluded, nothing active: not the exclusion mechanism's call
    ir = {
        "components": [
            {"ref": "R1", "type": "resistor", "nodes": ["N1", "N2"]},
            {"ref": "D1", "type": "led", "nodes": ["N1", "0"]},
        ],
    }
    act = {"ref": "D1", "type": "led", "nodes": ["N1", "0"]}
    assert _driver_excluded(ir, act, set()) is None


def main() -> int:
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                print(f"FAIL {name}: {exc}")
                failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
