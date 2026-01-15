"""
KiCad Netlist Generator
Converts parsed SPICE data to KiCad netlist format for netlistsvg
"""
import json
from typing import Dict, List, Any
from dataclasses import dataclass


class KiCadNetlistConverter:
    """Convert SPICE parsed data to KiCad netlist JSON format"""

    # Component type mapping from SPICE to KiCad
    COMP_TYPE_MAPPING = {
        'R': 'R',  # Resistor
        'C': 'C',  # Capacitor
        'L': 'L',  # Inductor
        'D': 'D',  # Diode
        'Q': 'Q',  # Transistor
        'V': 'V',  # Voltage source
        'I': 'I',  # Current source
        'U': 'U',  # Integrated circuit
        'X': 'U',  # Subcircuit -> treat as IC
        'T': 'U',  # Transformer -> treat as IC
    }

    # KiCad reference prefix mapping
    REF_PREFIX_MAPPING = {
        'R': 'R',
        'C': 'C',
        'L': 'L',
        'D': 'D',
        'Q': 'Q',
        'V': 'V',
        'I': 'V',
        'U': 'U',
        'X': 'U',
    }

    def __init__(self):
        self.netlist = {
            "exportVersion": 1,
            "design": {
                "title": "",
                "date": "",
                "tool": "CirGPT",
                "sheet": 1
            },
            "components": [],
            "modules": {},  # Old KiCad format required by netlistsvg (dictionary, not array)
            "nets": [],
            "libraries": []
        }

    def convert(self, spice_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert parsed SPICE data to KiCad netlist format

        Args:
            spice_data: Parsed SPICE data from SPICEParser

        Returns:
            KiCad netlist as dictionary (can be converted to JSON)
        """
        # Reset netlist
        self.netlist = {
            "exportVersion": 1,
            "design": {
                "title": spice_data.get('title', 'Circuit'),
                "date": "",
                "tool": "CirGPT",
                "sheet": 1
            },
            "components": [],
            "modules": {},  # Old KiCad format required by netlistsvg (dictionary)
            "nets": [],
            "libraries": []
        }

        # Convert components
        for comp in spice_data.get('components', []):
            kicad_comp = self._convert_component(comp)
            if kicad_comp:
                self.netlist['components'].append(kicad_comp)

                # Also add to modules (old KiCad format) - use reference as key
                kicad_module = self._create_module_from_component(kicad_comp)
                if kicad_module:
                    ref = kicad_comp['ref']
                    self.netlist['modules'][ref] = kicad_module

        # Convert nets
        net_id = 0
        for net_name, connections in spice_data.get('nets', {}).items():
            kicad_net = {
                "code": net_id,
                "name": self._sanitize_net_name(net_name),
                "nodes": []
            }

            # Add nodes (component connections)
            for comp_name in connections:
                node = self._create_node(comp_name, net_name, spice_data)
                if node:
                    kicad_net['nodes'].append(node)

            self.netlist['nets'].append(kicad_net)
            net_id += 1

        return self.netlist

    def _convert_component(self, spice_comp: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a single SPICE component to KiCad format"""
        name = spice_comp['name']
        comp_type = spice_comp['type']
        value = spice_comp.get('value', '')
        nodes = spice_comp.get('nodes', [])

        # Map component type
        kicad_type = self.COMP_TYPE_MAPPING.get(comp_type, comp_type)

        # Determine reference designator
        ref_prefix = self.REF_PREFIX_MAPPING.get(comp_type, comp_type)
        ref_des = f"{ref_prefix}{name[1:]}" if len(name) > 1 else name

        # KiCad component object
        kicad_comp = {
            "ref": ref_des,
            "val": value or spice_comp.get('model', ''),
            "footprint": "",
            "properties": {
                "Sheetname": "",
                "Sheetfile": ""
            },
            "fields": [],
            "pins": []
        }

        # Add pins based on component type and nodes
        for i, node in enumerate(nodes):
            pin_num = i + 1
            kicad_comp['pins'].append({
                "num": str(pin_num),
                "net": self._sanitize_net_name(node)
            })

        # Add library link (simplified)
        kicad_comp['lib'] = self._get_library_name(kicad_type, value)

        return kicad_comp

    def _create_node(self, comp_name: str, net_name: str,
                     spice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a node (connection point) for a net"""
        # Find the component
        comp = None
        for c in spice_data.get('components', []):
            if c['name'] == comp_name:
                comp = c
                break

        if not comp:
            return None

        # Find which pin connects to this net
        nodes = comp.get('nodes', [])
        try:
            pin_index = nodes.index(net_name)
            pin_num = pin_index + 1  # KiCad uses 1-based pin numbering
        except ValueError:
            return None

        ref_des = comp_name
        return {
            "ref": ref_des,
            "pin": str(pin_num)
        }

    def _sanitize_net_name(self, net_name: str) -> str:
        """Sanitize net name for KiCad format"""
        # Common conversions
        if net_name == '0':
            return 'GND'

        # Remove special characters
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', net_name)

        # Ensure it doesn't start with a number
        if sanitized and sanitized[0].isdigit():
            sanitized = 'net_' + sanitized

        return sanitized or 'Unnamed'

    def _get_library_name(self, comp_type: str, value: str) -> str:
        """Get KiCad library name for a component"""
        # Simplified library mapping
        if comp_type == 'R':
            return 'Device'
        elif comp_type == 'C':
            return 'Device'
        elif comp_type == 'L':
            return 'Device'
        elif comp_type == 'D':
            return 'Device'
        elif comp_type == 'Q':
            return 'Transistor'
        elif comp_type == 'U':
            # Try to determine specific library from value
            if '555' in value.upper():
                return 'Timer'
            elif 'OP' in value.upper() or 'LM' in value.upper():
                return 'Amplifier_Operational'
            else:
                return 'MCU'
        else:
            return 'Misc'

    def _create_module_from_component(self, kicad_comp: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a module entry (old KiCad format) from a component

        Args:
            kicad_comp: Component dictionary in KiCad format

        Returns:
            Module dictionary
        """
        # In the old KiCad format, modules are similar to components
        # but with slightly different structure
        module = {
            "reference": kicad_comp['ref'],
            "value": kicad_comp['val'],
            "footprint": kicad_comp.get('footprint', ''),
            "lib_id": f"{kicad_comp.get('lib', 'Misc')}:{kicad_comp['val']}",
            "properties": kicad_comp.get('properties', {}),
            "fields": kicad_comp.get('fields', []),
            "pins": kicad_comp.get('pins', []),
            "lib_source": {
                "lib": kicad_comp.get('lib', 'Misc'),
                "part": kicad_comp['val']
            }
        }
        return module

    def to_json(self, spice_data: Dict[str, Any], indent: int = 2) -> str:
        """
        Convert SPICE data to KiCad netlist JSON string

        Args:
            spice_data: Parsed SPICE data
            indent: JSON indentation

        Returns:
            JSON string
        """
        netlist = self.convert(spice_data)
        return json.dumps(netlist, indent=indent)

    def save_json_file(self, spice_data: Dict[str, Any], filename: str):
        """
        Save KiCad netlist to JSON file

        Args:
            spice_data: Parsed SPICE data
            filename: Output filename
        """
        netlist = self.convert(spice_data)
        with open(filename, 'w') as f:
            json.dump(netlist, f, indent=2)


def convert_spice_to_kicad(spice_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to convert SPICE data to KiCad netlist

    Args:
        spice_data: Parsed SPICE data from SPICEParser

    Returns:
        KiCad netlist dictionary
    """
    converter = KiCadNetlistConverter()
    return converter.convert(spice_data)


import re
