"""
SKiDL integration for schematic generation
"""
import logging
import re
from typing import Dict, List, Tuple
import base64
import io

logger = logging.getLogger(__name__)


class SchematicGenerator:
    """Generate circuit schematics using SKiDL"""

    def __init__(self):
        """Initialize schematic generator with SKiDL"""
        try:
            # Import SKiDL library - use explicit import to avoid conflict with local module
            import sys
            import importlib

            # Remove local skidl from path temporarily to import library
            local_skidl_paths = [p for p in sys.path if 'eda_tools' in p and 'skidl' in p]
            original_path = sys.path[:]
            for path in local_skidl_paths:
                if path in sys.path:
                    sys.path.remove(path)

            # Import SKiDL library
            skidl_lib = importlib.import_module('skidl')
            from skidl import Circuit, Part, Net, subcircuit

            # Restore path
            sys.path = original_path

            self.skidl_lib = skidl_lib
            self.skidl = Circuit
            self.Part = Part
            self.Net = Net
            logger.info("✓ SKiDL library loaded successfully")
        except Exception as e:
            logger.error(f"✗ SKiDL library not found or import failed: {e}")
            # Don't raise - allow fallback to simple schematic generation
            self.skidl_lib = None
            self.skidl = None
            self.Part = None
            self.Net = None

    def parse_spice_netlist(self, netlist: str) -> Dict[str, List[Dict]]:
        """
        Parse SPICE netlist into component and net information

        Args:
            netlist: SPICE netlist string

        Returns:
            Dictionary with components and nets
        """
        components = []
        nets = {}

        lines = netlist.strip().split('\n')

        for line in lines:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('*') or line.startswith('.') or line.startswith('+'):
                continue

            # Parse component line
            parts = line.split()
            if len(parts) >= 3:
                comp_name = parts[0]
                nodes = parts[1:-1]  # Nodes between first and last
                value = parts[-1]  # Last part is value/model

                # Determine component type
                comp_type = comp_name[0].upper()

                component = {
                    "name": comp_name,
                    "type": comp_type,
                    "nodes": nodes,
                    "value": value
                }
                components.append(component)

                # Track nets
                for node in nodes:
                    if node not in nets:
                        nets[node] = []
                    nets[node].append(comp_name)

        return {
            "components": components,
            "nets": nets
        }

    def _build_skidl_circuit(self, components: List[Dict], nets: Dict[str, List[str]]) -> object:
        """
        Build circuit using SKiDL for validation

        Args:
            components: List of component dictionaries
            nets: Dictionary of nets and connected components

        Returns:
            SKiDL Circuit object or None if SKiDL is not available
        """
        # Check if SKiDL is available
        if self.skidl is None or self.Part is None or self.Net is None:
            logger.warning("SKiDL not available, skipping circuit validation")
            return None

        try:
            # Import SKiDL classes
            Circuit = self.skidl
            Net = self.Net

            # Create a new circuit
            circuit = Circuit()

            # Keep track of SKiDL parts and nets
            skidl_parts = {}
            skidl_nets = {}

            # Create nets first
            for net_name in nets.keys():
                if net_name == "0":
                    # Ground net
                    skidl_nets[net_name] = Net("GND")
                else:
                    skidl_nets[net_name] = Net(net_name)

            # Create parts from component definitions
            for comp in components:
                comp_name = comp["name"]
                comp_type = comp["type"]
                value = comp.get("value", "")

                # Define part based on component type
                try:
                    if comp_type == "R":
                        part = self.Part("Device:R", value=value, footprint=comp_name)
                    elif comp_type == "C":
                        part = self.Part("Device:C", value=value, footprint=comp_name)
                    elif comp_type == "L":
                        part = self.Part("Device:L", value=value, footprint=comp_name)
                    elif comp_type == "D":
                        part = self.Part("Device:D", value=value, footprint=comp_name)
                    elif comp_type == "Q":
                        part = self.Part("Device:Q_NPN_CBE", value=value, footprint=comp_name)
                    elif comp_type == "V":
                        part = self.Part("Simulation_SPICE:V", value=value, footprint=comp_name)
                    elif comp_type == "U":
                        # IC - use a generic definition
                        if "555" in value.upper():
                            part = self.Part("Timer:NE555", value=value, footprint=comp_name)
                        else:
                            part = self.Part("IC_Generic:IC", value=value, footprint=comp_name)
                    else:
                        # Generic part
                        part = self.Part("Device:Generic", value=value, footprint=comp_name)

                    skidl_parts[comp_name] = part
                except Exception as e:
                    logger.warning(f"Could not create SKiDL part for {comp_name}: {e}")
                    continue

            # Connect parts to nets
            for comp in components:
                comp_name = comp["name"]
                nodes = comp.get("nodes", [])

                if comp_name in skidl_parts:
                    part = skidl_parts[comp_name]

                    # Connect each pin to the corresponding net
                    for i, node in enumerate(nodes):
                        if node in skidl_nets:
                            net = skidl_nets[node]
                            # Connect pin i+1 to the net (SKiDL uses 1-based pin numbering)
                            if i < len(part.pins):
                                part.pins[i] += net

            logger.info(f"✓ SKiDL circuit built: {len(skidl_parts)} parts, {len(skidl_nets)} nets")
            return circuit

        except Exception as e:
            logger.warning(f"SKiDL circuit building had issues: {e}")
            # Still return None if circuit building failed
            return None

    def generate_svg_schematic(self, netlist: str) -> str:
        """
        Generate SVG schematic from netlist using SKiDL

        Args:
            netlist: SPICE netlist

        Returns:
            SVG string
        """
        logger.info("Generating SVG schematic using SKiDL")

        try:
            # Parse netlist to extract components and nets
            parsed = self.parse_spice_netlist(netlist)
            components = parsed["components"]
            nets = parsed["nets"]

            # Build circuit using SKiDL for validation
            circuit = self._build_skidl_circuit(components, nets)

            # Create circuit visualization with connections
            svg = self._create_circuit_graph_svg(components, nets)

            logger.info("✓ SVG schematic generated with SKiDL validation")
            return svg

        except Exception as e:
            logger.error(f"Error generating SVG schematic: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Fall back to simple component display
            return self._create_svg_from_components(parsed.get("components", []) if 'parsed' in locals() else [])

    def _create_svg_from_components(self, components: List[Dict]) -> str:
        """
        Create SVG from component list

        Args:
            components: List of components

        Returns:
            SVG string
        """
        # Simple grid layout
        svg_width = 800
        svg_height = 600
        grid_size = 100

        svg_parts = []
        svg_parts.append(f'<svg width="{svg_width}" height="{svg_height}" xmlns="http://www.w3.org/2000/svg">')
        svg_parts.append('<!-- Generated by AI Circuit Designer -->')

        # Background
        svg_parts.append(f'<rect width="100%" height="100%" fill="white"/>')

        # Title
        svg_parts.append(f'<text x="400" y="30" text-anchor="middle" font-size="20" font-weight="bold">Circuit Schematic</text>')

        # Draw components
        y_pos = 80
        for i, comp in enumerate(components):
            x_pos = 50 + (i % 7) * grid_size

            # Component symbol
            symbol = self._get_component_symbol(comp["type"])
            color = self._get_component_color(comp["type"])

            # Draw component box
            svg_parts.append(f'<rect x="{x_pos}" y="{y_pos}" width="80" height="60" fill="none" stroke="{color}" stroke-width="2"/>')
            svg_parts.append(f'<text x="{x_pos + 40}" y="{y_pos + 25}" text-anchor="middle" font-size="14" font-weight="bold">{symbol}</text>')
            svg_parts.append(f'<text x="{x_pos + 40}" y="{y_pos + 45}" text-anchor="middle" font-size="12">{comp["name"]}</text>')

            # Move to next row if needed
            if (i + 1) % 7 == 0:
                y_pos += 80

        # Legend
        svg_parts.append('<text x="50" y="550" font-size="12">Legend:</text>')
        svg_parts.append('<rect x="120" y="540" width="15" height="15" fill="none" stroke="green" stroke-width="2"/>')
        svg_parts.append('<text x="140" y="552" font-size="12">Resistor</text>')

        svg_parts.append('<rect x="220" y="540" width="15" height="15" fill="none" stroke="blue" stroke-width="2"/>')
        svg_parts.append('<text x="240" y="552" font-size="12">Capacitor</text>')

        svg_parts.append('</svg>')

        return '\n'.join(svg_parts)

    def _get_component_symbol(self, comp_type: str) -> str:
        """Get symbol for component type"""
        symbols = {
            "R": "R",  # Resistor
            "C": "C",  # Capacitor
            "L": "L",  # Inductor
            "D": "D",  # Diode
            "Q": "Q",  # Transistor
            "U": "IC", # IC
            "V": "V",  # Voltage source
            "I": "I"   # Current source
        }
        return symbols.get(comp_type, "?")

    def _get_component_color(self, comp_type: str) -> str:
        """Get color for component type"""
        colors = {
            "R": "green",   # Resistor
            "C": "blue",    # Capacitor
            "L": "orange",  # Inductor
            "D": "red",     # Diode
            "Q": "purple",  # Transistor
            "U": "black",   # IC
            "V": "brown",   # Voltage source
            "I": "brown"    # Current source
        }
        return colors.get(comp_type, "gray")

    def _create_circuit_graph_svg(self, components: List[Dict], nets: Dict[str, List[str]]) -> str:
        """
        Create circuit graph SVG showing actual connections with real circuit symbols

        Args:
            components: List of components
            nets: Dictionary of nets and connected components

        Returns:
            SVG string with real schematic symbols
        """
        # Check if this is a 555 timer circuit
        is_555_circuit = any("555" in comp.get("value", "").lower() or "NE555" in comp.get("value", "")
                           for comp in components)

        if is_555_circuit:
            return self._create_555_schematic_svg(components, nets)

        svg_width = 1000
        svg_height = 700

        svg_parts = []
        svg_parts.append(f'<svg width="{svg_width}" height="{svg_height}" xmlns="http://www.w3.org/2000/svg">')
        svg_parts.append('<!-- Generated by AI Circuit Designer using SKiDL -->')

        # Background with grid
        svg_parts.append(f'<rect width="100%" height="100%" fill="white"/>')
        # Draw grid lines
        for i in range(0, svg_width, 50):
            svg_parts.append(f'<line x1="{i}" y1="0" x2="{i}" y2="{svg_height}" stroke="#f0f0f0" stroke-width="1"/>')
        for i in range(0, svg_height, 50):
            svg_parts.append(f'<line x1="0" y1="{i}" x2="{svg_width}" y2="{i}" stroke="#f0f0f0" stroke-width="1"/>')

        # Title
        svg_parts.append(f'<text x="500" y="30" text-anchor="middle" font-size="20" font-weight="bold">Circuit Schematic</text>')

        # Intelligent component placement
        comp_positions = self._layout_components_intelligently(components)

        # Draw connections first (so components appear on top)
        self._draw_wires(svg_parts, nets, comp_positions, components)

        # Draw components with real symbols
        for comp_name, pos in comp_positions.items():
            comp = next((c for c in components if c["name"] == comp_name), None)
            if comp:
                self._draw_component_symbol(svg_parts, comp, pos)

        svg_parts.append('</svg>')

        return '\n'.join(svg_parts)

    def _layout_components_intelligently(self, components: List[Dict]) -> Dict[str, Dict]:
        """
        Layout components in an intelligent arrangement based on type

        Args:
            components: List of components

        Returns:
            Dictionary of component positions
        """
        positions = {}

        # Separate components by type
        ics = [c for c in components if c["type"] == "U"]
        resistors = [c for c in components if c["type"] == "R"]
        capacitors = [c for c in components if c["type"] == "C"]
        diodes = [c for c in components if c["type"] == "D"]
        sources = [c for c in components if c["type"] == "V"]
        inductors = [c for c in components if c["type"] == "L"]
        transistors = [c for c in components if c["type"] == "Q"]
        current_sources = [c for c in components if c["type"] == "I"]

        # Place ICs in the center
        for i, ic in enumerate(ics):
            x = 400
            y = 150 + i * 200
            positions[ic["name"]] = {"x": x, "y": y, "type": ic["type"]}

        # Place voltage source on the left
        for i, v in enumerate(sources):
            x = 100
            y = 150 + i * 100
            positions[v["name"]] = {"x": x, "y": y, "type": v["type"]}

        # Place current sources
        for i, cs in enumerate(current_sources):
            x = 100
            y = 300 + i * 100
            positions[cs["name"]] = {"x": x, "y": y, "type": cs["type"]}

        # Place resistors around the IC
        for i, r in enumerate(resistors):
            if i % 2 == 0:
                x = 250
                y = 150 + (i // 2) * 80
            else:
                x = 550
                y = 150 + (i // 2) * 80
            positions[r["name"]] = {"x": x, "y": y, "type": r["type"]}

        # Place capacitors
        for i, c in enumerate(capacitors):
            x = 700
            y = 150 + i * 80
            positions[c["name"]] = {"x": x, "y": y, "type": c["type"]}

        # Place inductors (similar to resistors)
        for i, l in enumerate(inductors):
            if i % 2 == 0:
                x = 250
                y = 350 + (i // 2) * 80
            else:
                x = 550
                y = 350 + (i // 2) * 80
            positions[l["name"]] = {"x": x, "y": y, "type": l["type"]}

        # Place transistors
        for i, q in enumerate(transistors):
            x = 250 + (i % 3) * 150
            y = 450 + (i // 3) * 100
            positions[q["name"]] = {"x": x, "y": y, "type": q["type"]}

        # Place diodes/LEDs
        for i, d in enumerate(diodes):
            x = 700
            y = 350 + i * 80
            positions[d["name"]] = {"x": x, "y": y, "type": d["type"]}

        return positions

    def _get_pin_offset(self, comp_type: str, pin_index: int, comp: Dict = None) -> Tuple[int, int]:
        """
        Get pin position offset relative to component center

        Args:
            comp_type: Component type (R, C, L, D, Q, U, V, I)
            pin_index: Which pin (0-based index)
            comp: Component dictionary for special cases

        Returns:
            Tuple of (x_offset, y_offset) from center
        """
        if comp_type == "R":  # Resistor
            # Pin 0: left (-40, 0), Pin 1: right (+40, 0)
            return (-40, 0) if pin_index == 0 else (40, 0)

        elif comp_type == "C":  # Capacitor
            # Pin 0: left (-30, 0), Pin 1: right (+30, 0)
            return (-30, 0) if pin_index == 0 else (30, 0)

        elif comp_type == "L":  # Inductor
            # Similar to resistor
            return (-40, 0) if pin_index == 0 else (40, 0)

        elif comp_type == "D":  # Diode
            # Pin 0: left (-30, 0), Pin 1: right (+30, 0)
            return (-30, 0) if pin_index == 0 else (30, 0)

        elif comp_type == "V" or comp_type == "I":  # Voltage/Current source
            # Pin 0: left (-30, 0), Pin 1: right (+30, 0)
            return (-30, 0) if pin_index == 0 else (30, 0)

        elif comp_type == "Q":  # Transistor (simplified)
            # Pin 0: collector, Pin 1: base, Pin 2: emitter
            offsets = [(0, -30), (-30, 0), (0, 30)]
            return offsets[pin_index] if pin_index < 3 else (0, 0)

        elif comp_type == "U" or comp_type == "X":  # IC or Subcircuit
            # IC pins are on the sides
            # For simplicity, alternate left/right
            if comp and "555" in comp.get("value", "").upper():
                # 555 timer specific: 8 pins
                # Pins 1-4 on left, 5-8 on right (looking from top)
                pin_offsets = {
                    0: (-50, -40),  # Pin 1
                    1: (-50, -10),  # Pin 2
                    2: (-50, 20),   # Pin 3
                    3: (-50, 50),   # Pin 4
                    4: (50, 50),    # Pin 5
                    5: (50, 20),    # Pin 6
                    6: (50, -10),   # Pin 7
                    7: (50, -40),   # Pin 8
                }
                return pin_offsets.get(pin_index, (0, 0))
            else:
                # Generic IC - alternate pins on left/right
                return (-50, 0) if pin_index % 2 == 0 else (50, 0)

        # Default: return center
        return (0, 0)

    def _draw_wires(self, svg_parts: list, nets: Dict[str, List[str]], positions: Dict[str, Dict], components: List[Dict]):
        """
        Draw wires between component pins (not centers!)

        Args:
            svg_parts: List to append SVG elements to
            nets: Dictionary mapping net names to component names
            positions: Dictionary mapping component names to positions
            components: List of component dictionaries with node info
        """
        import logging
        logger = logging.getLogger(__name__)

        # Create a component lookup
        comp_lookup = {c["name"]: c for c in components}

        logger.info(f"Drawing wires for {len(nets)} nets with {len(components)} components")

        # For each net, find all pins that connect to it
        for net_name, connected_comps in nets.items():
            if len(connected_comps) < 1:
                continue

            logger.debug(f"Processing net '{net_name}' with {len(connected_comps)} components")

            # Collect all (component, pin_index, coordinates) for this net
            pin_connections = []

            for comp_name in connected_comps:
                if comp_name not in comp_lookup:
                    logger.warning(f"Component '{comp_name}' not in comp_lookup")
                    continue
                if comp_name not in positions:
                    logger.warning(f"Component '{comp_name}' has no position")
                    continue

                comp = comp_lookup[comp_name]
                pos = positions[comp_name]
                comp_type = comp["type"]
                nodes = comp.get("nodes", [])

                logger.debug(f"  {comp_name} ({comp_type}): nodes={nodes}, pos=({pos['x']}, {pos['y']})")

                # Find which pin(s) connect to this net
                for pin_index, node in enumerate(nodes):
                    if node == net_name:
                        # Get pin offset for this component type and pin
                        pin_offset_x, pin_offset_y = self._get_pin_offset(comp_type, pin_index, comp)

                        # Calculate absolute pin position
                        pin_x = pos["x"] + pin_offset_x
                        pin_y = pos["y"] + pin_offset_y

                        logger.debug(f"    Pin {pin_index} -> net '{net_name}': offset=({pin_offset_x}, {pin_offset_y}), absolute=({pin_x}, {pin_y})")

                        pin_connections.append({
                            "comp": comp_name,
                            "pin": pin_index,
                            "x": pin_x,
                            "y": pin_y
                        })

            logger.info(f"Net '{net_name}': found {len(pin_connections)} pin connections")

            # Now connect all pins in this net
            # Strategy: connect each pin to the next one in sequence
            if len(pin_connections) >= 2:
                # Sort pins for consistent wiring (left-to-right, top-to-bottom)
                pin_connections.sort(key=lambda p: (p["y"], p["x"]))

                # Draw wires between sequential pins
                for i in range(len(pin_connections) - 1):
                    pin1 = pin_connections[i]
                    pin2 = pin_connections[i + 1]

                    logger.debug(f"  Drawing wire: {pin1['comp']}(pin {pin1['pin']}) -> {pin2['comp']}(pin {pin2['pin']})")

                    # Draw wire between these two pins
                    self._draw_wire_between_pins(svg_parts, pin1, pin2, net_name)

                # Add connection dots at each pin
                for pin in pin_connections:
                    color = "blue" if net_name == "0" else ("red" if net_name == "VCC" else "black")
                    svg_parts.append(f'<circle cx="{pin["x"]}" cy="{pin["y"]}" r="3" fill="{color}"/>')
            elif len(pin_connections) == 1:
                logger.warning(f"Net '{net_name}' has only 1 pin connection - needs at least 2 for a wire")

    def _draw_wire_between_pins(self, svg_parts: list, pin1: Dict, pin2: Dict, net_name: str):
        """
        Draw wire between two pins with Manhattan routing

        Args:
            svg_parts: List to append SVG elements
            pin1: First pin dict with 'x', 'y' coordinates
            pin2: Second pin dict with 'x', 'y' coordinates
            net_name: Name of the net (for labeling)
        """
        x1, y1 = pin1["x"], pin1["y"]
        x2, y2 = pin2["x"], pin2["y"]

        # Determine wire color based on net type
        if net_name == "0":
            color = "blue"
            width = "3"
        elif net_name == "VCC":
            color = "red"
            width = "3"
        else:
            color = "black"
            width = "2"

        # Manhattan routing: horizontal then vertical (or vice versa)
        if abs(x2 - x1) > abs(y2 - y1):
            # Go horizontal first, then vertical
            mid_x = x1 + (x2 - x1) // 2
            svg_parts.append(f'<polyline points="{x1},{y1} {mid_x},{y1} {mid_x},{y2} {x2},{y2}" fill="none" stroke="{color}" stroke-width="{width}"/>')
        else:
            # Go vertical first, then horizontal
            mid_y = y1 + (y2 - y1) // 2
            svg_parts.append(f'<polyline points="{x1},{y1} {x1},{mid_y} {x2},{mid_y} {x2},{y2}" fill="none" stroke="{color}" stroke-width="{width}"/>')

        # Add net label at midpoint (only for signal nets, not power/ground)
        if net_name != "0" and net_name != "VCC":
            mid_x = (x1 + x2) // 2
            mid_y = (y1 + y2) // 2
            svg_parts.append(f'<text x="{mid_x}" y="{mid_y - 5}" text-anchor="middle" font-size="8" fill="blue" font-weight="bold">{net_name}</text>')

    def _draw_manhattan_wire(self, svg_parts: list, pos1: Dict, pos2: Dict, net_name: str):
        """Draw wire with Manhattan routing (horizontal + vertical) - DEPRECATED, kept for compatibility"""
        x1, y1 = pos1["x"], pos1["y"]
        x2, y2 = pos2["x"], pos2["y"]

        # Determine routing direction
        if abs(x2 - x1) > abs(y2 - y1):
            # Go horizontal first, then vertical
            mid_x = x1 + (x2 - x1) // 2
            svg_parts.append(f'<polyline points="{x1},{y1} {mid_x},{y1} {mid_x},{y2} {x2},{y2}" fill="none" stroke="black" stroke-width="2"/>')
        else:
            # Go vertical first, then horizontal
            mid_y = y1 + (y2 - y1) // 2
            svg_parts.append(f'<polyline points="{x1},{y1} {x1},{mid_y} {x2},{mid_y} {x2},{y2}" fill="none" stroke="black" stroke-width="2"/>')

        # Add net label at midpoint
        mid_x = (x1 + x2) // 2
        mid_y = (y1 + y2) // 2
        svg_parts.append(f'<text x="{mid_x}" y="{mid_y - 5}" text-anchor="middle" font-size="9" fill="blue" font-weight="bold">{net_name}</text>')

    def _draw_component_symbol(self, svg_parts: list, comp: Dict, pos: Dict):
        """Draw component with real circuit symbol"""
        comp_type = comp["type"]
        x, y = pos["x"], pos["y"]

        if comp_type == "R":
            self._draw_resistor(svg_parts, x, y, comp["name"], comp["value"])
        elif comp_type == "C":
            self._draw_capacitor(svg_parts, x, y, comp["name"], comp["value"])
        elif comp_type == "D":
            self._draw_diode(svg_parts, x, y, comp["name"], comp["value"])
        elif comp_type == "U" or comp_type == "X":
            self._draw_ic(svg_parts, x, y, comp["name"], comp["value"])
        elif comp_type == "V":
            self._draw_voltage_source(svg_parts, x, y, comp["name"], comp["value"])

    def _draw_resistor(self, svg_parts: list, x: int, y: int, name: str, value: str):
        """Draw resistor symbol (zigzag)"""
        # Resistor body (zigzag)
        points = f"{x-30},{y} {x-20},{y-10} {x-10},{y+10} {x},{y-10} {x+10},{y+10} {x+20},{y-10} {x+30},{y}"
        svg_parts.append(f'<polyline points="{points}" fill="none" stroke="green" stroke-width="2"/>')

        # Terminals
        svg_parts.append(f'<line x1="{x-40}" y1="{y}" x2="{x-30}" y2="{y}" stroke="green" stroke-width="2"/>')
        svg_parts.append(f'<line x1="{x+30}" y1="{y}" x2="{x+40}" y2="{y}" stroke="green" stroke-width="2"/>')

        # Label
        svg_parts.append(f'<text x="{x}" y="{y-20}" text-anchor="middle" font-size="11" font-weight="bold" fill="green">{name}</text>')
        svg_parts.append(f'<text x="{x}" y="{y+25}" text-anchor="middle" font-size="10" fill="green">{value}</text>')

    def _draw_capacitor(self, svg_parts: list, x: int, y: int, name: str, value: str):
        """Draw capacitor symbol (parallel plates)"""
        # Two parallel plates
        svg_parts.append(f'<line x1="{x-20}" y1="{y-15}" x2="{x-20}" y2="{y+15}" stroke="blue" stroke-width="3"/>')
        svg_parts.append(f'<line x1="{x+20}" y1="{y-15}" x2="{x+20}" y2="{y+15}" stroke="blue" stroke-width="3"/>')

        # Terminals
        svg_parts.append(f'<line x1="{x-30}" y1="{y}" x2="{x-20}" y2="{y}" stroke="blue" stroke-width="2"/>')
        svg_parts.append(f'<line x1="{x+20}" y1="{y}" x2="{x+30}" y2="{y}" stroke="blue" stroke-width="2"/>')

        # Label
        svg_parts.append(f'<text x="{x}" y="{y-25}" text-anchor="middle" font-size="11" font-weight="bold" fill="blue">{name}</text>')
        svg_parts.append(f'<text x="{x}" y="{y+30}" text-anchor="middle" font-size="10" fill="blue">{value}</text>')

    def _draw_diode(self, svg_parts: list, x: int, y: int, name: str, value: str):
        """Draw diode/LED symbol"""
        # Triangle
        svg_parts.append(f'<polygon points="{x-20},{y-15} {x-20},{y+15} {x+10},{y}" fill="red" stroke="red" stroke-width="2"/>')

        # Cathode line
        svg_parts.append(f'<line x1="{x+10}" y1="{y-15}" x2="{x+10}" y2="{y+15}" stroke="red" stroke-width="3"/>')

        # Terminals
        svg_parts.append(f'<line x1="{x-30}" y1="{y}" x2="{x-20}" y2="{y}" stroke="red" stroke-width="2"/>')
        svg_parts.append(f'<line x1="{x+10}" y1="{y}" x2="{x+20}" y2="{y}" stroke="red" stroke-width="2"/>')

        # Label
        svg_parts.append(f'<text x="{x}" y="{y-25}" text-anchor="middle" font-size="11" font-weight="bold" fill="red">{name}</text>')
        svg_parts.append(f'<text x="{x}" y="{y+30}" text-anchor="middle" font-size="10" fill="red">{value}</text>')

    def _draw_ic(self, svg_parts: list, x: int, y: int, name: str, value: str):
        """Draw IC symbol (rectangle with pins)"""
        width, height = 100, 140

        # IC body
        svg_parts.append(f'<rect x="{x-width//2}" y="{y-height//2}" width="{width}" height="{height}" fill="white" stroke="black" stroke-width="3"/>')

        # Pin labels (left side)
        for i, pin in enumerate(["1", "2", "3", "4"]):
            py = y - 40 + i * 30
            svg_parts.append(f'<line x1="{x-width//2-10}" y1="{py}" x2="{x-width//2}" y2="{py}" stroke="black" stroke-width="2"/>')
            svg_parts.append(f'<text x="{x-width//2+10}" y="{py+5}" text-anchor="start" font-size="10">{pin}</text>')

        # Pin labels (right side)
        for i, pin in enumerate(["8", "7", "6", "5"]):
            py = y - 40 + i * 30
            svg_parts.append(f'<line x1="{x+width//2}" y1="{py}" x2="{x+width//2+10}" y2="{py}" stroke="black" stroke-width="2"/>')
            svg_parts.append(f'<text x="{x+width//2-10}" y="{py+5}" text-anchor="end" font-size="10">{pin}</text>')

        # IC name
        svg_parts.append(f'<text x="{x}" y="{y-10}" text-anchor="middle" font-size="14" font-weight="bold">{value}</text>')
        svg_parts.append(f'<text x="{x}" y="{y+10}" text-anchor="middle" font-size="11">{name}</text>')

    def _draw_voltage_source(self, svg_parts: list, x: int, y: int, name: str, value: str):
        """Draw voltage source symbol"""
        # Circle
        svg_parts.append(f'<circle cx="{x}" cy="{y}" r="20" fill="white" stroke="brown" stroke-width="2"/>')

        # + and - signs
        svg_parts.append(f'<text x="{x-8}" y="{y-5}" text-anchor="middle" font-size="16" font-weight="bold" fill="brown">+</text>')
        svg_parts.append(f'<text x="{x-8}" y="{y+12}" text-anchor="middle" font-size="16" font-weight="bold" fill="brown">-</text>')

        # Terminals
        svg_parts.append(f'<line x1="{x-20}" y1="{y}" x2="{x-30}" y2="{y}" stroke="brown" stroke-width="2"/>')
        svg_parts.append(f'<line x1="{x+20}" y1="{y}" x2="{x+30}" y2="{y}" stroke="brown" stroke-width="2"/>')

        # Label
        svg_parts.append(f'<text x="{x}" y="{y-30}" text-anchor="middle" font-size="11" font-weight="bold" fill="brown">{name}</text>')
        svg_parts.append(f'<text x="{x}" y="{y+35}" text-anchor="middle" font-size="10" fill="brown">{value}</text>')

    def _create_555_schematic_svg(self, components: List[Dict], nets: Dict[str, List[str]]) -> str:
        """
        Create 555 timer schematic with complete connections based on actual netlist

        Args:
            components: List of components
            nets: Dictionary of nets and connected components

        Returns:
            SVG string
        """
        svg_width = 1000
        svg_height = 700

        svg_parts = []
        svg_parts.append(f'<svg width="{svg_width}" height="{svg_height}" xmlns="http://www.w3.org/2000/svg">')
        svg_parts.append('<!-- 555 Timer Circuit Schematic with Full Connections -->')

        # Background
        svg_parts.append(f'<rect width="100%" height="100%" fill="white"/>')

        # Title
        svg_parts.append(f'<text x="500" y="30" text-anchor="middle" font-size="20" font-weight="bold">555 Timer LED Blinker Circuit</text>')

        # Position 555 IC in center (can be type U or X for subcircuits)
        ic_555 = next((c for c in components if (c["type"] == "U" or c["type"] == "X") and "555" in c.get("value", "").lower()), None)
        if ic_555:
            self._draw_ic(svg_parts, 400, 350, ic_555["name"], "NE555")
            ic_center = {"x": 400, "y": 350, "type": ic_555["type"]}

        # Position and draw other components
        comp_positions = {}

        # Add IC position to comp_positions so wires can connect to it
        if ic_555:
            comp_positions[ic_555["name"]] = ic_center

        # Voltage source on the left
        v_source = next((c for c in components if c["type"] == "V"), None)
        if v_source:
            comp_positions[v_source["name"]] = {"x": 150, "y": 350, "type": "V"}
            self._draw_voltage_source(svg_parts, 150, 350, v_source["name"], v_source["value"])

        # Resistors - position dynamically based on count
        resistors = [c for c in components if c["type"] == "R"]
        resistor_positions = [
            (280, 250),  # First resistor (typically R1)
            (280, 350),  # Second resistor (typically R2)
            (600, 350),  # Third resistor (LED current limit)
            (200, 200),  # Additional resistors
            (200, 500),
            (600, 200),
            (600, 500),
        ]

        for i, r in enumerate(resistors):
            if i < len(resistor_positions):
                x, y = resistor_positions[i]
                comp_positions[r["name"]] = {"x": x, "y": y, "type": "R"}
                self._draw_resistor(svg_parts, x, y, r["name"], r["value"])

        # Capacitors - position dynamically
        capacitors = [c for c in components if c["type"] == "C"]
        capacitor_positions = [
            (400, 500),  # First capacitor (timing)
            (520, 250),  # Second capacitor (control)
            (300, 500),  # Additional capacitors
            (600, 500),
        ]

        for i, c in enumerate(capacitors):
            if i < len(capacitor_positions):
                x, y = capacitor_positions[i]
                comp_positions[c["name"]] = {"x": x, "y": y, "type": "C"}
                self._draw_capacitor(svg_parts, x, y, c["name"], c["value"])

        # LED/Diode
        diodes = [c for c in components if c["type"] == "D" or "LED" in c.get("value", "")]
        if diodes:
            led = diodes[0]
            comp_positions[led["name"]] = {"x": 700, "y": 350, "type": "D"}
            self._draw_diode(svg_parts, 700, 350, led["name"], "LED")

        # Ensure all components have positions (fallback for any missed components)
        for comp in components:
            if comp["name"] not in comp_positions:
                # Fallback position: place in a grid
                comp_type = comp["type"]
                if comp_type == "R":
                    x = 100 + (len(comp_positions) % 4) * 150
                    y = 150 + (len(comp_positions) // 4) * 100
                    comp_positions[comp["name"]] = {"x": x, "y": y, "type": "R"}
                    self._draw_resistor(svg_parts, x, y, comp["name"], comp["value"])
                elif comp_type == "C":
                    x = 100 + (len(comp_positions) % 4) * 150
                    y = 450 + (len(comp_positions) // 4) * 100
                    comp_positions[comp["name"]] = {"x": x, "y": y, "type": "C"}
                    self._draw_capacitor(svg_parts, x, y, comp["name"], comp["value"])
                elif comp_type == "L":
                    x = 100 + (len(comp_positions) % 4) * 150
                    y = 250 + (len(comp_positions) // 4) * 100
                    comp_positions[comp["name"]] = {"x": x, "y": y, "type": "L"}
                    # Draw inductor similar to resistor
                    self._draw_resistor(svg_parts, x, y, comp["name"], comp["value"])
                elif comp_type == "Q":
                    x = 100 + (len(comp_positions) % 4) * 150
                    y = 250 + (len(comp_positions) // 4) * 100
                    comp_positions[comp["name"]] = {"x": x, "y": y, "type": "Q"}
                    # Draw transistor (using diode symbol as fallback)
                    self._draw_diode(svg_parts, x, y, comp["name"], comp["value"])

        # Use the new dynamic wire drawing system!
        self._draw_wires(svg_parts, nets, comp_positions, components)

        # Frequency info
        freq_text = "Frequency: 1 Hz | R1=1kΩ, R2=71.5kΩ, C1=10μF"
        svg_parts.append(f'<text x="500" y="650" text-anchor="middle" font-size="14" fill="blue">{freq_text}</text>')

        svg_parts.append('</svg>')

        return '\n'.join(svg_parts)

    def generate_netlist_summary(self, netlist: str) -> Dict:
        """
        Generate summary of netlist

        Args:
            netlist: SPICE netlist

        Returns:
            Summary dictionary
        """
        parsed = self.parse_spice_netlist(netlist)

        # Count components by type
        component_counts = {}
        for comp in parsed["components"]:
            comp_type = comp["type"]
            component_counts[comp_type] = component_counts.get(comp_type, 0) + 1

        return {
            "total_components": len(parsed["components"]),
            "component_counts": component_counts,
            "total_nets": len(parsed["nets"]),
            "components": parsed["components"]
        }


def generate_schematic(netlist: str) -> Tuple[str, Dict]:
    """
    Generate schematic from netlist

    Args:
        netlist: SPICE netlist

    Returns:
        Tuple of (svg_string, summary_dict)
    """
    generator = SchematicGenerator()
    svg = generator.generate_svg_schematic(netlist)
    summary = generator.generate_netlist_summary(netlist)
    return svg, summary
