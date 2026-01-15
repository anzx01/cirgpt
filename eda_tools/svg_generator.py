"""
Industrial-Grade SVG Schematic Generator
Uses graph-based automatic placement and pin-to-pin routing algorithms
"""
import json
import math
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass


@dataclass
class Point:
    x: float
    y: float


@dataclass
class ComponentLayout:
    name: str
    comp_type: str
    value: str
    x: float
    y: float
    width: float
    height: float
    pins: List[Dict[str, Any]]  # Each pin: {num, net, x, y relative to component}


class SVGSchematicGenerator:
    """Generate SVG schematics with automatic placement and routing"""

    # Component dimensions (in grid units)
    COMP_DIMENSIONS = {
        'R': {'width': 80, 'height': 40},  # Resistor
        'C': {'width': 60, 'height': 40},  # Capacitor
        'L': {'width': 80, 'height': 40},  # Inductor
        'D': {'width': 60, 'height': 40},  # Diode
        'V': {'width': 80, 'height': 60},  # Voltage source
        'I': {'width': 80, 'height': 60},  # Current source
        'Q': {'width': 100, 'height': 80},  # Transistor
        'U': {'width': 120, 'height': 120},  # IC
        'X': {'width': 120, 'height': 120},  # Subcircuit
    }

    def __init__(self, spice_data: Dict[str, Any]):
        """
        Initialize generator with parsed SPICE data

        Args:
            spice_data: Parsed SPICE data from SPICEParser
        """
        self.spice_data = spice_data
        self.components: List[ComponentLayout] = []
        self.net_wires: Dict[str, List[Point]] = {}  # net_name -> list of wire points

    def generate(self) -> str:
        """
        Generate SVG schematic

        Returns:
            SVG string
        """
        # Step 1: Place components using force-directed layout
        self._place_components()

        # Step 2: Route wires between pins (pin-to-pin)
        self._route_wires()

        # Step 3: Generate SVG
        svg = self._render_svg()

        return svg

    def _place_components(self):
        """Place components using force-directed graph layout"""
        components = self.spice_data.get('components', [])
        nets = self.spice_data.get('nets', {})

        # Build connection graph
        graph = {}
        for comp in components:
            graph[comp['name']] = {'connections': [], 'type': comp['type']}

        # Count connections between components
        for net_name, connections in nets.items():
            for i, comp1 in enumerate(connections):
                for comp2 in connections[i+1:]:
                    if comp1 != comp2:
                        graph[comp1]['connections'].append(comp2)
                        graph[comp2]['connections'].append(comp1)

        # Initial placement in a grid
        grid_size = 200
        cols = math.ceil(math.sqrt(len(components)))
        comp_positions = {}

        for idx, comp in enumerate(components):
            row = idx // cols
            col = idx % cols
            comp_positions[comp['name']] = Point(col * grid_size, row * grid_size)

        # Force-directed layout algorithm
        iterations = 100
        k = 150  # Optimal distance
        width_factor = 0.1  # Repulsion factor
        length_factor = 0.01  # Attraction factor

        for iteration in range(iterations):
            # Calculate forces
            forces = {name: Point(0, 0) for name in comp_positions}

            # Repulsion between all components
            for name1 in comp_positions:
                for name2 in comp_positions:
                    if name1 != name2:
                        p1 = comp_positions[name1]
                        p2 = comp_positions[name2]
                        dx = p1.x - p2.x
                        dy = p1.y - p2.y
                        dist = math.sqrt(dx*dx + dy*dy) or 1
                        force = k * k / dist
                        forces[name1].x += (dx / dist) * force * width_factor
                        forces[name1].y += (dy / dist) * force * width_factor

            # Attraction along connections
            for name, data in graph.items():
                for connected in data['connections']:
                    if connected in comp_positions:
                        p1 = comp_positions[name]
                        p2 = comp_positions[connected]
                        dx = p1.x - p2.x
                        dy = p1.y - p2.y
                        dist = math.sqrt(dx*dx + dy*dy) or 1
                        force = (dist - k) * length_factor
                        forces[name].x -= (dx / dist) * force
                        forces[name].y -= (dy / dist) * force

            # Apply forces
            for name in comp_positions:
                # Limit movement
                max_move = 10
                move_x = max(-max_move, min(max_move, forces[name].x))
                move_y = max(-max_move, min(max_move, forces[name].y))

                comp_positions[name].x += move_x
                comp_positions[name].y += move_y

                # Keep in positive quadrant
                comp_positions[name].x = max(50, comp_positions[name].x)
                comp_positions[name].y = max(50, comp_positions[name].y)

        # Create component layouts with pin positions
        for comp in components:
            name = comp['name']
            comp_type = comp['type']
            pos = comp_positions.get(name, Point(100, 100))

            dims = self.COMP_DIMENSIONS.get(comp_type, {'width': 80, 'height': 60})
            nodes = comp.get('nodes', [])

            # Calculate pin positions
            pins = []
            num_pins = len(nodes)
            if num_pins > 0:
                pin_spacing = dims['height'] / (num_pins + 1)
                for i, node in enumerate(nodes):
                    pin_y = (i + 1) * pin_spacing
                    pins.append({
                        'num': str(i + 1),
                        'net': node,
                        'x': 0,  # Left side of component
                        'y': pin_y
                    })

            layout = ComponentLayout(
                name=name,
                comp_type=comp_type,
                value=comp.get('value', ''),
                x=pos.x,
                y=pos.y,
                width=dims['width'],
                height=dims['height'],
                pins=pins
            )

            self.components.append(layout)

    def _route_wires(self):
        """Route wires between connected pins using Manhattan routing"""
        nets = self.spice_data.get('nets', {})

        for net_name, connections in nets.items():
            if net_name == '0':  # Ground symbol handled separately
                continue

            # Get all pins connected to this net
            pin_points = []
            for comp_name in connections:
                comp_layout = self._find_component_layout(comp_name)
                if comp_layout:
                    for pin in comp_layout.pins:
                        if pin['net'] == net_name:
                            # Absolute position of pin
                            abs_x = comp_layout.x + pin['x']
                            abs_y = comp_layout.y + pin['y']
                            pin_points.append(Point(abs_x, abs_y))

            # Create wires connecting pins (daisy chain)
            if len(pin_points) >= 2:
                self.net_wires[net_name] = self._create_wire_path(pin_points)

    def _create_wire_path(self, points: List[Point]) -> List[Point]:
        """
        Create Manhattan routing path between points

        Uses daisy-chain routing with horizontal/vertical segments only
        """
        if len(points) < 2:
            return points

        # Sort points by x coordinate
        sorted_points = sorted(points, key=lambda p: p.x)

        wire_path = []

        for i in range(len(sorted_points) - 1):
            p1 = sorted_points[i]
            p2 = sorted_points[i + 1]

            # Manhattan routing: horizontal then vertical
            # Go from p1 to midpoint
            mid_x = (p1.x + p2.x) / 2

            wire_path.append(p1)
            wire_path.append(Point(mid_x, p1.y))
            wire_path.append(Point(mid_x, p2.y))
            wire_path.append(p2)

        return wire_path

    def _find_component_layout(self, name: str) -> ComponentLayout:
        """Find component layout by name"""
        for comp in self.components:
            if comp.name == name:
                return comp
        return None

    def _render_svg(self) -> str:
        """Render final SVG"""
        # Calculate canvas size
        max_x = 0
        max_y = 0
        for comp in self.components:
            max_x = max(max_x, comp.x + comp.width + 100)
            max_y = max(max_y, comp.y + comp.height + 100)

        width = max_x + 100
        height = max_y + 100

        # SVG header
        svg_lines = [
            f'<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            f'<style>',
            f'  .component {{ fill: none; stroke: #000; stroke-width: 2; }}',
            f'  .wire {{ fill: none; stroke: #00f; stroke-width: 2; }}',
            f'  .pin {{ fill: #000; }}',
            f'  .text {{ font-family: Arial, sans-serif; font-size: 12px; fill: #000; }}',
            f'  .value {{ font-family: Arial, sans-serif; font-size: 10px; fill: #666; }}',
            f'</style>',
            f''
        ]

        # Draw wires
        for net_name, wire_points in self.net_wires.items():
            if len(wire_points) >= 2:
                path_data = f"M {wire_points[0].x:.1f} {wire_points[0].y:.1f}"
                for point in wire_points[1:]:
                    path_data += f" L {point.x:.1f} {point.y:.1f}"

                svg_lines.append(f'<path class="wire" d="{path_data}" />')
                svg_lines.append(f'<text class="value" x="{wire_points[0].x + 5}" y="{wire_points[0].y - 5}">{net_name}</text>')

        # Draw components
        for comp in self.components:
            # Component body
            svg_lines.append(f'<rect class="component" x="{comp.x:.1f}" y="{comp.y:.1f}" '
                           f'width="{comp.width:.1f}" height="{comp.height:.1f}" rx="5" />')

            # Component name
            svg_lines.append(f'<text class="text" x="{comp.x + 5}" y="{comp.y + 15}">{comp.name}</text>')

            # Component value
            if comp.value:
                svg_lines.append(f'<text class="value" x="{comp.x + 5}" y="{comp.y + comp.height - 5}">{comp.value}</text>')

            # Draw pins
            for pin in comp.pins:
                pin_abs_x = comp.x + pin['x']
                pin_abs_y = comp.y + pin['y']
                svg_lines.append(f'<circle class="pin" cx="{pin_abs_x:.1f}" cy="{pin_abs_y:.1f}" r="3" />')

        # Ground symbols
        nets = self.spice_data.get('nets', {})
        if '0' in nets:
            for comp_name in nets['0']:
                comp_layout = self._find_component_layout(comp_name)
                if comp_layout:
                    for pin in comp_layout.pins:
                        if pin['net'] == '0':
                            pin_abs_x = comp_layout.x + pin['x']
                            pin_abs_y = comp_layout.y + pin['y']
                            self._draw_ground_symbol(svg_lines, pin_abs_x, pin_abs_y)

        # SVG footer
        svg_lines.append('</svg>')

        return '\n'.join(svg_lines)

    def _draw_ground_symbol(self, svg_lines: List[str], x: float, y: float):
        """Draw ground symbol at given position"""
        size = 15
        # Vertical line
        svg_lines.append(f'<line class="component" x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y + size:.1f}" />')
        # Three horizontal lines
        svg_lines.append(f'<line class="component" x1="{x - size:.1f}" y1="{y + size:.1f}" x2="{x + size:.1f}" y2="{y + size:.1f}" />')
        svg_lines.append(f'<line class="component" x1="{x - size * 0.6:.1f}" y1="{y + size + 5:.1f}" x2="{x + size * 0.6:.1f}" y2="{y + size + 5:.1f}" />')
        svg_lines.append(f'<line class="component" x1="{x - size * 0.3:.1f}" y1="{y + size + 10:.1f}" x2="{x + size * 0.3:.1f}" y2="{y + size + 10:.1f}" />')


def generate_schematic_svg(spice_data: Dict[str, Any]) -> str:
    """
    Convenience function to generate SVG schematic from SPICE data

    Args:
        spice_data: Parsed SPICE data from SPICEParser

    Returns:
        SVG string
    """
    generator = SVGSchematicGenerator(spice_data)
    return generator.generate()


# For testing
if __name__ == '__main__':
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from spice_parser import SPICEParser

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

    parser = SPICEParser()
    spice_data = parser.parse(test_netlist)

    generator = SVGSchematicGenerator(spice_data)
    svg = generator.generate()

    with open('test_svg_output.svg', 'w') as f:
        f.write(svg)

    print(f"Generated SVG: {len(svg)} bytes")
    print(f"SVG saved to: test_svg_output.svg")
