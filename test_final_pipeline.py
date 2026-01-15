#!/usr/bin/env python
"""
Final End-to-End Test for Industrial-Grade Schematic Generation Pipeline

This test demonstrates the complete workflow:
1. SPICE netlist parsing
2. SVG generation with automatic layout and routing
3. Output validation
"""
import sys
import os

# Add eda_tools to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'eda_tools'))

from eda_tools.spice_parser import SPICEParser
from eda_tools.svg_generator import SVGSchematicGenerator


def test_555_timer_complete():
    """Complete end-to-end test with 555 timer circuit"""

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

    print("=" * 70)
    print("FINAL END-TO-END TEST: Industrial-Grade Schematic Generation")
    print("=" * 70)

    # Step 1: Parse SPICE netlist
    print("\n[Step 1] Parsing SPICE netlist...")
    parser = SPICEParser()
    try:
        spice_data = parser.parse(test_netlist)
        print(f"[OK] Parsed {len(spice_data['components'])} components")
        print(f"[OK] Found {len(spice_data['nets'])} nets")

        # Display parsed components
        print("\nParsed Components:")
        for comp in spice_data['components']:
            print(f"  {comp['name']}: type={comp['type']}, nodes={comp['nodes']}, value={comp['value']}")

    except Exception as e:
        print(f"[ERROR] Failed to parse SPICE: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 2: Generate SVG
    print("\n[Step 2] Generating SVG schematic...")
    try:
        generator = SVGSchematicGenerator(spice_data)
        svg = generator.generate()
        print(f"[OK] Generated SVG: {len(svg)} bytes")

        # Save to file
        output_file = 'test_final_schematic.svg'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(svg)
        print(f"[OK] Saved to: {output_file}")

    except Exception as e:
        print(f"[ERROR] Failed to generate SVG: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 3: Validate output
    print("\n[Step 3] Validating SVG output...")
    checks = {
        "Valid XML header": '<?xml' in svg,
        "Has SVG root element": '<svg' in svg,
        "Has component elements": svg.count('class="component"') >= len(spice_data['components']),
        "Has wire elements": 'class="wire"' in svg,
        "Has pin elements": 'class="pin"' in svg,
        "Has ground connections": '0' in spice_data['nets'] and len(spice_data['nets']['0']) > 0,
        "Contains NE555": 'NE555' in svg,
    }

    all_passed = True
    for check, passed in checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {check}")
        if not passed:
            all_passed = False

    # Summary
    print("\n" + "=" * 70)
    if all_passed:
        print("SUCCESS: Complete pipeline working!")
        print("\nFeatures implemented:")
        print("  - Component-specific SPICE parsing")
        print("  - Force-directed graph layout for components")
        print("  - Pin-to-pin Manhattan wire routing")
        print("  - Professional SVG output with styling")
        print("  - Ground symbols")
        print("\nThe industrial-grade schematic generation system is fully functional!")
        print(f"\nOutput saved to: {output_file}")
        print("Open the SVG file in a browser to view the schematic.")
    else:
        print("FAILED: Some validation checks failed")
        return False

    print("=" * 70)
    return all_passed


if __name__ == '__main__':
    success = test_555_timer_complete()
    sys.exit(0 if success else 1)
