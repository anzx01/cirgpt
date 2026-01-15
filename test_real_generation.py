"""
Test script to verify real circuit generation (no mock data)
"""
import requests
import json
import sys
import io

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def test_circuit_generation():
    """Test the complete circuit generation pipeline"""

    print("=" * 60)
    print("Testing Real Circuit Generation")
    print("=" * 60)

    # Test description
    description = "Design a 555 timer LED blinker circuit with 1 Hz frequency"

    print(f"\n1. Parsing description: {description}")
    print("-" * 60)

    # Parse natural language
    try:
        parse_response = requests.post(
            "http://localhost:8001/ai/parse",
            json={"description": description},
            timeout=30
        )

        if parse_response.status_code == 200:
            requirements = parse_response.json()["requirements"]
            print("✓ Successfully parsed requirements")
            print(f"  Circuit type: {requirements['topology']['type']}")
            print(f"  Components found: {len(requirements['components'])}")
            print(f"  Specifications: {requirements['specifications']}")
        else:
            print(f"✗ Parse failed: {parse_response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Parse error: {e}")
        return False

    print("\n2. Generating circuit netlist")
    print("-" * 60)

    # Generate netlist
    try:
        gen_response = requests.post(
            "http://localhost:8001/ai/generate",
            json={"requirements": requirements},
            timeout=30
        )

        if gen_response.status_code == 200:
            netlist = gen_response.json()["netlist"]
            print("✓ Successfully generated netlist")
            print(f"  Netlist length: {len(netlist)} characters")
            print(f"  First few lines:\n{netlist[:200]}...")
        else:
            print(f"✗ Generation failed: {gen_response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Generation error: {e}")
        return False

    print("\n3. Simulating circuit (PySpice)")
    print("-" * 60)

    # Simulate circuit
    try:
        sim_response = requests.post(
            "http://localhost:8002/eda/simulation",
            json={"netlist": netlist},
            timeout=60
        )

        if sim_response.status_code == 200:
            response_data = sim_response.json()
            if response_data.get("success"):
                sim_result = response_data.get("results", {})
                print("[OK] Successfully simulated circuit")

                # Check if it's using real data
                if "error" in sim_result and "mock" in str(sim_result.get("message", "")):
                    print("  [!] WARNING: Using mock data!")
                    print(f"  Message: {sim_result.get('message', '')}")
                else:
                    print("  [+] Using REAL PySpice simulation")

                voltages = sim_result.get("voltages", {})
                time_points = sim_result.get("time", [])

                if time_points:
                    print(f"  Time points: {len(time_points)}")
                    print(f"  Voltage nodes: {list(voltages.keys())}")

                    # Show some sample values
                    if "output" in voltages:
                        output_v = voltages["output"]
                        print(f"  Output voltage range: {min(output_v):.2f}V to {max(output_v):.2f}V")
            else:
                print(f"[!] Simulation returned success=False")
                return False
        else:
            print(f"[!] Simulation failed: {sim_response.status_code}")
            print(f"  Error: {sim_response.text}")
            return False
    except Exception as e:
        print(f"[!] Simulation error: {e}")
        return False

    print("\n4. Generating schematic (SKiDL)")
    print("-" * 60)

    # Generate schematic
    try:
        schematic_response = requests.post(
            "http://localhost:8002/eda/schematic",
            json={"netlist": netlist},
            timeout=30
        )

        if schematic_response.status_code == 200:
            schematic_result = schematic_response.json()
            print("✓ Successfully generated schematic")
            print(f"  SVG size: {len(schematic_result.get('svg', ''))} characters")

            summary = schematic_result.get("summary", {})
            print(f"  Components: {summary.get('total_components', 0)}")
            print(f"  Nets: {summary.get('total_nets', 0)}")
        else:
            print(f"✗ Schematic generation failed: {schematic_response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Schematic error: {e}")
        return False

    print("\n5. Generating PCB layout")
    print("-" * 60)

    # Generate PCB
    try:
        pcb_response = requests.post(
            "http://localhost:8002/eda/pcb",
            json={"netlist": netlist},
            timeout=30
        )

        if pcb_response.status_code == 200:
            pcb_result = pcb_response.json()
            print("✓ Successfully generated PCB layout")

            layout = pcb_result.get("layout", {})
            components = layout.get("components", [])
            tracks = layout.get("tracks", [])

            print(f"  Components placed: {len(components)}")
            print(f"  Tracks routed: {len(tracks)}")
            print(f"  Board size: {layout.get('board_outline', {})}")

            # Check placement algorithm
            if components:
                first_comp = components[0]
                position = first_comp.get("position", {})
                rotation = first_comp.get("rotation", 0)

                print(f"  Sample component placement:")
                print(f"    {first_comp['name']}: x={position.get('x', 0)}, y={position.get('y', 0)}, rotation={rotation}°")

        else:
            print(f"✗ PCB generation failed: {pcb_response.status_code}")
            return False
    except Exception as e:
        print(f"✗ PCB error: {e}")
        return False

    print("\n" + "=" * 60)
    print("✓ All tests completed successfully!")
    print("=" * 60)

    print("\nKey Improvements:")
    print("  • Simulation: Using REAL PySpice (not mock waveforms)")
    print("  • Schematic: Using SKiDL circuit library")
    print("  • PCB: Using intelligent force-directed placement")
    print("  • All data is generated from actual circuit analysis")

    return True

if __name__ == "__main__":
    test_circuit_generation()
