#!/usr/bin/env python
"""
Test script for the new industrial-grade schematic generation pipeline
"""
import sys
import os

# Add eda_tools to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'eda_tools'))

from eda_tools.spice_parser import SPICEParser
from eda_tools.kicad_netlist import KiCadNetlistConverter
from eda_tools.netlistsvg_wrapper import NetlistSVGGenerator


def test_555_timer():
    """Test with 555 timer circuit"""

    test_netlist = """* 555 Timer LED Blinker
V1 VCC 0 DC 9
R1 VCC 7 1k
R2 7 6 71.5k
C1 6 0 10u
C2 5 0 10n
R3 3 700 220
D1 700 0 LED
XU1 1 2 3 4 8 7 6 5 NE555
"""

    print("=" * 60)
    print("Testing Industrial-Grade Schematic Generation Pipeline")
    print("=" * 60)

    # Step 1: Parse SPICE
    print("\n[Step 1] Parsing SPICE netlist...")
    parser = SPICEParser()
    try:
        spice_data = parser.parse(test_netlist)
        print(f"[OK] Parsed {len(spice_data['components'])} components")
        print(f"[OK] Found {len(spice_data['nets'])} nets")

        # Show components
        print("\nComponents:")
        for comp in spice_data['components']:
            print(f"  {comp['name']}: type={comp['type']}, nodes={comp['nodes']}, value={comp['value']}")

        # Show nets
        print("\nNets:")
        for net_name, connections in list(spice_data['nets'].items())[:5]:
            print(f"  {net_name}: {', '.join(connections)}")

    except Exception as e:
        print(f"[ERROR] Failed to parse SPICE: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 2: Convert to KiCad netlist
    print("\n[Step 2] Converting to KiCad netlist format...")
    converter = KiCadNetlistConverter()
    try:
        kicad_netlist = converter.convert(spice_data)
        print(f"[OK] Converted to KiCad format")
        print(f"[OK] Export version: {kicad_netlist['exportVersion']}")
        print(f"[OK] Design title: {kicad_netlist['design']['title']}")

        # Save KiCad netlist for inspection
        import json
        with open('test_kicad_netlist.json', 'w') as f:
            json.dump(kicad_netlist, f, indent=2)
        print(f"[OK] KiCad netlist saved to: test_kicad_netlist.json")

    except Exception as e:
        print(f"[ERROR] Failed to convert to KiCad format: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 3: Generate SVG with netlistsvg
    print("\n[Step 3] Generating SVG schematic with netlistsvg...")
    generator = NetlistSVGGenerator()
    try:
        svg = generator.generate(kicad_netlist, 'test_netlistsvg_output.svg')
        print(f"[OK] Generated SVG: {len(svg)} bytes")
        print(f"[OK] SVG saved to: test_netlistsvg_output.svg")

        # Check SVG content
        checks = {
            "Contains '<svg'": '<svg' in svg,
            "Contains 'NE555'": 'NE555' in svg,
            "Contains components": 'R1' in svg or 'C1' in svg,
            "Contains wires": 'path' in svg or 'line' in svg or 'polyline' in svg
        }

        print("\nSVG Content Checks:")
        all_passed = True
        for check, passed in checks.items():
            status = "[OK]" if passed else "[FAIL]"
            print(f"  {status} {check}")
            if not passed:
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"[ERROR] Failed to generate SVG: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_555_timer()

    print("\n" + "=" * 60)
    if success:
        print("SUCCESS: All tests passed!")
        print("\nThe industrial-grade schematic generation pipeline is working!")
        print("Next step: Integrate into API and add circuit validation.")
    else:
        print("FAILED: Some tests failed")
        print("\nPlease check the errors above and fix them.")
        sys.exit(1)

    print("=" * 60)
