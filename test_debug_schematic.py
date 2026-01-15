"""
Debug test to see actual errors
"""
import sys
import io
sys.path.insert(0, 'G:/myaist/cirgpt/eda_tools')

# Set UTF-8 encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from skidl.schematic_generator import SchematicGenerator
import traceback

test_netlist = """* 555 Timer Circuit
V1 VCC 0 DC 9.0
U1 1 2 3 4 5 6 7 8 NE555
R1 VCC 7 1.0k
C1 6 0 10.0u
.end"""

print("=" * 60)
print("DEBUG: Testing schematic generation")
print("=" * 60)

try:
    generator = SchematicGenerator()
    print("\n[OK] Generator initialized")

    # Parse netlist
    parsed = generator.parse_spice_netlist(test_netlist)
    print(f"[OK] Parsed {len(parsed['components'])} components")

    # Generate SVG
    print("\n[INFO] Calling generate_svg_schematic()...")
    svg = generator.generate_svg_schematic(test_netlist)

    print(f"\n[OK] SVG generated: {len(svg)} chars")

    # Check content
    if '<polyline ' in svg:
        print("[SUCCESS] Found connection lines!")
    else:
        print("[WARNING] No connection lines found")

    if 'zigzag' in svg or 'NE555' in svg:
        print("[SUCCESS] Found real circuit symbols!")
    else:
        print("[WARNING] No real symbols found")

except Exception as e:
    print(f"\n[ERROR] {e}")
    print("\nFull traceback:")
    traceback.print_exc()

print("\n" + "=" * 60)
