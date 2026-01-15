"""
SPICE Netlist Parser
Parses SPICE netlists into structured data for schematic generation
"""
import re
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass


@dataclass
class Component:
    """Represents an electronic component"""
    name: str
    type: str  # R, C, L, D, V, I, Q, U, X, etc.
    nodes: List[str]
    value: str
    model: str = ""
    parameters: Dict[str, str] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


@dataclass
class Net:
    """Represents a net (connection point)"""
    name: str
    connections: List[str]  # Component names connected to this net


class SPICEParser:
    """Parse SPICE netlist files into structured data"""

    def __init__(self):
        self.components: List[Component] = []
        self.nets: Dict[str, List[str]] = {}
        self.title: str = ""
        self.comments: List[str] = []

    def parse(self, netlist: str) -> Dict[str, Any]:
        """
        Parse SPICE netlist string

        Args:
            netlist: SPICE netlist as string

        Returns:
            Dictionary with components, nets, and metadata
        """
        self.components = []
        self.nets = {}
        self.title = ""
        self.comments = []

        lines = netlist.strip().split('\n')

        for line in lines:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Handle comments
            if line.startswith('*') or line.startswith('//'):
                comment = line.lstrip('*').lstrip('/').strip()
                if comment and not self.title:
                    self.title = comment
                self.comments.append(comment)
                continue

            # Handle continuation lines
            if line.startswith('+'):
                if self.components:
                    # Append to previous component's parameters
                    prev_comp = self.components[-1]
                    params = self._parse_parameters(line[1:].strip())
                    prev_comp.parameters.update(params)
                continue

            # Parse component line
            try:
                self._parse_component_line(line)
            except Exception as e:
                print(f"Warning: Failed to parse line '{line}': {e}")
                continue

        # Build nets from component connections
        self._build_nets()

        return {
            'title': self.title,
            'components': [
                {
                    'name': c.name,
                    'type': c.type,
                    'nodes': c.nodes,
                    'value': c.value,
                    'model': c.model,
                    'parameters': c.parameters
                }
                for c in self.components
            ],
            'nets': self.nets,
            'comments': self.comments
        }

    def _parse_component_line(self, line: str):
        """Parse a single component line"""
        # Split by whitespace
        parts = line.split()

        if not parts or len(parts) < 2:
            return

        # Component name (first character indicates type)
        name = parts[0]
        comp_type = name[0].upper()

        # Special handling for subcircuits (X)
        if comp_type == 'X':
            self._parse_subcircuit(parts)
            return

        # Parse based on component type
        # Two-terminal components: R, L, C, D -> NAME node1 node2 value [params]
        # Voltage sources: V -> NAME node1 node2 TYPE value [params]
        # Current sources: I -> NAME node1 node2 TYPE value [params]
        # Transistors: Q -> NAME c b e model [params]
        # ICs: U -> NAME pin1 pin2 ... [params]

        nodes = []
        value = ""
        model = ""
        parameters = {}

        i = 1  # Start after component name

        # Handle two-terminal components (R, L, C, D)
        if comp_type in ['R', 'L', 'C', 'D']:
            # Need at least: NAME node1 node2 value
            if len(parts) >= 4:
                nodes = [parts[1], parts[2]]
                value = parts[3]
                i = 4
            else:
                # Malformed, try to extract what we can
                while i < len(parts) and len(nodes) < 2:
                    nodes.append(parts[i])
                    i += 1
                if i < len(parts):
                    value = parts[i]
                    i += 1

        # Handle voltage sources (V)
        elif comp_type == 'V':
            # Format: VNAME node1 node2 TYPE value
            # TYPE can be DC, AC, PULSE, etc.
            if len(parts) >= 4:
                nodes = [parts[1], parts[2]]
                # The next part might be a type (DC, AC, etc.)
                if parts[3].upper() in ['DC', 'AC', 'PULSE', 'SIN', 'EXP', 'PWL', 'SFFM']:
                    value = parts[3]  # Store the type as value
                    # If there's another part after, it might be the magnitude
                    if len(parts) >= 5 and '=' not in parts[4]:
                        value = f"{parts[3]} {parts[4]}"
                        i = 5
                    else:
                        i = 4
                else:
                    value = parts[3]
                    i = 4
            else:
                # Malformed
                while i < len(parts) and len(nodes) < 2:
                    nodes.append(parts[i])
                    i += 1

        # Handle current sources (I) - same as V
        elif comp_type == 'I':
            if len(parts) >= 4:
                nodes = [parts[1], parts[2]]
                if parts[3].upper() in ['DC', 'AC', 'PULSE', 'SIN', 'EXP', 'PWL', 'SFFM']:
                    value = parts[3]
                    if len(parts) >= 5 and '=' not in parts[4]:
                        value = f"{parts[3]} {parts[4]}"
                        i = 5
                    else:
                        i = 4
                else:
                    value = parts[3]
                    i = 4
            else:
                while i < len(parts) and len(nodes) < 2:
                    nodes.append(parts[i])
                    i += 1

        # Handle transistors (Q, M, J)
        elif comp_type in ['Q', 'M', 'J']:
            # Format: QNAME c b e model [params]
            # Need at least 3 nodes + model
            if len(parts) >= 5:
                nodes = parts[1:4]  # collector, base, emitter
                model = parts[4]
                i = 5
            else:
                # Try to extract what we can
                while i < len(parts) and len(nodes) < 3:
                    nodes.append(parts[i])
                    i += 1
                if i < len(parts):
                    model = parts[i]
                    i += 1

        # Handle ICs (U) - unknown number of pins
        elif comp_type == 'U':
            # Everything between name and value/model are nodes
            while i < len(parts):
                part = parts[i]
                if '=' in part:
                    break
                # Try to detect if this looks like a value/model
                # Models are usually alphanumeric without special chars
                # Values usually start with digit or special SPICE keywords
                if self._looks_like_value(part, comp_type) or (part.isalpha() and len(part) > 2):
                    # This might be a model or value
                    if not value:
                        value = part
                        i += 1
                        break
                nodes.append(part)
                i += 1

        # Parse remaining parameters
        while i < len(parts):
            part = parts[i]
            if '=' in part:
                key, val = part.split('=', 1)
                parameters[key] = val
            i += 1

        # Create component
        component = Component(
            name=name,
            type=comp_type,
            nodes=nodes,
            value=value,
            model=model,
            parameters=parameters
        )

        self.components.append(component)

    def _looks_like_value(self, part: str, comp_type: str) -> bool:
        """Check if a part looks like a value for the given component type"""
        # Values typically start with digit
        if not part:
            return False

        # Numeric values (with optional unit suffix)
        if part[0].isdigit() or part[0] == '.':
            return True

        # Special SPICE values (DC, AC, PULSE, etc.)
        if part.upper() in ['DC', 'AC', 'PULSE', 'SIN', 'EXP', 'PWL', 'SFFM']:
            return True

        return False

    def _parse_subcircuit(self, parts: List[str]):
        """Parse subcircuit call (X component)"""
        # Format: XNAME nodes... SUBCIRCUIT_NAME params...
        name = parts[0]

        # Nodes are everything between name and subcircuit name
        nodes = []
        subcircuit_name = ""
        parameters = {}

        i = 1
        while i < len(parts):
            part = parts[i]

            # Check if this looks like a parameter (contains =)
            if '=' in part:
                break

            # Check if this might be the subcircuit name
            # (typically subcircuit names are uppercase and don't look like node names)
            if part.upper() == part and not part[0].isdigit() and i > 1:
                subcircuit_name = part
                i += 1
                break

            nodes.append(part)
            i += 1

        # Parse remaining parameters
        while i < len(parts):
            part = parts[i]
            if '=' in part:
                key, val = part.split('=', 1)
                parameters[key.strip()] = val.strip()
            i += 1

        component = Component(
            name=name,
            type='X',  # Subcircuit
            nodes=nodes,
            value=subcircuit_name,  # Store subcircuit name as value
            model=subcircuit_name,
            parameters=parameters
        )

        self.components.append(component)

    def _is_value(self, part: str, comp_type: str) -> bool:
        """Check if a part looks like a value for the given component type"""
        # Common value patterns
        if re.match(r'^\d+\.?\d*[kKmMuUnNpP]?\$', part):
            return True

        # Specific component type patterns
        if comp_type in ['R', 'L', 'C']:
            return re.match(r'^\d+', part) is not None

        if comp_type == 'V':
            return part.upper() in ['DC', 'AC', 'PULSE', 'SIN', 'EXP', 'PWL']

        if comp_type == 'Q':
            # Transistor model name
            return part.isalpha() or part.isalnum()

        return False

    def _parse_parameters(self, param_str: str) -> Dict[str, str]:
        """Parse parameter string like R=1K C=1u"""
        params = {}
        parts = param_str.split()
        for part in parts:
            if '=' in part:
                key, val = part.split('=', 1)
                params[key.strip()] = val.strip()
        return params

    def _build_nets(self):
        """Build net connections from components"""
        # Collect all unique nodes and their connections
        node_connections = {}

        for comp in self.components:
            for node in comp.nodes:
                if node not in node_connections:
                    node_connections[node] = []
                node_connections[node].append(comp.name)

        # Create net objects
        # Ground (0) is always a net
        if '0' in node_connections:
            self.nets['0'] = node_connections['0']

        # Other significant nodes
        for node, connections in node_connections.items():
            if len(connections) >= 2:  # Only create nets for nodes with 2+ connections
                net_name = node
                self.nets[net_name] = connections

    def get_components_by_type(self, comp_type: str) -> List[Component]:
        """Get all components of a specific type"""
        return [c for c in self.components if c.type == comp_type]

    def get_component(self, name: str) -> Component:
        """Get a component by name"""
        for comp in self.components:
            if comp.name == name:
                return comp
        return None


def parse_spice_netlist(netlist: str) -> Dict[str, Any]:
    """
    Convenience function to parse SPICE netlist

    Args:
        netlist: SPICE netlist string

    Returns:
        Parsed circuit data
    """
    parser = SPICEParser()
    return parser.parse(netlist)
