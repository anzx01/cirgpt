"""Compare the generated sheet netlist (.net) against the design's CircuitIR nets.

Usage:
    venv/Scripts/python.exe scripts/net_audit.py <dir-with-.net-and-ir.json>
    venv/Scripts/python.exe scripts/net_audit.py <file.net> <ir.json>

Prints, per IR net: which of its ref.pin connections landed on the same sheet
net, which are missing, and which sheet nets have no IR counterpart.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def parse_net(path: Path):
    text = path.read_text(encoding="utf-8")
def parse_net(path: Path):
    text = path.read_text(encoding="utf-8")
    nets = {}
    cur = None
    pend_ref = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("(net"):
            cur = None
            pend_ref = None
            continue
        m = re.match(r'\(name "([^"]*)"\)', s)
        if m and cur is None and line.startswith("\t\t\t"):
            cur = m.group(1)
            nets[cur] = set()
            continue
        if cur is None:
            continue
        m = re.match(r'\(ref "([^"]+)"\)', s)
        if m:
            pend_ref = m.group(1)
            continue
        m = re.match(r'\(pin "([^"]+)"\)', s)
        if m and pend_ref:
            nets[cur].add((pend_ref, m.group(1)))
            pend_ref = None
    return {k: v for k, v in nets.items() if v}
    return nets


def load_ir(path: Path):
    ir = json.loads(path.read_text(encoding="utf-8"))
    return ir


def expand_pins(ir: dict):
    """IR uses semantic pin names for registry parts; the sheet netlist carries
    real pin numbers. Expand every ref.pin to its sheet-level pin set."""
    import sys as _sys
    from pathlib import Path as _P
    root = _P(__file__).resolve().parents[1]
    if str(root) not in _sys.path:
        _sys.path.insert(0, str(root))
    from mcp_schematic import _REAL_PARTS, _PIN_SYNONYMS, _real_part_key

    by_ref = {}
    comp_nodes = {}
    for comp in ir.get("components") or []:
        ref = str(comp.get("ref"))
        comp_nodes[ref] = [str(n) for n in comp.get("nodes") or []]
        key = _real_part_key(comp)
        if key:
            by_ref[ref] = _REAL_PARTS[key]

    def pins_of(ref: str, pin: str):
        part = by_ref.get(ref)
        if part:
            canon = _PIN_SYNONYMS.get(pin, pin)
            return set(part["pins"].get(canon) or [])
        nodes = comp_nodes.get(ref)
        if nodes and not pin.isdigit() and pin in nodes:
            return {str(nodes.index(pin) + 1)}
        return {pin}

    out = []
    for net in ir.get("nets") or []:
        conns = set()
        for c in net.get("connections") or []:
            ref, _, pin = str(c).rpartition(".")
            for p in pins_of(ref, pin):
                conns.add((ref, p))
        out.append({"name": net.get("name"), "connections": conns})
    return out


def main() -> int:
    if len(sys.argv) == 3:
        net_file, ir_file = Path(sys.argv[1]), Path(sys.argv[2])
    else:
        d = Path(sys.argv[1])
        net_file = next(d.glob("*.net"))
        ir_file = d / "ir.json"
    sheet = parse_net(net_file)
    ir = load_ir(ir_file)
    ir_nets = expand_pins(ir)

    print(f"sheet nets: {len(sheet)}  ir nets: {len(ir_nets)}")
    bad = 0
    for net in ir_nets:
        name = str(net.get("name"))
        want = set(net.get("connections") or [])
        # find sheet nets containing any wanted ref.pin
        owners = {n for n, conns in sheet.items() if conns & want}
        merged = set().union(*(sheet[n] for n in owners)) if owners else set()
        missing = want - merged
        extra = merged - want
        status = "OK " if not missing else "MISS"
        if missing or (owners and len(owners) > 1):
            bad += 1
        if len(owners) > 1:
            status = "SPLIT"
        print(f"[{status}] {name}: want {len(want)} pins")
        if len(owners) > 1:
            print(f"       split across sheet nets: {sorted(owners)}")
        if missing:
            print(f"       missing on sheet: {sorted(missing)}")
        if extra:
            print(f"       extra on sheet: {sorted(extra)[:8]}")
    print(f"\nproblem nets: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
