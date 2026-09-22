"""Unit tests for power_on.py pure logic (no ngspice needed)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from power_on import (  # noqa: E402
    _classify_transient,
    _driver_excluded,
    _ref_transient_modelable,
)

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


def test_transient_modelable_requires_timer_types():
    ir = {
        "components": [
            {"ref": "U1", "type": "ne555", "nodes": []},
            {"ref": "U9", "type": "mcu", "nodes": []},
            {"ref": "U2", "type": "comparator", "nodes": []},
        ],
    }
    assert _ref_transient_modelable(ir, ["U1"]) is True
    assert _ref_transient_modelable(ir, ["U9"]) is False
    assert _ref_transient_modelable(ir, ["U1", "U9"]) is False
    assert _ref_transient_modelable(ir, ["MISSING"]) is False


def test_classify_blinking_led():
    # uniform 1 Hz blink sampled at dt=1/6s; duty/freq must come from
    # edge-bounded segments, not raw point counting
    times = [i / 6.0 for i in range(14)]
    flags = [False] * 2 + [True] * 3 + [False] * 3 + [True] * 3 + [False] * 3
    e = _classify_transient(times, flags)
    assert e["verdict"].startswith("瞬态上电后周期动作"), e
    assert "1.00Hz" in e["verdict"], e
    assert e["on_fraction"] == 0.5, e  # steady duty, not the raw 6/14


def test_classify_skips_poweron_startpulse_and_tail():
    # real 555 shape: first ON runs 1.58x long (cap charges from 0 V) and
    # the window tail clips the last OFF; steady duty/freq must stay ~50%/1Hz
    dt = 0.01

    def seg(state, secs):
        return [state] * round(secs / dt)

    flags = (seg(True, 0.80) + seg(False, 0.51) + seg(True, 0.50)
             + seg(False, 0.51) + seg(True, 0.50) + seg(False, 0.30))
    times = [i * dt for i in range(len(flags))]
    e = _classify_transient(times, flags)
    assert e["verdict"].startswith("瞬态上电后周期动作"), e
    assert abs(e["on_fraction"] - 0.5) < 0.03, e
    assert abs(e["freq_hz"] - 1.0) < 0.05, e


def test_classify_single_pulse_is_not_periodic():
    times = [i * 0.125 for i in range(16)]
    flags = [False] * 4 + [True] * 4 + [False] * 8
    e = _classify_transient(times, flags)
    assert e["verdict"] == "瞬态上电后短暂动作后停止", e
    assert e["freq_hz"] == 0.0, e


def test_classify_steady_and_dead():
    assert _classify_transient([i * 0.2 for i in range(10)], [True] * 10)["verdict"].startswith("瞬态上电后持续动作")
    assert _classify_transient([i * 0.2 for i in range(10)], [False] * 10)["verdict"].startswith("瞬态上电后仍未动作")


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
