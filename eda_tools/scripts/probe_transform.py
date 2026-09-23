"""Offline decision trace for the MCP schematic wiring pipeline.

Replays _expand_real_part_connections -> _pin_aliases -> _remap_power_pins ->
_plan_wire_routes against the saved .kicad_sch of a repro run, printing each
net's member resolution and where pins get lost.

Usage:
    venv/Scripts/python.exe scripts/probe_transform.py <ir.json> <file.kicad_sch>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_schematic import (  # noqa: E402
    _expand_real_part_connections,
    _pin_aliases,
    _pin_positions_from_sch,
    _pin_types_on_sheet,
    _plan_wire_routes,
    _remap_power_pins,
    _rail_symbol,
    _is_gnd,
    _symbol_for,
)


def main() -> None:
    ir = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    sch_text = Path(sys.argv[2]).read_text(encoding="utf-8", errors="replace")

    ir2, expand_drops = _expand_real_part_connections(ir)
    print("== expand_real_part_connections drops:", sorted(expand_drops))

    components = [c for c in ir2.get("components", []) if isinstance(c, dict)]
    placed = []
    for comp in components:
        lib_sym = _symbol_for(comp)
        if lib_sym:
            placed.append((comp, lib_sym[0], lib_sym[1]))
    placed_refs = {str(c.get("ref")) for c, _l, _s in placed}

    pin_positions = _pin_positions_from_sch(sch_text)
    pin_types = _pin_types_on_sheet(sch_text)
    aliases = _pin_aliases(placed, ir2.get("nets") or [], pin_positions)
    print("== aliases:", aliases)

    wired_nets, gate_dropped = _remap_power_pins(
        ir2.get("nets") or [], pin_types, pin_positions
    )
    print("== remap gate_dropped:", sorted(gate_dropped))

    xs = [p[0] for p in pin_positions.values()]
    columns_x = sorted({round(x, 0) for x in xs})
    plans = _plan_wire_routes(wired_nets, placed_refs, aliases, pin_positions, columns_x)

    print("\n== per-net trace")
    for net in wired_nets:
        name = str(net.get("name") or "")
        row = []
        for conn in net.get("connections") or []:
            ref, _, pin = str(conn).rpartition(".")
            pos = pin_positions.get((ref, pin)) or pin_positions.get(
                (ref, aliases.get(ref, {}).get(pin, pin))
            )
            row.append(f"{conn}@{pos}")
        kind = "WIRE" if name in plans else (
            "RAIL" if (_is_gnd(name) or _rail_symbol(name)) else "LABEL"
        )
        print(f"[{kind}] {name}: {row}")

    print("\n== plans:")
    for name, p in plans.items():
        print(f"  {name}: segs={len(p['segments'])} junctions={len(p['junctions'])}")


if __name__ == "__main__":
    main()
