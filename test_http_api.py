"""
Test HTTP API directly and save response
"""
import requests
import json

test_netlist = """* 555 Timer LED Blinker Circuit
V1 VCC 0 DC 9.0
U1 1 2 3 4 5 6 7 8 NE555
R1 VCC 7 1.0k
R2 7 6 71.5k
C1 6 0 10.0u
C2 5 0 10n
.end"""

print("Testing HTTP API: http://localhost:8002/eda/schematic")
print("=" * 60)

try:
    response = requests.post(
        "http://localhost:8002/eda/schematic",
        json={"netlist": test_netlist},
        timeout=30
    )

    print(f"\nStatus Code: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")

    if response.status_code == 200:
        data = response.json()
        print(f"\nResponse Keys: {list(data.keys())}")
        print(f"Success: {data.get('success')}")

        svg = data.get('svg', '')
        print(f"\nSVG Length: {len(svg)}")
        print(f"First 200 chars: {svg[:200]}")

        # Check for connections
        if '<polyline ' in svg:
            print("\n[SUCCESS] Found polyline connections!")
        else:
            print("\n[FAILED] No polyline found")

        if 'zigzag' in svg or 'NE555' in svg:
            print("[SUCCESS] Found real circuit symbols!")
        else:
            print("[FAILED] No real symbols found")

        # Save SVG
        with open('http_api_schematic.svg', 'w', encoding='utf-8') as f:
            f.write(svg)
        print("\nSaved to: http_api_schematic.svg")

    else:
        print(f"\nError: {response.text}")

except Exception as e:
    print(f"\nException: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
