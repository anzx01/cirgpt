#!/usr/bin/env python
"""Test IC detection for 555 timer"""

import sys
sys.path.insert(0, 'eda_tools')

from schematic_gen.schematic_generator import SchematicGenerator

netlist = """* 555 Timer LED Blinker
V1 VCC 0 DC 9
R1 VCC 7 1k
R2 7 6 71.5k
C1 6 0 10u
C2 5 0 10n
R3 3 700 220
D1 700 0 LED
XU1 1 2 3 4 8 7 6 5 NE555
"""

gen = SchematicGenerator()
parsed = gen.parse_spice_netlist(netlist)

print("Parsed components:")
for comp in parsed["components"]:
    print(f"  {comp['name']}: type={comp['type']}, value={comp.get('value', 'N/A')}, nodes={comp['nodes']}")

print("\nLooking for 555 IC:")
for comp in parsed["components"]:
    value = comp.get("value", "").lower()
    has_555 = "555" in value
    print(f"  {comp['name']}: type={comp['type']}, value='{value}', has_555={has_555}")

ic_555 = next((c for c in parsed["components"] if (c["type"] == "U" or c["type"] == "X") and "555" in c.get("value", "").lower()), None)
print(f"\nFound 555 IC: {ic_555}")

if ic_555:
    print(f"  Name: {ic_555['name']}")
    print(f"  Type: {ic_555['type']}")
    print(f"  Value: {ic_555.get('value', 'N/A')}")
