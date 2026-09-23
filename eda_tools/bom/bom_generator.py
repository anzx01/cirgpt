"""
BOM (Bill of Materials) generation
"""
import logging
import csv
import re
from typing import Dict, List, Any
from io import StringIO

logger = logging.getLogger(__name__)

# Subcircuit instances whose model names a chip are ICs, not generic modules
_IC_MODEL_RE = re.compile(
    r"^(?:[a-z]{0,3}555|555|lm\d|tl\d|ne\d|ua7|adc\d|dac\d|atmega|attiny"
    r"|pic1|stm32|esp32|cd40|max\d|ds\d|74)",
    re.I,
)

# 登记器件的真实采购信息（与 mcp_schematic._REAL_PARTS 对应）
_REAL_MPN = {
    "ESP32-C3": ("Espressif ESP32-C3 (QFN-32)", "SMD, QFN-32 4x4mm", 1.20),
    "USB_C_Receptacle_USB2.0": ("HRO TYPE-C-31-M-12 16P", "SMD, USB-C 16P", 0.35),
    "AMS1117-3.3": ("AMS1117-3.3 (SOT-223)", "SMD, SOT-223", 0.15),
}

# IR 类型 -> BOM 类别。IR 里的语义类型比参考前缀可靠（led 不是二极管、
# fuse 不是未知件、tvs_diode 与整流二极管封装完全不同）。
_IR_BOM_TYPES = {
    "resistor": "Resistor",
    "capacitor": "Capacitor",
    "inductor": "Inductor",
    "led": "LED",
    "diode": "Diode",
    "tvs_diode": "TVS Diode",
    "zener_diode": "Diode",
    "schottky_diode": "Diode",
    "transistor": "Transistor",
    "mosfet": "Transistor",
    "connector": "Connector",
    "fuse": "Fuse",
    "switch": "Switch",
    "motor": "Motor",
    "pump": "Motor",
    "sensor": "Sensor",
    "mcu_module_esp32c3": "IC",
    "usb_c_power_connector": "Connector",
    "ldo_ams1117": "IC",
}

# 功率 MOSFET 常见型号（TO-220/TO-252 族），信号管才是 TO-92
_POWER_FET_RE = re.compile(r"^(irlz|irf|irl|stp|fqp|sup|buk|aod|ao)", re.I)


