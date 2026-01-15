"""
Test the wrapper function
"""
import sys
import io
sys.path.insert(0, 'G:/myaist/cirgpt/eda_tools')

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from skidl.schematic_generator import generate_schematic

test_netlist = """* 555 Timer Circuit
V1 VCC 0 DC 9.0
U1 1 2 3 4 5 6 7 8 NE555
R1 VCC 7 1.0k
C1 6 0 10.0u
.end"""

print("Testing generate_schematic() wrapper function...")

svg, summary = generate_schematic(test_netlist)

print(f"\nSVG length: {len(svg)}")
print(f"Summary: {summary}")

if '<polyline ' in svg:
    print("\n[SUCCESS] Found connections!")
else:
    print("\n[FAILED] No connections")
