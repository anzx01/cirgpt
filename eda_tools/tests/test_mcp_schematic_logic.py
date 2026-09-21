"""
Offline tests for the KiCad MCP schematic builder's pure logic: schematic
file parsing (pin geometry) and the connectivity validation gate.

Run with:
    cd eda_tools
    python -m tests.test_mcp_schematic_logic

Does not launch the MCP server or kicad-cli.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_schematic import (  # noqa: E402
    _connectivity_matches,
    _fmt_value,
    _label_stub_len,
    _parse_netlist_nets,
    _pin_aliases,
    _pin_offsets_from_lib_symbols,
    _pin_positions_from_sch,
    _plan_wire_routes,
    _safe_label,
    _segs_conflict,
    _symbol_for,
    _symbol_units_from_lib,
)

SCH = """(kicad_sch (version 20250114)
  (lib_symbols
    (symbol "Device:R"
      (symbol "R_0_1" (polyline (pts (xy -2.54 0) (xy 2.54 0))))
      (symbol "R_1_1"
        (pin passive line (at 0 3.81 270) (length 1.27)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27))))
        )
        (pin passive line (at 0 -3.81 90) (length 1.27)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "2" (effects (font (size 1.27 1.27))))
        )
      )
    )
  )
  (symbol
    (lib_id "Device:R")
    (at 100 100 0)
    (unit 1)
    (property "Reference" "R1" (at 100 95 0))
    (property "Value" "330" (at 100 105 0))
    (pin "1" (uuid "00000000-0000-0000-0000-000000000001"))
    (pin "2" (uuid "00000000-0000-0000-0000-000000000002"))
  )
)
"""

NETLIST = """(export (version "E")
  (components)
  (nets
    (net (code "1") (name "/N1") (class "Default")
      (node (ref "R1") (pin "2") (pintype "passive"))
      (node (ref "D1") (pin "2") (pintype "passive"))
    )
    (net (code "2") (name "GND") (class "Default")
      (node (ref "D1") (pin "1") (pintype "passive"))
      (node (ref "#PWR01") (pin "1") (pintype "power_in"))
    )
  )
)
"""

IR_NETS = [
    {"name": "N1", "connections": ["R1.2", "D1.2"]},
    {"name": "GND", "connections": ["D1.1"]},
]


def test_pin_geometry():
    libs = _pin_offsets_from_lib_symbols(SCH)
    # multi-unit shape: {lib_id: {unit: {pin number: (dx, dy)}}}; a resistor
    # has no root-shared pins, so only unit 1 is present
    assert libs["Device:R"] == {1: {"1": (0.0, 3.81), "2": (0.0, -3.81)}}, libs
    pos = _pin_positions_from_sch(SCH)
    # lib pins are y-up, sheet is y-down: pin1 (0,3.81) lands above (100,100)
    assert pos[("R1", "1")] == (100.0, 96.19), pos
    assert pos[("R1", "2")] == (100.0, 103.81), pos


def test_netlist_parsing():
    nets = _parse_netlist_nets(NETLIST)
    by_name = dict(nets)
    assert by_name["/N1"] == {("R1", "2"), ("D1", "2")}, by_name
    assert ("#PWR01", "1") in by_name["GND"]


def test_validation_gate():
    pos = {("R1", "1"): (0.0, 0.0), ("R1", "2"): (1.0, 1.0), ("D1", "1"): (2.0, 2.0), ("D1", "2"): (3.0, 3.0)}
    ok = _connectivity_matches(
        IR_NETS, {"R1", "D1"}, _parse_netlist_nets(NETLIST), pos, {}, set()
    )
    assert ok, "matching connectivity must pass"

    broken = [
        {"name": "N1", "connections": ["R1.2", "D1.1"]},  # D1.1 also in GND
        {"name": "GND", "connections": ["D1.1"]},
    ]
    assert not _connectivity_matches(
        broken, {"R1", "D1"}, _parse_netlist_nets(NETLIST), pos, {}, set()
    ), "mismatched connectivity must be rejected"

    missing = [{"name": "N1", "connections": ["R1.2", "D1.2", "D1.9"]}]
    assert not _connectivity_matches(
        missing, {"R1", "D1"}, _parse_netlist_nets(NETLIST), pos, {}, set()
    ), "a pin absent from the export must fail its IR net"

    tolerated = [{"name": "N1", "connections": ["R1.2", "D1.2", "D1.9"]}]
    assert _connectivity_matches(
        tolerated, {"R1", "D1"}, _parse_netlist_nets(NETLIST), pos, {}, {("D1", "9")}
    ), "a pin dropped as absent from the symbol must not fail the gate"


def test_pin_aliases_for_letter_pinned_transistor():
    placed = [
        (
            {
                "ref": "Q1",
                "type": "mosfet",
                "value": "IRLZ44N",
                "nodes": ["PUMP_GATE", "0", "PUMP_NEG"],
            },
            "Device",
            "Q_NMOS",
        )
    ]
    nets = [
        {"name": "PUMP_GATE", "connections": ["Q1.1", "R4.1", "U2.4"]},
        {"name": "0", "connections": ["Q1.2"]},
        {"name": "PUMP_NEG", "connections": ["Q1.3", "J3.2"]},
    ]
    pos = {("Q1", "G"): (0.0, 0.0), ("Q1", "S"): (1.0, 0.0), ("Q1", "D"): (2.0, 0.0)}
    aliases = _pin_aliases(placed, nets, pos)
    assert aliases.get("Q1") == {"1": "G", "2": "S", "3": "D"}, aliases


def test_value_formatting():
    assert _fmt_value({"value": 16000000, "unit": "Hz"}) == "16MHz"
    assert _fmt_value({"value": 220, "unit": "V"}) == "220V"
    assert _fmt_value({"value": 100e-9, "unit": "F"}) == "100nF"
    assert _fmt_value({"type": "resistor", "value": 10000}) == "10k"
    assert _fmt_value({"type": "capacitor", "value": 100e-6}) == "100uF"
    assert _fmt_value({"value": "IRLZ44N"}) == "IRLZ44N"
    assert _safe_label("12V in!") == "12V_in_"


def test_segment_conflict_rules():
    h = (0.0, 10.0, 20.0, 10.0)      # horizontal y=10, x 0..20
    v_mid = (10.0, 0.0, 10.0, 20.0)  # vertical x=10 crossing h mid-wire: safe
    assert not _segs_conflict(h, v_mid)
    v_tee = (5.0, 0.0, 5.0, 10.0)    # vertical ends exactly on h: T-junction
    assert _segs_conflict(h, v_tee)
    h_overlap = (15.0, 10.0, 30.0, 10.0)  # collinear overlap with h
    assert _segs_conflict(h, h_overlap)
    h_parallel = (0.0, 12.7, 20.0, 12.7)  # parallel, different row: safe
    assert not _segs_conflict(h, h_parallel)
    h_disjoint = (25.0, 10.0, 35.0, 10.0)  # collinear but disjoint
    assert not _segs_conflict(h, h_disjoint)


def test_wire_route_planning():
    # Two components in one column, one signal net between them; power nets
    # are excluded from wiring; a foreign pin sitting on the trunk path makes
    # that net fall back to labels.
    pin_positions = {
        ("R1", "1"): (50.0, 60.0),
        ("R1", "2"): (50.0, 68.0),
        ("D1", "1"): (50.0, 120.0),
        ("D1", "2"): (50.0, 128.0),
        ("U1", "1"): (50.0, 180.0),
    }
    ir_nets = [
        {"name": "VCC", "connections": ["R1.1"]},                     # power: skipped
        {"name": "N1", "connections": ["R1.2", "D1.2"]},              # wireable
        {"name": "N2", "connections": ["D1.1", "U1.1"]},              # wireable
    ]
    plans = _plan_wire_routes(ir_nets, {"R1", "D1", "U1"}, {}, pin_positions, [50.0])
    assert set(plans) == {"N1", "N2"}, plans
    n1 = plans["N1"]
    stubs = [s for s in n1["segments"] if abs(s[1] - s[3]) < 0.01]
    trunk = [s for s in n1["segments"] if abs(s[0] - s[2]) < 0.01]
    assert len(stubs) == 2 and len(trunk) == 1, n1["segments"]
    trunk_x = trunk[0][0]
    assert trunk_x != 50.0  # trunk lives in a gutter, not on the components
    assert all(s[0] == 50.0 and s[2] == trunk_x for s in stubs)
    assert len(n1["junctions"]) == 2

    # A foreign pin exactly on N1's trunk forces N1 back to labels.
    pin_positions[("X1", "1")] = (trunk_x, 100.0)
    plans2 = _plan_wire_routes(ir_nets + [{"name": "XNET", "connections": ["X1.1"]}],
                               {"R1", "D1", "U1", "X1"}, {}, pin_positions, [50.0])
    assert "N1" not in plans2, plans2.keys()


# IR type strings seen in stored designs; each must land on the KiCad symbol
# it represents, never on the generic Connector fallback (a 555 rendered as
# an 8-pin header bar instead of an IC box looked "not like a chip").
_SYMBOL_MAP_CASES = [
    ({"type": "ne555", "value": "NE555", "nodes": [str(i) for i in range(8)]}, ("Timer", "LM555xN")),
    ({"type": "555_timer", "value": "NE555", "nodes": [str(i) for i in range(8)]}, ("Timer", "LM555xN")),
    ({"type": "timer_ic", "value": "NE555", "nodes": [str(i) for i in range(8)]}, ("Timer", "LM555xN")),
    ({"type": "ideal_opamp", "value": "IDEAL", "nodes": ["a", "b", "c"]}, ("Amplifier_Operational", "LM358")),
    ({"type": "operational_amplifier", "value": "", "nodes": ["a", "b", "c"]}, ("Amplifier_Operational", "LM358")),
    ({"type": "npn_transistor", "value": "", "nodes": ["a", "b", "c"]}, ("Device", "Q_NPN")),
    ({"type": "pnp_transistor", "value": "", "nodes": ["a", "b", "c"]}, ("Device", "Q_PNP")),
    ({"type": "nmosfet", "value": "", "nodes": ["a", "b", "c"]}, ("Device", "Q_NMOS")),
    ({"type": "voltage_regulator", "value": "5", "nodes": ["a", "b", "c"]}, ("Regulator_Linear", "L7805")),
]


def test_symbol_type_coverage():
    for comp, expected in _SYMBOL_MAP_CASES:
        got = _symbol_for(comp)
        assert got == expected, f"{comp.get('type')}: {got} != {expected}"
    # unknown IC-ish types still degrade to the connector fallback
    comp = {"type": "mystery_module", "value": "MOD", "nodes": ["a", "b", "c", "d"]}
    assert _symbol_for(comp) == ("Connector_Generic", "Conn_01x04")


UNIT0_LIB = """(
  symbol "Timer:LM555xN"
  (pin power_in line (at -10.16 0 0) (length 2.54)
    (name "GND" (effects (font (size 1.27 1.27))))
    (number "1" (effects (font (size 1.27 1.27))))
  )
  (pin power_in line (at 10.16 0 180) (length 2.54)
    (name "VCC" (effects (font (size 1.27 1.27))))
    (number "8" (effects (font (size 1.27 1.27))))
  )
  (symbol "LM555xN_1_1"
    (pin input line (at -10.16 5.08 0) (length 2.54)
      (name "TRIG" (effects (font (size 1.27 1.27))))
      (number "2" (effects (font (size 1.27 1.27))))
    )
  )
)
"""


def test_unit0_pins_fold_into_unit1():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        lib_dir = Path(tmp)
        (lib_dir / "Timer.kicad_sym").write_text(UNIT0_LIB, encoding="utf-8")
        units = _symbol_units_from_lib(lib_dir, ["Timer:LM555xN"])
    # unit-0 pins (power) are common to every unit: they must ride along with
    # unit 1 instead of creating a phantom second instance to place.
    assert set(units["Timer:LM555xN"]) == {1}, units
    assert units["Timer:LM555xN"][1] == {"1", "2", "8"}, units


def test_label_stub_length_covers_text():
    # KiCad renders label text left-to-right from the anchor at any
    # rotation, so the stub must outsize the text: ~0.9x1.27mm per char
    # ("CTRL" is 3.55mm wide) plus a grid of clearance, grid-aligned.
    assert _label_stub_len("OUT") == 5.08
    assert _label_stub_len("CTRL") == 7.62
    assert _label_stub_len("THRESH") == 10.16
    # never shorter than two grids even for 1-2 char names
    assert _label_stub_len("N1") == 5.08


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