class BOMGenerator:
    """Generate Bill of Materials from netlist"""

    def __init__(self):
        """Initialize BOM generator"""
        # Component pricing database (simplified)
        self.component_prices = {
            "Resistor": 0.05,
            "Capacitor": 0.08,
            "Inductor": 0.15,
            "Diode": 0.10,
            "LED": 0.15,
            "Transistor": 0.20,
            "IC": 0.50,
            "Switch": 0.30,
            "Connector": 0.20,
            "Relay": 1.20,
            "Motor": 3.00,
            "Module": 1.50,
            "Sensor": 1.25,
            "Voltage Source": 0.00,
            "Current Source": 0.00
        }

    def generate_bom(self, netlist: str, design_name: str = "Circuit",
                     circuit_ir: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate BOM from netlist (or preferentially from CircuitIR)

        Args:
            netlist: SPICE netlist
            design_name: Name of the design
            circuit_ir: Optional CircuitIR; when present its components are
                the BOM source of truth (real refs/models), since netlist
                engineering models replace digital parts with sources.

        Returns:
            BOM data
        """
        logger.info("Generating BOM")

        try:
            # Parse components from netlist or IR
            if circuit_ir and circuit_ir.get("components"):
                components = self._components_from_ir(circuit_ir)
            else:
                components = self._parse_components(netlist)

            # Group by component type
            grouped_components = self._group_components(components)

            # Calculate costs
            cost_breakdown = self._calculate_costs(grouped_components)

            # Generate BOM entries
            bom_entries = self._create_bom_entries(grouped_components, cost_breakdown)

            # Calculate totals
            total_cost = sum(entry.get("unit_price", 0) * entry.get("quantity", 0)
                           for entry in bom_entries)
            total_components = sum(entry.get("quantity", 0) for entry in bom_entries)

            bom_data = {
                "design_name": design_name,
                "entries": bom_entries,
                "summary": {
                    "total_components": total_components,
                    "total_cost": round(total_cost, 2),
                    "unique_components": len(bom_entries)
                }
            }

            logger.info(f"✓ BOM generated: {total_components} components, ${total_cost:.2f}")
            return bom_data

        except Exception as e:
            logger.error(f"Error generating BOM: {e}")
            raise

    def _components_from_ir(self, ir: Dict[str, Any]) -> List[Dict[str, Any]]:
        """BOM component list straight from CircuitIR (real refs/models)."""
        components: List[Dict[str, Any]] = []
        for comp in ir.get("components") or []:
            if not isinstance(comp, dict):
                continue
            t = str(comp.get("type") or "").lower()
            if t in {"voltage_source", "signal_source", "supply", "power_source"}:
                continue  # 仿真源，不是采购件
            ref = str(comp.get("ref") or "").strip()
            if not ref:
                continue
            value = str(comp.get("model") or comp.get("value") or t or ref)
            comp_type = _IR_BOM_TYPES.get(t) or self._get_component_type(ref, value)
            components.append({
                "reference": ref,
                "type": comp_type,
                "value": value,
                "quantity": 1,
            })
        return components

    def _parse_components(self, netlist: str) -> List[Dict[str, Any]]:
        """
        Parse components from netlist

        Args:
            netlist: SPICE netlist

        Returns:
            List of components
        """
        components = []
        lines = netlist.strip().split('\n')

        subckt_depth = 0
        for line in lines:
            line = line.strip()
            # Skip comments, commands, and continuations
            if not line or line.startswith('*') or line.startswith('+'):
                continue
            low = line.lower()
            if low.startswith('.subckt'):
                subckt_depth += 1
                continue
            if subckt_depth:
                # behavioural macro-model internals are not purchasable parts
                if low.startswith('.ends'):
                    subckt_depth -= 1
                continue
            if line.startswith('.'):
                continue

            parts = line.split()
            if len(parts) >= 3:
                comp_name = parts[0]
                prefix = comp_name[0].upper()
                value_index = self._value_index(prefix, parts)
                if value_index is None:
                    continue
                value = parts[value_index]
                if self._is_nonphysical_source(comp_name, prefix, value):
                    continue

                comp_type = self._get_component_type(comp_name, value)

                component = {
                    "reference": comp_name,
                    "type": comp_type,
                    "value": value,
                    "quantity": 1
                }
                components.append(component)

        return components

    def _is_nonphysical_source(self, comp_name: str, prefix: str, value: str) -> bool:
        """Skip behavioral sources that exist only to drive simulations."""
        return prefix in {"V", "I"} and (
            comp_name.upper() in {"VCTRL", "VOSC"}
            or value.upper().startswith(("PULSE", "SIN", "EXP", "PWL", "SFFM"))
        )

    def _value_index(self, prefix: str, parts: List[str]) -> int:
        """Return the token index that represents the purchasable part value."""
        if prefix in {"R", "L", "C", "D"} and len(parts) >= 4:
            return 3
        if prefix in {"V", "I"} and len(parts) >= 4:
            if len(parts) >= 5 and parts[3].upper() in {"DC", "AC", "PULSE", "SIN", "EXP", "PWL", "SFFM"}:
                return 4
            return 3
        if prefix == "S" and len(parts) >= 6:
            return 5
        if prefix in {"J", "K", "M", "X"} and len(parts) >= 2:
            return len(parts) - 1
        if prefix in {"Q"} and len(parts) >= 5:
            return 4
        if prefix in {"U", "X"} and len(parts) >= 2:
            return len(parts) - 1
        return len(parts) - 1

    def _get_component_type(self, comp_name: str, value: str) -> str:
        """
        Get component type from reference designator

        Args:
            comp_name: Component reference (e.g., R1, C1, U1)
            value: Component value

        Returns:
            Component type
        """
        prefix = comp_name[0].upper()

        type_map = {
            "R": "Resistor",
            "C": "Capacitor",
            "L": "Inductor",
            "D": "Diode",
            "Q": "Transistor",
            "S": "Switch",
            "U": "IC",
            "J": "Connector",
            "K": "Relay",
            "F": "Fuse",
            "M": "Motor",
            "X": "Module",
            "V": "Voltage Source",
            "I": "Current Source"
        }

        # Check for LED specifically
        lower_value = value.lower()
        if prefix == "X" and _IC_MODEL_RE.match(value):
            return "IC"
        if prefix == "J":
            return "Connector"
        if prefix == "K":
            return "Relay"
        if prefix == "M":
            return "Motor"
        if "led" in lower_value:
            return "LED"
        if "sensor" in lower_value:
            return "Sensor"
        if "pump" in lower_value or "motor" in lower_value or "fan" in lower_value:
            return "Motor"
        if "relay" in lower_value:
            return "Relay"
        if "connector" in lower_value or "terminal" in lower_value:
            return "Connector"

        return type_map.get(prefix, "Unknown")

    def _group_components(self, components: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """
        Group components by type and value

        Args:
            components: List of components

        Returns:
            Grouped components dictionary
        """
        grouped = {}

        for comp in components:
            comp_type = comp["type"]
            value = comp["value"]

            # Create group key
            group_key = f"{comp_type}_{value}"

            if group_key not in grouped:
                grouped[group_key] = {
                    "type": comp_type,
                    "value": value,
                    "references": [],
                    "quantity": 0
                }

            grouped[group_key]["references"].append(comp["reference"])
            grouped[group_key]["quantity"] += 1

        return grouped

    def _calculate_costs(self, grouped_components: Dict[str, Dict]) -> Dict[str, float]:
        """
        Calculate component costs

        Args:
            grouped_components: Grouped components

        Returns:
            Cost breakdown dictionary
        """
        costs = {}

        for key, comp in grouped_components.items():
            comp_type = comp["type"]

            # Get base price (登记器件使用真实估价)
            real_price = _REAL_MPN.get(str(comp.get("value") or ""))
            base_price = real_price[2] if real_price else self.component_prices.get(comp_type, 0.10)

            # Adjust price based on quantity (bulk discount)
            quantity = comp["quantity"]
            if quantity >= 100:
                multiplier = 0.8
            elif quantity >= 10:
                multiplier = 0.9
            else:
                multiplier = 1.0

            unit_price = base_price * multiplier
            costs[key] = round(unit_price, 4)

        return costs

    def _create_bom_entries(self, grouped_components: Dict[str, Dict],
                          costs: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Create BOM entries

        Args:
            grouped_components: Grouped components
            costs: Component costs

        Returns:
            List of BOM entries
        """
        entries = []

        for key, comp in grouped_components.items():
            entry = {
                "designator": ", ".join(comp["references"]),
                "quantity": comp["quantity"],
                "component_type": comp["type"],
                "value": comp["value"],
                "footprint": self._get_footprint(comp["type"], comp["value"]),
                "unit_price": costs[key],
                "total_price": round(costs[key] * comp["quantity"], 2),
                "supplier": "Generic",  # Could be expanded to query supplier APIs
                "part_number": self._get_part_number(comp["type"], comp["value"])
            }
            entries.append(entry)

        # Sort by component type
        entries.sort(key=lambda x: x["component_type"])

        return entries

    def _get_footprint(self, comp_type: str, value: str = "") -> str:
        """
        Get footprint for component type

        Args:
            comp_type: Component type
            value: Component value/model (registry parts carry real packages)

        Returns:
            Footprint description
        """
        real = _REAL_MPN.get(str(value or ""))
        if real:
            return real[1]
        if comp_type == "Transistor" and _POWER_FET_RE.match(str(value or "")):
            return "THT, TO-220"
        footprints = {
            "Resistor": "THT, Axial, 0.25W",
            "Capacitor": "THT, Radial, Disc",
            "Inductor": "THT, Axial",
            "Diode": "THT, DO-35",
            "TVS Diode": "THT, DO-35 / SMA",
            "LED": "THT, 3mm, Radial",
            "Transistor": "THT, TO-92",
            "IC": "THT, DIP-8",
            "Switch": "THT, Momentary Pushbutton",
            "Connector": "Screw terminal / pin header",
            "Relay": "THT, relay module",
            "Motor": "External load / terminal block",
            "Module": "Module / header",
            "Sensor": "Module / header",
            "Fuse": "THT, 5x20mm glass",
            "Voltage Source": "N/A",
            "Current Source": "N/A"
        }
        return footprints.get(comp_type, "Unknown")

    def _get_part_number(self, comp_type: str, value: str) -> str:
        """
        Get generic part number

        Args:
            comp_type: Component type
            value: Component value

        Returns:
            Part number
        """
        # 登记器件给出真实采购信息
        if value in _REAL_MPN:
            return _REAL_MPN[value][0]
        # Simplified part numbers
        return f"{comp_type.upper()}-{value.replace(' ', '-')}"

    def export_to_csv(self, bom_data: Dict[str, Any]) -> str:
        """
        Export BOM to CSV format

        Args:
            bom_data: BOM data

        Returns:
            CSV string
        """
        output = StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            "Designator",
            "Quantity",
            "Component Type",
            "Value",
            "Footprint",
            "Unit Price ($)",
            "Total Price ($)",
            "Supplier",
            "Part Number"
        ])

        # Write entries
        for entry in bom_data["entries"]:
            writer.writerow([
                entry["designator"],
                entry["quantity"],
                entry["component_type"],
                entry["value"],
                entry["footprint"],
                entry["unit_price"],
                entry["total_price"],
                entry["supplier"],
                entry["part_number"]
            ])

        # Write summary
        writer.writerow([])
        writer.writerow(["Summary"])
        writer.writerow(["Total Components:", bom_data["summary"]["total_components"]])
        writer.writerow(["Unique Components:", bom_data["summary"]["unique_components"]])
        writer.writerow(["Total Cost ($):", bom_data["summary"]["total_cost"]])

        return output.getvalue()

    def export_to_excel(self, bom_data: Dict[str, Any]) -> str:
        """
        Export BOM to Excel format (placeholder)

        Args:
            bom_data: BOM data

        Returns:
            Excel file data (base64)
        """
        # For MVP, return CSV
        # In production, use openpyxl to generate actual Excel files
        return self.export_to_csv(bom_data)


def generate_bom(netlist: str, design_name: str = "Circuit",
                 circuit_ir: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Generate BOM from netlist (or CircuitIR when provided)

    Args:
        netlist: SPICE netlist
        design_name: Design name

    Returns:
        BOM data
    """
    generator = BOMGenerator()
    bom_data = generator.generate_bom(netlist, design_name, circuit_ir=circuit_ir)

    # Add CSV export
    bom_data["csv"] = generator.export_to_csv(bom_data)

    return bom_data
