"""
Direct test of schematic generator to see errors
"""
import sys
import io
sys.path.insert(0, 'G:/myaist/cirgpt/eda_tools')

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from skidl.schematic_generator import SchematicGenerator

test_netlist = """* 555 Timer LED Blinker Circuit
V1 VCC 0 DC 9.0
U1 1 2 3 4 5 6 7 8 NE555
R1 VCC 7 1.0k
R2 7 6 71.5k
C1 6 0 10.0u
.end"""

print("Testing schematic generator directly...")
print("=" * 60)

try:
    generator = SchematicGenerator()
    print("✓ Generator initialized")

    # Parse netlist
    parsed = generator.parse_spice_netlist(test_netlist)
    print(f"✓ Parsed {len(parsed['components'])} components, {len(parsed['nets'])} nets")
    print(f"  Components: {[c['name'] for c in parsed['components']]}")
    print(f"  Nets: {list(parsed['nets'].keys())}")

    # Generate SVG
    svg = generator.generate_svg_schematic(test_netlist)
    print(f"\n✓ SVG generated: {len(svg)} characters")

    # Check what method was used
    if '<rect x="' in svg and 'width="80" height="60"' in svg:
        print("\n⚠ WARNING: Using simple component boxes (fallback mode)")
        print("  This means _create_circuit_graph_svg failed!")

        # Check if SVG has connections
        if '<polyline ' in svg:
            print("  ✓ But connections are present!")
        else:
            print("  ✗ No connections found")
    elif '<polyline ' in svg:
        print("\n✓ SUCCESS: Using real circuit symbols with connections!")
    else:
        print("\n? Unknown format")

    # Save SVG
    with open('test_direct_schematic.svg', 'w', encoding='utf-8') as f:
        f.write(svg)
    print("\nSaved to: test_direct_schematic.svg")

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
