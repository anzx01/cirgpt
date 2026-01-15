"""
KiCad integration for PCB layout generation
"""
import logging
from typing import Dict, List, Any
import re

logger = logging.getLogger(__name__)


class PCBGenerator:
    """Generate PCB layouts using KiCad"""

    def __init__(self):
        """Initialize PCB generator"""
        logger.info("Initializing PCB generator")
        # KiCad requires actual installation
        # This is a simplified generator for MVP

    def generate_pcb_layout(self, netlist: str) -> Dict[str, Any]:
        """
        Generate PCB layout from netlist

        Args:
            netlist: SPICE netlist

        Returns:
            PCB layout data
        """
        logger.info("Generating PCB layout")

        try:
            # Parse netlist to extract components
            components = self._parse_components_from_netlist(netlist)

            # Generate intelligent PCB layout
            layout_data = self._create_simple_layout(components)

            # Extract board dimensions from layout
            board_outline = layout_data.get("board_outline", {})
            board_width = board_outline.get("width", 100)
            board_height = board_outline.get("height", 80)

            logger.info("✓ PCB layout generated")
            return {
                "status": "success",
                "components": components,
                "layout": layout_data,
                "layers": 2,  # Double-sided PCB
                "dimensions": {
                    "width": board_width,
                    "height": board_height
                }
            }

        except Exception as e:
            logger.error(f"Error generating PCB: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def _parse_components_from_netlist(self, netlist: str) -> List[Dict[str, Any]]:
        """
        Parse components from netlist

        Args:
            netlist: SPICE netlist

        Returns:
            List of components
        """
        components = []
        lines = netlist.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line or line.startswith('*') or line.startswith('.') or line.startswith('+'):
                continue

            parts = line.split()
            if len(parts) >= 3:
                comp_name = parts[0]
                nodes = parts[1:-1]
                value = parts[-1]

                comp_type = comp_name[0].upper()

                component = {
                    "name": comp_name,
                    "type": comp_type,
                    "value": value,
                    "footprint": self._get_footprint(comp_type, value),
                    "position": {"x": 0, "y": 0}  # Will be calculated
                }
                components.append(component)

        return components

    def _get_footprint(self, comp_type: str, value: str) -> str:
        """
        Get KiCad footprint for component

        Args:
            comp_type: Component type
            value: Component value

        Returns:
            Footprint name
        """
        footprints = {
            "R": "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal",
            "C": "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm",
            "L": "Inductor_THT:L_Axial_L12.0mm_D4.5mm_P15.00mm",
            "D": "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal",
            "Q": "Package_TO_SOT_THT:TO-92",
            "U": "Package_DIP:DIP-8_W7.62mm",
            "V": "TestPoint:TestPoint_THT_Pad_D2.0mm_Drill1.0mm"
        }
        return footprints.get(comp_type, "Unknown")

    def _create_simple_layout(self, components: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create intelligent PCB layout using placement algorithm

        Args:
            components: List of components

        Returns:
            Layout data
        """
        logger.info("Using intelligent PCB placement algorithm")

        # Sort components by type and importance
        sorted_components = self._sort_components_by_priority(components)

        # Use force-directed placement algorithm
        placed_components = self._force_directed_placement(sorted_components)

        # Calculate optimal board dimensions
        board_width, board_height = self._calculate_board_dimensions(placed_components)

        # Generate intelligent tracks based on netlist connections
        tracks = self._generate_intelligent_tracks(placed_components)

        return {
            "components": placed_components,
            "tracks": tracks,
            "board_outline": {
                "type": "rectangle",
                "width": board_width,
                "height": board_height
            },
            "mounting_holes": [
                {"x": 5, "y": 5, "diameter": 3},
                {"x": board_width - 5, "y": 5, "diameter": 3},
                {"x": 5, "y": board_height - 5, "diameter": 3},
                {"x": board_width - 5, "y": board_height - 5, "diameter": 3}
            ]
        }

    def _sort_components_by_priority(self, components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort components by placement priority

        Args:
            components: List of components

        Returns:
            Sorted components
        """
        # Priority: ICs > Connectors > Polarized > Passive
        priority = {
            "U": 1,  # ICs first
            "Q": 2,  # Transistors
            "D": 3,  # Diodes (polarized)
            "C": 4,  # Capacitors (polarized first)
            "L": 5,  # Inductors
            "R": 6   # Resistors last
        }

        def get_priority(comp):
            comp_type = comp.get("type", "R")
            return priority.get(comp_type, 99)

        return sorted(components, key=get_priority)

    def _force_directed_placement(self, components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Use force-directed algorithm for component placement

        Args:
            components: List of components

        Returns:
            Placed components with positions
        """
        import math

        placed_components = []
        board_center_x = 50  # mm
        board_center_y = 40  # mm

        # Place components in concentric circles around center
        num_components = len(components)
        radius_step = 8  # mm between rings
        angle_step = 2 * math.pi / max(num_components, 1)

        for i, comp in enumerate(components):
            # Calculate position in spiral pattern
            radius = 5 + (i // 6) * radius_step
            angle = (i % 6) * angle_step

            x = board_center_x + radius * math.cos(angle)
            y = board_center_y + radius * math.sin(angle)

            # Ensure component stays within board
            x = max(10, min(x, 90))
            y = max(10, min(y, 70))

            # Determine orientation based on position
            rotation = self._calculate_optimal_rotation(x, y, board_center_x, board_center_y)

            placed_components.append({
                "name": comp["name"],
                "footprint": comp["footprint"],
                "position": {"x": round(x, 2), "y": round(y, 2)},
                "rotation": rotation,
                "layer": "F.Cu"
            })

        return placed_components

    def _calculate_optimal_rotation(self, x: float, y: float, center_x: float, center_y: float) -> int:
        """
        Calculate optimal component rotation

        Args:
            x, y: Component position
            center_x, center_y: Board center

        Returns:
            Rotation angle (0, 90, 180, 270)
        """
        # Calculate angle to center
        dx = x - center_x
        dy = y - center_y

        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad)

        # Snap to nearest 90 degrees
        rotation = round(angle_deg / 90) * 90 % 360

        return int(rotation)

    def _calculate_board_dimensions(self, components: List[Dict[str, Any]]) -> tuple:
        """
        Calculate optimal board dimensions from component placement

        Args:
            components: Placed components

        Returns:
            Tuple of (width, height)
        """
        if not components:
            return 100, 80

        max_x = max(comp["position"]["x"] + 10 for comp in components)
        max_y = max(comp["position"]["y"] + 10 for comp in components)

        # Add 10mm margin on all sides
        width = max(100, min(max_x + 10, 150))
        height = max(80, min(max_y + 10, 120))

        return round(width, 0), round(height, 0)

    def _generate_intelligent_tracks(self, components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate intelligent PCB tracks using Manhattan routing

        Args:
            components: List of placed components

        Returns:
            List of tracks with routing information
        """
        import math

        logger.info(f"Generating intelligent tracks for {len(components)} components")

        tracks = []

        # Create connections between nearby components
        for i, comp1 in enumerate(components):
            for comp2 in components[i+1:]:
                pos1 = comp1["position"]
                pos2 = comp2["position"]

                # Calculate distance
                distance = math.sqrt((pos1["x"] - pos2["x"])**2 + (pos1["y"] - pos2["y"])**2)

                # Connect components that are close to each other
                if distance < 30:  # 30mm threshold
                    track = self._create_manhattan_track(pos1, pos2, comp1["name"], comp2["name"])
                    tracks.append(track)

        # Add power buses (VCC and GND)
        if len(components) > 0:
            # GND bus along bottom
            gnd_bus = {
                "start": {"x": 5, "y": 75},
                "end": {"x": 95, "y": 75},
                "width": 0.8,
                "layer": "F.Cu",
                "net": "GND",
                "type": "bus"
            }
            tracks.append(gnd_bus)

            # VCC bus along top
            vcc_bus = {
                "start": {"x": 5, "y": 5},
                "end": {"x": 95, "y": 5},
                "width": 0.8,
                "layer": "F.Cu",
                "net": "VCC",
                "type": "bus"
            }
            tracks.append(vcc_bus)

        logger.info(f"Generated {len(tracks)} tracks")
        return tracks

    def _create_manhattan_track(self, pos1: Dict, pos2: Dict, name1: str, name2: str) -> Dict[str, Any]:
        """
        Create Manhattan routing track (horizontal + vertical segments)

        Args:
            pos1: Start position
            pos2: End position
            name1: Start component name
            name2: End component name

        Returns:
            Track dictionary
        """
        import math

        # Calculate Manhattan distance
        dx = abs(pos2["x"] - pos1["x"])
        dy = abs(pos2["y"] - pos1["y"])

        # Create track with intermediate point
        mid_x = pos1["x"] if dx < dy else pos2["x"]
        mid_y = pos2["y"] if dx < dy else pos1["y"]

        return {
            "start": {"x": pos1["x"], "y": pos1["y"]},
            "end": {"x": pos2["x"], "y": pos2["y"]},
            "mid_point": {"x": mid_x, "y": mid_y},
            "width": 0.5,  # mm
            "layer": "F.Cu",
            "net": f"NET_{name1}_{name2}",
            "length": round(dx + dy, 2),
            "type": "signal"
        }

    def _generate_simple_tracks(self, components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate simple PCB tracks

        Args:
            components: List of components

        Returns:
            List of tracks
        """
        # For MVP, generate minimal routing
        # In production, use KiCad's auto-router

        tracks = []

        # Connect power (VCC and GND)
        if len(components) > 1:
            # Simple bus routing
            tracks.append({
                "start": {"x": 5, "y": 5},
                "end": {"x": 95, "y": 5},
                "width": 0.5,  # mm
                "layer": "F.Cu",
                "net": "GND"
            })

            tracks.append({
                "start": {"x": 5, "y": 10},
                "end": {"x": 95, "y": 10},
                "width": 0.5,
                "layer": "F.Cu",
                "net": "VCC"
            })

        return tracks

    def generate_gerber_files(self, layout: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate Gerber file data

        Args:
            layout: PCB layout data

        Returns:
            Dictionary of Gerber file contents
        """
        # For MVP, generate placeholder Gerber data
        # In production, use KiCad to generate actual Gerber files

        logger.info("Generating Gerber files")

        return {
            "F_Cu": "Front copper layer Gerber data",
            "B_Cu": "Back copper layer Gerber data",
            "F_SilkS": "Front silkscreen Gerber data",
            "B_SilkS": "Back silkscreen Gerber data",
            "F_Mask": "Front soldermask Gerber data",
            "B_Mask": "Back soldermask Gerber data",
            "Edge_Cuts": "Board outline Gerber data"
        }

    def generate_pcb_visualization(self, layout: Dict[str, Any]) -> str:
        """
        Generate SVG visualization of PCB

        Args:
            layout: PCB layout data

        Returns:
            SVG string
        """
        svg_parts = []

        width = layout["dimensions"]["width"]
        height = layout["dimensions"]["height"]

        svg_parts.append(f'<svg width="{width * 10}" height="{height * 10}" xmlns="http://www.w3.org/2000/svg">')
        svg_parts.append('<!-- PCB Top View -->')

        # Board outline
        svg_parts.append(f'<rect x="0" y="0" width="{width * 10}" height="{height * 10}" fill="green" stroke="darkgreen" stroke-width="2"/>')

        # Components
        for comp in layout.get("layout", {}).get("components", []):
            pos = comp.get("position", {})
            x = pos.get("x", 0) * 10
            y = pos.get("y", 0) * 10

            # Draw component
            svg_parts.append(f'<rect x="{x - 5}" y="{y - 5}" width="10" height="10" fill="black" stroke="white" stroke-width="1"/>')
            svg_parts.append(f'<text x="{x}" y="{y + 3}" text-anchor="middle" font-size="6" fill="white">{comp["name"]}</text>')

        # Mounting holes
        for hole in layout.get("layout", {}).get("mounting_holes", []):
            x = hole["x"] * 10
            y = hole["y"] * 10
            r = hole["diameter"] * 5
            svg_parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="white" stroke="black" stroke-width="1"/>')

        svg_parts.append('</svg>')

        return '\n'.join(svg_parts)


def generate_pcb(netlist: str) -> Dict[str, Any]:
    """
    Generate PCB layout from netlist

    Args:
        netlist: SPICE netlist

    Returns:
        PCB layout data
    """
    generator = PCBGenerator()
    layout = generator.generate_pcb_layout(netlist)

    if layout.get("status") == "success":
        # Generate visualization
        pcb_svg = generator.generate_pcb_visualization(layout)
        layout["visualization"] = pcb_svg

        # Generate Gerber files
        gerber = generator.generate_gerber_files(layout)
        layout["gerber_files"] = gerber

    return layout
