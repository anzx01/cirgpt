"""
KiCad MCP schematic generation from CircuitIR.

Runs the mcp-kicad-sch-api MCP server (a thin wrapper around the
kicad-sch-api library) as a stdio subprocess and drives it as an MCP
client: components are placed from a type -> library-symbol map, then
every net connection gets a net label on the symbol pin (power rails
get power-library symbols instead). Before the artifacts are returned,
kicad-cli exports a netlist and the connectivity is compared with the
IR's nets; a mismatch raises so the caller can fall back to the SKiDL
pipeline.

Requires the eda_tools venv: mcp (>=1,<2), kicad-sch-api, and the
mcp-kicad-sch-api wheel (vendored under eda_tools/wheels/).
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from math import cos, radians, sin
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class McpSchematicError(RuntimeError):
    """Raised when MCP-based KiCad generation cannot produce valid artifacts."""


# ---------------------------------------------------------------------------
# toolchain discovery (KiCad paths are shared with the SKiDL pipeline)

def _find_kicad() -> Tuple[Path, Path]:
    env_cli = os.environ.get("KICAD_CLI")
    if env_cli and Path(env_cli).exists():
        cli = Path(env_cli)
        return cli.resolve().parents[1], cli
    env_root = os.environ.get("KICAD_ROOT")
    for root in [Path(env_root)] if env_root else []:
        cli = root / "bin" / "kicad-cli.exe"
        if cli.exists():
            return root, cli
    which = shutil.which("kicad-cli")
    if which:
        cli = Path(which)
        return cli.resolve().parents[1], cli
    # Install location differs per machine (which drive, which version dir);
    # probe the common spots on every drive, newest version wins.
    from kicad_artifacts import scan_kicad_roots

    for root in scan_kicad_roots():
        return root, root / "bin" / "kicad-cli.exe"
    raise McpSchematicError(
        "KiCad CLI not found. Install KiCad or set KICAD_ROOT or KICAD_CLI."
    )


def _server_env(kicad_root: Path, kicad_cli: Path) -> Dict[str, str]:
    symbol_dir = kicad_root / "share" / "kicad" / "symbols"
    env = dict(os.environ)
    env.update(
        {
            "KICAD_ROOT": str(kicad_root),
            "KICAD_CLI": str(kicad_cli),
            "KICAD_SYMBOL_DIR": str(symbol_dir),
            "KICAD8_SYMBOL_DIR": str(symbol_dir),
            "KICAD9_SYMBOL_DIR": str(symbol_dir),
            "PYTHONUTF8": "1",
            "PATH": str(kicad_root / "bin") + os.pathsep + os.environ.get("PATH", ""),
        }
    )
    return env


def mcp_backend_available() -> bool:
    """True when the MCP server module can be imported by this venv."""
    try:
        import importlib.util

        return importlib.util.find_spec("mcp_kicad_sch_api") is not None
    except Exception:
        return False


# ---------------------------------------------------------------------------
# CircuitIR -> KiCad library mapping (ported from the SKiDL generic builder)

RES_FP = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal"
CAP_FP = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm"
CPOL_FP = "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm"
LED_FP = "LED_THT:LED_D5.0mm"
DIP8_FP = "Package_DIP:DIP-8_W7.62mm"
SW_FP = "Button_Switch_THT:SW_PUSH_6mm"
TP_FP = "TestPoint:TestPoint_THTPad_D1.5mm_Drill0.7mm"

_GND_NAMES = {"0", "GND", "VSS", "DGND", "AGND", "GROUND"}

_SOURCE_TYPES = {"dc_voltage_source", "dc_source", "voltage_source", "battery"}


def _is_gnd(name: Any) -> bool:
    return str(name).upper() in _GND_NAMES


def _rail_symbol(name: Any) -> Optional[str]:
    """Power-library symbol name for a rail net, or None."""
    n = str(name).upper().replace("-", "_")
    if n in {"VEE", "VSS", "V_", "VNEG", "V_NEG"}:
        return "VEE"
    if n in {"VCC", "VDD", "3V3", "3.3V"}:
        return "+3V3" if "3" in n else "VCC"
    if n in {"5V", "+5V", "VCC_5V", "VDD_5V", "VCC5V", "VBUS"}:
        return "+5V"
    if n in {"9V", "+9V", "VCC_9V"}:
        return "+9V"
    if n in {"12V", "+12V", "VIN_12V", "VCC_12V"}:
        return "+12V"
    if n in {"15V", "+15V", "VIN_15V"}:
        return "+15V"
    return None


def _subsystem_of(comp: Dict[str, Any]) -> str:
    """Grouping key for layout columns.

    The AI sometimes omits `subsystem` entirely (every component then lands in
    one "other" column, producing a 1:11 vertical strip). Fall back to the
    role's leading word (sensor_pullup -> sensor), then to a type class.
    """
    sub = str(comp.get("subsystem") or "").strip()
    if sub:
        return sub
    role = str(comp.get("role") or "").strip().lower().replace("-", "_")
    if role:
        head = role.split("_")[0]
        if head:
            return head
    t = str(comp.get("type") or "").strip().lower()
    if t in {"resistor", "capacitor", "cap"}:
        return "passive"
    if t in {"connector", "test_point"}:
        return "connector"
    return "other"


# ---------------------------------------------------------------------------
# 真实器件登记表
#
# 这些器件的符号、封装与引脚真值全部来自本机 KiCad 10 标准库（登记时
# 逐一核对过 .kicad_sym 引脚定义）。CircuitIR 里用语义引脚名（如 3V3、
# VBUS、VI），布线时由 _expand_real_part_connections 翻译成真实引脚号，
# 引脚号绝不由 LLM 编造。
# ---------------------------------------------------------------------------
_REAL_PARTS: Dict[str, Dict[str, Any]] = {
    "mcu_module_esp32c3": {
        "lib": "MCU_Espressif",
        "symbol": "ESP32-C3",
        "footprint": "Package_DFN_QFN:QFN-32-1EP_4x4mm_P0.4mm_EP2.65x2.65mm",
        "value_label": "ESP32-C3",
        "pins": {
            "3V3": ["2", "3", "11", "17", "31", "32"],  # 全部 VDD 引脚
            "GND": ["33"],
            "EN": ["7"],
            "TX": ["28"],   # U0TXD
            "RX": ["27"],   # U0RXD
            "IO2": ["6"],
            "IO4": ["9"],   # MTMS
            "IO5": ["10"],  # MTDI
            "IO6": ["12"],  # MTCK
            "IO7": ["13"],  # MTDO
            "IO8": ["14"],
            "IO9": ["15"],
            "IO10": ["16"],
            "IO18": ["25"],
            "IO19": ["26"],
        },
        "pin_aliases": {
            "3V3": ["3V3", "VCC", "VDD", "+3V3", "3.3V"],
            "GND": ["GND", "0", "VSS", "DGND"],
            "EN": ["EN", "CHIP_EN", "CHIP_EN/RESET"],
            "TX": ["TX", "UART_TX", "TXD", "TXD0", "U0TXD", "GPIO21"],
            "RX": ["RX", "UART_RX", "RXD", "RXD0", "U0RXD", "GPIO20"],
            "IO2": ["IO2", "GPIO2"],
            "IO4": ["IO4", "GPIO4", "MTMS"],
            "IO5": ["IO5", "GPIO5", "MTDI"],
            "IO6": ["IO6", "GPIO6", "MTCK"],
            "IO7": ["IO7", "GPIO7", "MTDO"],
            "IO8": ["IO8", "GPIO8"],
            "IO9": ["IO9", "GPIO9"],
            "IO10": ["IO10", "GPIO10"],
            "IO18": ["IO18", "GPIO18"],
            "IO19": ["IO19", "GPIO19"],
        },
    },
    "usb_c_power_connector": {
        "lib": "Connector",
        "symbol": "USB_C_Receptacle_USB2.0_16P",
        "footprint": "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
        "value_label": "USB_C_Receptacle_USB2.0",
        "pins": {
            "VBUS": ["A4", "A9", "B4", "B9"],
            "CC1": ["A5"],
            "CC2": ["B5"],
            "D+": ["A6", "B6"],
            "D-": ["A7", "B7"],
            "GND": ["A1", "B1", "A12", "B12"],
            "SHIELD": ["SH"],
        },
        "pin_aliases": {
            "VBUS": ["VBUS", "+5V", "5V", "VBUS_5V"],
            "CC1": ["CC1"],
            "CC2": ["CC2"],
            "D+": ["D+", "DP"],
            "D-": ["D-", "DM"],
            "GND": ["GND", "0", "VSS"],
            "SHIELD": ["SHIELD", "SH"],
        },
    },
    "ldo_ams1117": {
        "lib": "Regulator_Linear",
        "symbol": "AMS1117-3.3",
        "footprint": "Package_TO_SOT_SMD:SOT-223-3_TabPin2",
        "value_label": "AMS1117-3.3",
        "pins": {
            "VI": ["3"],
            "VO": ["2"],
            "GND": ["1"],
        },
        # LDO 的 IR 节点写的是所在网络名：输入网络常叫 VBUS/5V/VIN
        "pin_aliases": {
            "VI": ["VI", "VIN", "IN", "VBUS", "+5V", "5V"],
            "VO": ["VO", "VOUT", "OUT", "3V3", "+3V3", "3.3V"],
            "GND": ["GND", "0", "VSS"],
        },
    },
}

# 语义引脚名的常见同义词（LLM 措辞差异），翻译到登记表的标准名
_PIN_SYNONYMS: Dict[str, str] = {
    "VCC": "3V3", "VDD": "3V3", "3V3": "3V3", "+3V3": "3V3", "3.3V": "3V3",
    "GND": "GND", "0": "GND", "VSS": "GND", "DGND": "GND",
    "EN": "EN", "CHIP_EN": "EN", "CHIP_EN/RESET": "EN",
    "TX": "TX", "UART_TX": "TX", "TXD": "TX", "TXD0": "TX", "U0TXD": "TX", "GPIO21": "TX",
    "RX": "RX", "UART_RX": "RX", "RXD": "RX", "RXD0": "RX", "U0RXD": "RX", "GPIO20": "RX",
    "VBUS": "VBUS", "VBUS_5V": "VBUS", "+5V": "VBUS", "5V": "VBUS",
    "CC1": "CC1", "CC2": "CC2",
    "DP": "D+", "D+": "D+", "DM": "D-", "D-": "D-",
    "SHIELD": "SHIELD", "SH": "SHIELD",
    "VI": "VI", "VIN": "VI", "IN": "VI",
    "VO": "VO", "VOUT": "VO", "OUT": "VO",
}


def _real_part_key(comp: Dict[str, Any]) -> Optional[str]:
    """Registry key for a component, matched by canonical type or part text."""
    t = str(comp.get("type") or "").lower().strip()
    if t in _REAL_PARTS:
        return t
    text = " ".join(
        str(comp.get(k) or "") for k in ("value", "model", "manufacturer_part", "name")
    ).lower()
    if "esp32-c3" in text or "esp32c3" in text:
        return "mcu_module_esp32c3"
    if "ams1117" in text:
        return "ldo_ams1117"
    if "usb-c" in text or "usb_c" in text or "type-c" in text or "typec" in text:
        return "usb_c_power_connector"
    return None


def _expand_real_part_connections(
    ir: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """Normalize every net connection to a pin the placed symbol actually has.

    DeepSeek writes either style (and mixes them in one IR):

    * positional — ``ref.index`` with 1-based node position (the IR spec);
    * semantic — ``ref.name`` like ``J1.VBUS`` / ``U2.IO2`` / ``J2.TX``.

    Registry parts translate the semantic name to the real KiCad pin
    number(s), expanding multi-pin groups (VBUS x4, GND x4, ...) into one
    connection per physical pin. Generic parts resolve semantic names
    positionally: the node list's order IS the symbol's pin order
    (``J2.TX`` with nodes [3V3, TX, RX, GND] is pin 2). Unresolvable
    names are dropped and reported so the caller can disclose them
    instead of silently losing them.
    """
    components = {
        str(c.get("ref")): c for c in ir.get("components", []) if isinstance(c, dict)
    }
    dropped: List[str] = []

    def part_pin_info(ref: str):
        """(pins, alias->semantic) for a registry part, else None."""
        comp = components.get(ref)
        if comp is None:
            return None
        key = _real_part_key(comp)
        if key is None:
            return None
        part = _REAL_PARTS[key]
        alias_map: Dict[str, str] = {}
        for semantic, names in (part.get("pin_aliases") or {}).items():
            for n in names:
                alias_map[n.upper()] = semantic
        return part["pins"], alias_map

    def semantic_of(node: str, alias_map: Dict[str, str]) -> Optional[str]:
        """Canonical registry semantic name for an IR node label.

        Exact alias first; then a longest-prefix match so model-invented
        variants (VIN_FUSED -> VI, VBUS_PROT -> VBUS, 3V3_MCU -> 3V3)
        still land on the right pin instead of being dropped.
        """
        u = node.upper()
        if u in alias_map:
            return alias_map[u]
        syn = _PIN_SYNONYMS.get(u)
        if syn:
            return syn
        for cand in sorted(alias_map, key=len, reverse=True):
            if len(cand) > 1 and u.startswith(cand):
                return alias_map[cand]
        for cand in sorted(_PIN_SYNONYMS, key=len, reverse=True):
            if len(cand) > 1 and u.startswith(cand):
                return _PIN_SYNONYMS[cand]
        return None

    new_nets: List[Any] = []
    for net in ir.get("nets", []):
        if not isinstance(net, dict):
            new_nets.append(net)
            continue
        conns: List[str] = []
        extra: List[str] = []
        for conn in net.get("connections", []) or []:
            ref, _, pin = str(conn).rpartition(".")
            comp = components.get(ref)
            if comp is None:
                conns.append(str(conn))
                continue
            nodes = [str(n) for n in comp.get("nodes") or []]
            if pin.isdigit():
                idx = int(pin) - 1
                if idx < 0 or idx >= len(nodes):
                    dropped.append(f"{conn}(节点越界)")
                    continue
                node = nodes[idx].strip()
            else:
                node = pin.strip()
            info = part_pin_info(ref)
            if info is not None:
                pins_map, alias_map = info
                semantic = node if node in pins_map else semantic_of(node, alias_map)
                group = pins_map.get(semantic) if semantic else None
                if not group:
                    dropped.append(f"{ref}.{node}(未知引脚)")
                    continue
                conns.append(f"{ref}.{group[0]}")
                extra.extend(f"{ref}.{p}" for p in group[1:])
            else:
                # generic part: symbol pins are numbers; the node list is
                # positional, so a semantic label resolves to its slot
                if node in nodes:
                    conns.append(f"{ref}.{nodes.index(node) + 1}")
                else:
                    conns.append(str(conn))
        new_net = dict(net)
        new_net["connections"] = conns + extra
        new_nets.append(new_net)

    # A pin listed on TWO nets (LLMs name the pump return both PUMP_NEG and
    # GND) is one electrical node: merge those nets, rail name wins, and
    # disclose the merge instead of letting both a label and a power symbol
    # land on the same pin (KiCad: multiple_net_names).
    by_pin: Dict[str, List[int]] = {}
    for i, net in enumerate(new_nets):
        if not isinstance(net, dict):
            continue
        for conn in net.get("connections") or []:
            by_pin.setdefault(str(conn), []).append(i)
    merge_into: Dict[int, int] = {}
    merged_disclosures: List[str] = []
    for pin, owners in by_pin.items():
        owners = [i for i in dict.fromkeys(owners) if i not in merge_into]
        if len(owners) < 2:
            continue
        names = [str(new_nets[i].get("name")) for i in owners]
        target = next(
            (i for i in owners if _is_gnd(new_nets[i].get("name")) or _rail_symbol(new_nets[i].get("name"))),
            owners[0],
        )
        union: List[str] = []
        for i in owners:
            if i == target:
                continue
            merge_into[i] = target
            union.extend(str(c) for c in new_nets[i].get("connections") or [])
        keep = [c for c in new_nets[target].get("connections") or [] if c != pin]
        keep.append(pin)
        seen = set(keep)
        for c in union:
            if c not in seen:
                seen.add(c)
                keep.append(c)
        new_nets[target]["connections"] = keep
        merged_disclosures.append(
            f"引脚 {pin} 同时位于网络 {'、'.join(names)}；为同一电气节点，已合并为 "
            f"{new_nets[target].get('name')}"
        )
    if merge_into:
        new_nets = [
            n for i, n in enumerate(new_nets) if i not in merge_into
        ]

    expanded = dict(ir)
    expanded["nets"] = new_nets
    if merged_disclosures:
        expanded["warnings"] = list(ir.get("warnings") or []) + [
            "IR 网络修正：" + d for d in merged_disclosures
        ]
    return expanded, dropped


def _symbol_for(comp: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    key = _real_part_key(comp)
    if key is not None:
        part = _REAL_PARTS[key]
        return (part["lib"], part["symbol"])
    t = str(comp.get("type") or "").lower()
    v = str(comp.get("value") or "")
    vu = v.upper()
    if "screw" in v.lower():
        n = len(comp.get("nodes") or [])
        if 2 <= n <= 8:
            return ("Connector", f"Screw_Terminal_01x{n:02d}")
    if t == "resistor":
        return ("Device", "R")
    if t in {"capacitor", "cap"}:
        return ("Device", "C")
    if t == "inductor":
        return ("Device", "L")
    if t == "led":
        return ("Device", "LED")
    if t == "tvs_diode":
        return ("Device", "D_TVS")
    if t == "zener_diode":
        return ("Device", "D_Zener")
    if t == "diode":
        if any(k in vu for k in ("SS", "1N58", "SK", "BAT", "MBR")):
            return ("Device", "D_Schottky")
        return ("Device", "D")
    if t == "crystal":
        return ("Device", "Crystal")
    if t == "fuse":
        return ("Device", "Fuse")
    if t in {"switch", "button"}:
        return ("Switch", "SW_SPST")
    if t in {
        "mosfet",
        "transistor_mosfet",
        "fet",
        "power_mosfet",
        "nmos",
        "pmos",
        "nmosfet",
        "pmosfet",
        "n_mosfet",
        "p_mosfet",
        "n_channel_mosfet",
        "p_channel_mosfet",
        "n_channel_fet",
        "p_channel_fet",
    }:
        if "PMOS" in (t + vu).upper().replace(" ", "") or "-P" in vu:
            return ("Device", "Q_PMOS")
        return ("Device", "Q_NMOS")
    if t in {"bjt", "transistor", "transistor_npn", "npn_transistor"}:
        if "PNP" in vu:
            return ("Device", "Q_PNP")
        return ("Device", "Q_NPN")
    if t in {"transistor_pnp", "pnp_transistor"}:
        return ("Device", "Q_PNP")
    if t in {"linear_regulator", "voltage_regulator"}:
        return ("Regulator_Linear", "L7805")
    if t in {"timer_ic", "timer", "ne555", "555_timer"}:
        return ("Timer", "LM555xN")
    if t in {"opamp", "operational_amplifier", "ideal_opamp"}:
        return ("Amplifier_Operational", "LM358")
    # LM393-style comparator: DIP8 pinout is identical to the LM358 symbol
    # (1=OUT1 2=IN1- 3=IN1+ 4=GND 5=IN2+ 6=IN2- 7=OUT2 8=VCC).
    if t in {"comparator", "comparator_ic"}:
        return ("Amplifier_Operational", "LM358")
    if t == "microcontroller":
        return ("MCU_Microchip_ATmega", "ATmega328P-P")
    if t in _SOURCE_TYPES:
        # a supply drawn as a connector reads as "no power source here";
        # the SPICE DC source symbol carries + / - and the voltage value
        return ("Simulation_SPICE", "VDC")
    if t == "signal_source":
        return ("Simulation_SPICE", "VSIN")
    if t == "test_point":
        return ("Connector", "TestPoint")
    if t == "connector":
        n = len(comp.get("nodes") or [])
        if 2 <= n <= 8:
            return ("Connector_Generic", f"Conn_01x{n:02d}")
    n = len(comp.get("nodes") or [])
    if 2 <= n <= 8:
        return ("Connector_Generic", f"Conn_01x{n:02d}")
    return None


def _footprint_for(lib: str, sym: str, comp: Dict[str, Any]) -> str:
    key = _real_part_key(comp)
    if key is not None:
        return _REAL_PARTS[key]["footprint"]
    t = str(comp.get("type") or "").lower()
    if (lib, sym) == ("Device", "R"):
        return RES_FP
    if (lib, sym) == ("Device", "C"):
        try:
            return CPOL_FP if float(comp.get("value") or 0) >= 1e-6 else CAP_FP
        except (TypeError, ValueError):
            return CAP_FP
    if (lib, sym) == ("Device", "LED"):
        return LED_FP
    if t in {"timer_ic", "timer", "ne555", "555_timer"}:
        return DIP8_FP
    if t in {
        "opamp",
        "operational_amplifier",
        "ideal_opamp",
        "comparator",
        "comparator_ic",
    }:
        return DIP8_FP
    if t in {"switch", "button"}:
        return SW_FP
    if t == "test_point":
        return TP_FP
    return ""


def _fmt_value(comp: Dict[str, Any]) -> str:
    key = _real_part_key(comp)
    if key is not None:
        return str(_REAL_PARTS[key]["value_label"])
    t = str(comp.get("type") or "").lower()
    value = comp.get("value")
    unit = str(comp.get("unit") or "").strip()
    if value is None or value == "":
        return str(comp.get("ref") or t or "PART")

    def num(v: float) -> str:
        return f"{v:g}"

    try:
        fv = float(value)
    except (TypeError, ValueError):
        return str(value)

    if unit:
        if abs(fv) >= 1e9:
            return f"{num(fv / 1e9)}G{unit}"
        if abs(fv) >= 1e6:
            return f"{num(fv / 1e6)}M{unit}"
        if abs(fv) >= 1e3:
            return f"{num(fv / 1e3)}k{unit}"
        if abs(fv) != 0 and abs(fv) < 1:
            if abs(fv) >= 1e-3:
                return f"{num(fv * 1e3)}m{unit}"
            if abs(fv) >= 1e-6:
                return f"{num(fv * 1e6)}u{unit}"
            if abs(fv) >= 1e-9:
                return f"{num(fv * 1e9)}n{unit}"
            return f"{num(fv * 1e12)}p{unit}"
        return f"{num(fv)}{unit}"
    if t == "resistor":
        if abs(fv) >= 1_000_000:
            return f"{num(fv / 1_000_000)}M"
        if abs(fv) >= 1_000:
            return f"{num(fv / 1_000)}k"
        return num(fv)
    if t in {"capacitor", "cap"}:
        if abs(fv) >= 1e-3:
            return f"{num(fv)}F"
        if abs(fv) >= 1e-6:
            return f"{num(fv * 1e6)}uF"
        if abs(fv) >= 1e-9:
            return f"{num(fv * 1e9)}nF"
        return f"{num(fv * 1e12)}pF"
    if t == "inductor":
        if abs(fv) >= 1:
            return num(fv)
        return f"{num(fv * 1e6)}u"
    return num(fv)


def _safe_label(name: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9_+\-./]", "_", str(name).strip())
    return text or "NET"


_TRANSISTOR_LIBS = {
    "Device:Q_NMOS": {"gnd": "S", "rail": "D", "drive": "G", "load": "D"},
    "Device:Q_PMOS": {"gnd": "D", "rail": "S", "drive": "G", "load": "S"},
    "Device:Q_NPN": {"gnd": "E", "rail": "E", "drive": "B", "load": "C"},
    "Device:Q_PNP": {"gnd": "C", "rail": "C", "drive": "B", "load": "E"},
}


def _label_stub_len(label: str) -> float:
    """Stub length that keeps a net label's text clear of the pin it names.

    KiCad draws label text left-to-right from the anchor regardless of the
    label's rotation, so the wire stub must be at least as long as the text
    (about 0.9x font size per char) plus one grid of clearance, rounded up
    to a whole grid and never shorter than two grids.
    """
    return 2.54 * max(2, math.ceil((0.9 * 1.27 * len(label) + 1.27) / 2.54))


def _pin_aliases(
    placed: List[Tuple[Dict[str, Any], str, str]],
    ir_nets: List[Dict[str, Any]],
    pin_positions: Dict[Tuple[str, str], Tuple[float, float]],
) -> Dict[str, Dict[str, str]]:
    """Alias maps for letter-pinned symbols (e.g. KiCad 10 Q_NMOS uses D/G/S).

    IR pins are positional (pin k == nodes[k-1]); for three-terminal
    transistors the node's net identifies the role: the ground/rail node is
    the source/emitter, the node sharing a net with a driver (R*/U*) is the
    gate/base, the remaining one is the drain/collector.
    """
    net_members: Dict[str, List[str]] = {}
    for net in ir_nets:
        if isinstance(net, dict):
            net_members[str(net.get("name") or "")] = [
                str(c).rpartition(".")[0] for c in net.get("connections", []) or []
            ]

    aliases: Dict[str, Dict[str, str]] = {}
    for comp, lib, sym in placed:
        ref = str(comp.get("ref") or "")
        roles = _TRANSISTOR_LIBS.get(f"{lib}:{sym}")
        symbol_pins = {pin for (r, pin) in pin_positions if r == ref}
        if not roles or not ref or any(p.isdigit() for p in symbol_pins):
            continue

        nodes = [str(n) for n in comp.get("nodes") or []][:3]
        if len(nodes) < 3:
            continue
        pin_role: Dict[str, str] = {}
        remaining = list(range(3))
        for idx, net_name in enumerate(nodes):
            if _is_gnd(net_name):
                pin_role[str(idx + 1)] = roles["gnd"]
                remaining.remove(idx)
                break
        if len(remaining) == 3:  # no ground node; try a power rail
            for idx, net_name in enumerate(nodes):
                if _rail_symbol(net_name):
                    pin_role[str(idx + 1)] = roles["rail"]
                    remaining.remove(idx)
                    break
        if len(remaining) >= 2:
            drive_idx = None
            for idx in remaining:
                members = net_members.get(nodes[idx], [])
                if any(m.startswith(("R", "U")) for m in members):
                    drive_idx = idx
                    break
            if drive_idx is None:
                drive_idx = remaining[0]
            pin_role[str(drive_idx + 1)] = roles["drive"]
            remaining.remove(drive_idx)
        # Whatever is left, in node order: first the load pin, then the
        # source/emitter pin (deterministic when the IR gives no hints).
        if remaining:
            pin_role[str(remaining[0] + 1)] = roles["load"]
            remaining = remaining[1:]
        if remaining:
            pin_role[str(remaining[0] + 1)] = roles["gnd"]

        usable = {num: pin for num, pin in pin_role.items() if pin in symbol_pins}
        if len(usable) == 3:
            aliases[ref] = usable
            logger.info("MCP builder: pin aliases for %s (%s): %s", ref, f"{lib}:{sym}", usable)
    return aliases


# ---------------------------------------------------------------------------
# MCP client helpers

_POS_RE = re.compile(r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)")


class _McpSession:
    """Small typed wrapper over an MCP client session for one server run."""

    def __init__(self, session) -> None:
        self._session = session
        self.calls: List[str] = []

    async def call(self, name: str, args: Dict[str, Any]) -> str:
        self.calls.append(name)
        result = await self._session.call_tool(name, args)
        text = result.content[0].text if result.content else ""
        if result.isError:
            raise McpSchematicError(f"MCP tool {name} failed: {text[:400]}")
        return text


# ---------------------------------------------------------------------------
# schematic file parsing for exact pin geometry
#
# The MCP server's get_component_pin_position applies a buggy transform, so
# pin positions are computed locally from the saved .kicad_sch instead:
# lib_symbols gives each pin's offset from the symbol origin, the instance's
# (at x y rot) places it. Everything is placed unrotated, so the transform
# reduces to a translation in practice.

def _child_blocks(text: str, start: int, end: int) -> List[Tuple[str, int, int]]:
    """Direct child s-expression blocks of the block spanning [start, end)."""
    blocks = []
    depth = 0
    in_string = False
    escaped = False
    block_start = -1
    i = start
    while i < end:
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
        elif ch == "(":
            depth += 1
            if depth == 2 and block_start < 0:
                block_start = i
        elif ch == ")":
            if depth == 2 and block_start >= 0:
                blocks.append((text[block_start:i + 1], block_start, i + 1))
                block_start = -1
            depth -= 1
        i += 1
    return blocks


def _unit_pins_from_symbol_block(block: str) -> Dict[int, Dict[str, Tuple[float, float]]]:
    """{unit: {pin_number: (dx, dy)}} for one symbol block.

    Unit 0 holds pins declared on the root symbol (shared by every unit);
    unit N >= 1 holds the pins of sub-symbol ``NAME_N_<convert>``.
    """
    units: Dict[int, Dict[str, Tuple[float, float]]] = {}
    stack: List[Tuple[str, int]] = [(block, 0)]
    while stack:
        current, unit_no = stack.pop()
        # Spans of child sub-symbol blocks; pins inside those spans belong to
        # the child's unit, not to this level.
        child_spans: List[Tuple[int, int]] = []
        for sub, ss, se in _child_blocks(current, 0, len(current)):
            sub_match = re.match(r"\(\s*symbol\s+\"([^\"]+)\"", sub)
            if sub_match:
                child_spans.append((ss, se))
                unit_m = re.search(r"_(\d+)_(\d+)$", sub_match.group(1))
                stack.append((sub, int(unit_m.group(1)) if unit_m else 0))
        for pin_match in re.finditer(r"\(\s*pin\b", current):
            start = pin_match.start()
            if any(ss <= start <= se for ss, se in child_spans):
                continue
            pin_open = start
            pin_close = _matching_paren(current, pin_open)
            pin_block = current[pin_open:pin_close + 1]
            at_match = re.search(
                r"\(\s*at\s+(-?[\d.]+)\s+(-?[\d.]+)(?:\s+-?[\d.]+)?\s*\)", pin_block
            )
            num_match = re.search(r'\(\s*number\s+"([^"]+)"', pin_block)
            if at_match and num_match:
                units.setdefault(unit_no, {})[num_match.group(1)] = (
                    float(at_match.group(1)),
                    float(at_match.group(2)),
                )
    return units


def _pin_offsets_from_lib_symbols(text: str) -> Dict[str, Dict[int, Dict[str, Tuple[float, float]]]]:
    """Map lib_id -> unit pin offsets from the embedded lib_symbols block."""
    lib_start = text.find("(lib_symbols")
    if lib_start < 0:
        return {}
    open_paren = text.find("(", lib_start)
    lib_end = _matching_paren(text, open_paren)
    if lib_end < 0:
        return {}

    result: Dict[str, Dict[int, Dict[str, Tuple[float, float]]]] = {}
    for block, _s, _e in _child_blocks(text, open_paren, lib_end + 1):
        name_match = re.match(r'\(\s*symbol\s+"([^"]+)"', block)
        if not name_match:
            continue
        units = _unit_pins_from_symbol_block(block)
        if units:
            result[name_match.group(1)] = units
    return result


def _symbol_units_from_lib(
    symbol_dir: Path, lib_ids: List[str]
) -> Dict[str, Dict[int, Set[str]]]:
    """{lib_id: {unit: {pin numbers}}} read from the KiCad symbol libraries.

    Tells the placer which units a multi-unit symbol is made of so IR-used
    units can be placed; single-unit symbols come back as {1: {...}}.
    """
    lib_text: Dict[str, str] = {}
    result: Dict[str, Dict[int, Set[str]]] = {}
    for lib_id in lib_ids:
        lib, _, name = lib_id.partition(":")
        if not name:
            continue
        if lib not in lib_text:
            path = Path(symbol_dir) / f"{lib}.kicad_sym"
            try:
                lib_text[lib] = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                lib_text[lib] = ""
        text = lib_text.get(lib, "")
        units: Dict[int, Set[str]] = {}
        # KiCad >= 10 lib files quote top-level symbols without the library
        # prefix; embedded lib_symbols blocks in schematics keep it. Aliases
        # carry an (extends "BASE") and keep their pins on the base symbol.
        name_pattern = r'\(\s*symbol\s+"(?:' + re.escape(lib_id) + r"|" + re.escape(name) + r')"'
        anchor = re.search(name_pattern, text)
        for _hop in range(8):
            if not anchor:
                break
            open_paren = text.find("(", anchor.start())
            end = _matching_paren(text, open_paren)
            if end < 0:
                break
            block = text[open_paren : end + 1]
            extends_m = re.search(r'\(\s*extends\s+"([^"]+)"', block)
            if not extends_m:
                for unit, pins in _unit_pins_from_symbol_block(block).items():
                    units[unit] = set(pins)
                break
            anchor = re.search(
                r'\(\s*symbol\s+"' + re.escape(extends_m.group(1)) + r'"', text
            )
        # Pins carrying unit 0 are common to every unit (LM555xN keeps its
        # power pins there): they render with unit 1, so fold them in rather
        # than letting the placer stack a phantom "unit 0" instance.
        common = units.pop(0, None)
        if common is not None:
            units.setdefault(1, set()).update(common)
        if not units:
            units = {1: set()}
        result[lib_id] = units
    return result


def _symbol_instances(text: str) -> List[Dict[str, Any]]:
    """Top-level symbol instances: lib_id, position, rotation, reference."""
    lib_start = text.find("(lib_symbols")
    open_paren = text.find("(", lib_start) if lib_start >= 0 else -1
    lib_end = _matching_paren(text, open_paren) if open_paren >= 0 else -1
    scan_from = lib_end + 1 if lib_end >= 0 else 0

    instances = []
    pos = scan_from
    while True:
        match = re.search(r"\n\s*\(symbol\b", text[pos:])
        if not match:
            break
        block_open = pos + match.start() + 1
        block_end = _matching_paren(text, text.find("(", block_open))
        if block_end < 0:
            break
        block = text[block_open:block_end + 1]
        pos = block_end + 1
        lib_id_m = re.search(r'\(\s*lib_id\s+"([^"]+)"', block)
        at_m = re.search(
            r"\(\s*at\s+(-?[\d.]+)\s+(-?[\d.]+)(?:\s+(-?[\d.]+))?\s*\)", block
        )
        unit_m = re.search(r"\(\s*unit\s+(\d+)\s*\)", block)
        ref_m = re.search(r'\(\s*property\s+"Reference"\s+"([^"]+)"', block)
        if lib_id_m and at_m and ref_m:
            instances.append(
                {
                    "lib_id": lib_id_m.group(1),
                    "x": float(at_m.group(1)),
                    "y": float(at_m.group(2)),
                    "rot": float(at_m.group(3) or 0),
                    "unit": int(unit_m.group(1)) if unit_m else 1,
                    "ref": ref_m.group(1),
                }
            )
    return instances


def _pin_positions_from_sch(text: str) -> Dict[Tuple[str, str], Tuple[float, float]]:
    """Exact {(ref, pin): (x, y)} for every placed symbol instance.

    A multi-unit instance only owns the pins of its own unit plus the pins
    shared at the symbol root; sibling units' pins belong to their own
    instances.
    """
    lib_units = _pin_offsets_from_lib_symbols(text)
    positions: Dict[Tuple[str, str], Tuple[float, float]] = {}
    for inst in _symbol_instances(text):
        units = lib_units.get(inst["lib_id"])
        if not units:
            continue
        pins = {**(units.get(0) or {}), **(units.get(inst["unit"]) or {})}
        if not pins:
            continue
        theta = radians(inst["rot"])
        cos_t, sin_t = cos(theta), sin(theta)
        for pin, (dx, dy) in pins.items():
            # Lib symbols store pin offsets y-up while the sheet is y-down, so
            # the offset is flipped before the (unused in practice) rotation.
            rx = dx * cos_t - dy * sin_t
            ry = -dx * sin_t - dy * cos_t
            positions[(inst["ref"], pin)] = (
                round(inst["x"] + rx, 4),
                round(inst["y"] + ry, 4),
            )
    return positions


def _run_cli(cmd: List[str], timeout: float = 60) -> subprocess.CompletedProcess:
    """kicad-cli with one patient retry.

    The first invocation on a cold symbol-library cache can exceed the
    normal timeout by a wide margin; a single transient timeout must not
    kill an otherwise complete generation. Two timeouts report failure
    honestly — the caller decides what to degrade.
    """
    last_err: Optional[subprocess.TimeoutExpired] = None
    for attempt, to in enumerate((timeout, timeout * 4)):
        if attempt:
            logger.info(
                "kicad-cli timed out after %ss (%s...); retrying patiently",
                timeout, " ".join(str(c) for c in cmd[:4]),
            )
        try:
            return subprocess.run(
                cmd, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=to,
            )
        except subprocess.TimeoutExpired as exc:
            last_err = exc
    return subprocess.CompletedProcess(
        cmd, returncode=-1, stdout="",
        stderr=f"kicad-cli timed out twice ({last_err})",
    )


def _pin_name_is_rail(name: Any) -> bool:
    """True when a pin's own name declares a power rail (VCC/VDD/GND/V+/V-).

    Functional supply names (an LDO's VI/VO, a USB receptacle's VBUS) are
    deliberately NOT rails here: they name the pin's role, not a global net,
    so the IR's net assignment for them must be kept.
    """
    u = str(name or "").upper().strip()
    if not u:
        return False
    if "GND" in u or u in {"VSS", "V-", "VEE", "VGND", "V+"}:
        return True
    if u == "VBUS":
        return False  # the USB 5 V bus name names a role, not a global rail
    return u in {"VCC", "VDD"} or _rail_symbol(u) is not None


def _remap_power_pins(
    ir_nets: List[Dict[str, Any]],
    pin_types: Dict[Tuple[str, str], Tuple[str, str]],
    pin_positions: Dict[Tuple[str, str], Tuple[float, float]],
) -> Tuple[List[Dict[str, Any]], Set[Tuple[str, str]]]:
    """Re-home IR connections that land supply pins on the wrong nets.

    Free-form IRs describe opamps as 5-pin behavioural parts, so their
    supply tail nodes land positionally wherever (LM358: pin 4 is V-,
    pin 8 is V+). Two repairs, applied net by net:

    * a rail net wired onto a pin that is not a supply pin of the rail's
      polarity moves to a free supply pin of that polarity - and moving
      off a pin frees it for the opposite rail (VCC leaving V- opens it
      for VEE);
    * a signal net never carries supply pins: they are dropped here and
      the power-attach pass re-homes each to the rail its pin name asks
      for (V- -> GND, V+ -> the design's main rail).

    Returns (rewritten nets, pins excluded from the connectivity gate).
    """

    def polarity_neg(ref: str, pin: str) -> Optional[bool]:
        name, etype = pin_types.get((ref, pin), ("", ""))
        if etype not in ("power_in", "power_out"):
            return None
        u = str(name).upper()
        return "GND" in u or u in {"VSS", "V-", "VEE", "VGND"}

    occupied: Set[Tuple[str, str]] = set()
    for net in ir_nets:
        if isinstance(net, dict):
            for conn in net.get("connections") or []:
                r, _, p = str(conn).rpartition(".")
                if r and p and (r, p) in pin_positions:
                    occupied.add((r, p))

    def free_power_pin(ref: str, neg: bool) -> Optional[Tuple[str, str]]:
        for (r2, p2), (nm2, et2) in sorted(pin_types.items()):
            if r2 != ref or et2 != "power_in":
                continue
            if (r2, p2) in occupied or (r2, p2) not in pin_positions:
                continue
            u2 = str(nm2).upper()
            if ("GND" in u2 or u2 in {"VSS", "V-", "VEE", "VGND"}) != neg:
                continue
            return (r2, p2)
        return None

    # Role remap for behavioural opamp/comparator IRs: their five nodes
    # follow [IN+, IN-, OUT, V+, V-], but the real DIP-8 symbol keeps
    # 1=OUT, 2=IN-, 3=IN+, 4=V-, 8=V+. Positional wiring then grounds the
    # output and drives inputs from the supply - the role map below sends
    # each node to the pin that plays its part. Enabled only when the tail
    # nodes sit on rail-ish nets (the convention's signature); a free-form
    # IR whose pin 4/5 carry signals keeps its positional wiring.
    pin_net: Dict[Tuple[str, str], str] = {}
    for net in ir_nets:
        if isinstance(net, dict):
            nm = str(net.get("name") or "")
            for conn in net.get("connections") or []:
                r, _, pn = str(conn).rpartition(".")
                if r and pn:
                    pin_net.setdefault((r, pn), nm)

    rewrite: Dict[Tuple[str, str], str] = {}
    refs = sorted({r for r, _p in pin_net})
    for ref in refs:
        declared = sorted({p for r, p in pin_net if r == ref})
        if declared != ["1", "2", "3", "4", "5"]:
            continue
        plus = minus = out = pos = neg = None
        for (r2, p2), (nm2, et2) in sorted(pin_types.items()):
            if r2 != ref or (r2, p2) not in pin_positions:
                continue
            n2 = str(nm2)
            if n2 == "+" and plus is None:
                plus = p2
            elif n2 == "-" and minus is None:
                minus = p2
            elif et2 == "output" and out is None:
                out = p2
            elif et2 == "power_in":
                u2 = n2.upper()
                if "GND" in u2 or u2 in {"VSS", "V-", "VEE", "VGND"}:
                    neg = neg or p2
                else:
                    pos = pos or p2
        if not all((plus, minus, out, pos, neg)):
            continue
        net_of = lambda k: pin_net.get((ref, k), "")
        if all(
            _is_gnd(net_of(k)) or _rail_symbol(net_of(k)) for k in ("4", "5")
        ):
            # opamp convention [IN+, IN-, OUT, V+, V-]: rails at the tail
            role_map = {"1": plus, "2": minus, "3": out, "4": pos, "5": neg}
        elif (
            _rail_symbol(net_of("1"))
            and not _is_gnd(net_of("1"))
            and _is_gnd(net_of("2"))
        ):
            # comparator convention [V+, GND, IN-, OUT, IN+]: rails at the
            # head, inverting input first
            role_map = {"1": pos, "2": neg, "3": minus, "4": out, "5": plus}
        else:
            continue
        if all(role_map[k] == k for k in role_map):
            continue
        for k, target in role_map.items():
            if target != k:
                rewrite[(ref, k)] = target
                logger.info(
                    "MCP wiring: opamp role remap %s.%s -> %s.%s", ref, k, ref, target
                )

    if rewrite:
        for net in ir_nets:
            if isinstance(net, dict):
                net["connections"] = [
                    f"{r}.{rewrite.get((r, p), p)}"
                    if (r, p) in rewrite
                    else str(c)
                    for c in (net.get("connections") or [])
                    for r, _x, p in [str(c).rpartition(".")]
                ]
        # refresh the occupancy/pin_net view the supply rules work from
        pin_net = {}
        for net in ir_nets:
            if isinstance(net, dict):
                nm = str(net.get("name") or "")
                for conn in net.get("connections") or []:
                    r, _, pn = str(conn).rpartition(".")
                    if r and pn:
                        pin_net.setdefault((r, pn), nm)
        occupied = {
            (r, p) for (r, p) in pin_net if (r, p) in pin_positions
        }

    gate_dropped: Set[Tuple[str, str]] = set()
    nets_out: List[Dict[str, Any]] = []
    for net in ir_nets:
        if not isinstance(net, dict):
            nets_out.append(net)
            continue
        name = str(net.get("name") or "")
        railish = bool(_is_gnd(name) or _rail_symbol(name))
        want_neg = _is_gnd(name) or str(name).upper() in {"VEE", "VSS", "V-"}
        conns = [str(c) for c in (net.get("connections") or [])]
        new_conns: List[str] = []
        for conn in conns:
            ref, _, pin = conn.rpartition(".")
            pol = polarity_neg(ref, pin) if (ref, pin) in pin_positions else None
            if pol is None:
                new_conns.append(conn)  # not a supply pin: faithful wiring
                continue
            if railish and pol == want_neg:
                new_conns.append(conn)  # already the right supply pin
                continue
            if not railish:
                # Supply pin on a signal net: only re-home it when the pin's
                # own NAME declares a rail (VCC/VDD/GND/V+/V-...). Functional
                # names (an LDO's VI/VO, a DC-DC's SW) mean the IR put the
                # pin on that net on purpose - e.g. the regulator input on a
                # custom-named unregulated rail - and re-homing it to the
                # main rail would short input to output.
                if _pin_name_is_rail(pin_types.get((ref, pin), ("", ""))[0]):
                    gate_dropped.add((ref, pin))
                    occupied.discard((ref, pin))
                    logger.info(
                        "MCP wiring: signal net %s drops supply pin %s.%s (re-homed to its rail)",
                        name, ref, pin,
                    )
                    continue
                new_conns.append(conn)
                continue
            target = free_power_pin(ref, want_neg)
            if target:
                logger.info(
                    "MCP wiring: rail %s moves %s.%s -> %s.%s (%s)",
                    name, ref, pin, target[0], target[1], pin_types[target][0],
                )
                occupied.discard((ref, pin))
                occupied.add(target)
                gate_dropped.add((ref, pin))
                new_conns.append(f"{target[0]}.{target[1]}")
            else:
                new_conns.append(conn)
        nets_out.append({**net, "connections": new_conns})
    return nets_out, gate_dropped


def _pin_anchors(text: str) -> Dict[Tuple[str, str], Tuple[float, float]]:
    """{(ref, pin): owning instance centre} for multi-unit awareness.

    Each unit of a multi-unit symbol is its own instance with its own
    anchor; outward stub directions must be judged against the unit that
    actually owns the pin, not unit 1's anchor.
    """
    lib_units = _pin_offsets_from_lib_symbols(text)
    out: Dict[Tuple[str, str], Tuple[float, float]] = {}
    for inst in _symbol_instances(text):
        units = lib_units.get(inst["lib_id"])
        if not units:
            continue
        pins = {**(units.get(0) or {}), **(units.get(inst["unit"]) or {})}
        for pin in pins:
            out.setdefault((inst["ref"], pin), (inst["x"], inst["y"]))
    return out


def _pin_types_from_lib_symbols(text: str) -> Dict[str, Dict[str, Tuple[str, str]]]:
    """{lib_id: {pin number: (pin name, electrical type)}} from embedded symbols.

    Covers unit sub-symbols and root (common) pins alike; aliases that
    (extends "...") a base symbol resolve through to it.
    """
    lib_start = text.find("(lib_symbols")
    if lib_start < 0:
        return {}
    open_paren = text.find("(", lib_start)
    end = _matching_paren(text, open_paren)
    block_all = text[open_paren:end + 1] if end > 0 else text[lib_start:]

    out: Dict[str, Dict[str, Tuple[str, str]]] = {}

    def parse_symbol_block(lib_id: str, block: str) -> None:
        pins: Dict[str, Tuple[str, str]] = {}
        for m in re.finditer(
            r'\(\s*pin\s+(\w+)\s+\w+\s.*?\(\s*name\s+"([^"]*)".*?\(\s*number\s+"([^"]*)"',
            block, flags=re.DOTALL,
        ):
            etype, name, number = m.group(1), m.group(2), m.group(3)
            pins.setdefault(number, (name, etype))
        if pins:
            out.setdefault(lib_id, {}).update(pins)

    pos = 0
    while True:
        match = re.search(r'\(\s*symbol\s+"([^"]+)"', block_all[pos:])
        if not match:
            break
        lib_id = match.group(1)
        block_open = pos + match.start()
        open_paren2 = block_all.find("(", block_open)
        end2 = _matching_paren(block_all, open_paren2)
        if end2 < 0:
            break
        block = block_all[open_paren2:end2 + 1]
        pos = end2 + 1
        # skip nested unit sub-symbols ("NAME_1_1"): their pins repeat
        # inside the parent block this loop already visits
        if re.search(r'_\d+_\d+"', block_all[block_open:block_open + len(lib_id) + 4]):
            continue
        extends_m = re.search(r'\(\s*extends\s+"([^"]+)"', block)
        if extends_m:
            base = out.get(extends_m.group(1)) or out.get(
                f"{lib_id.rpartition(':')[0]}:{extends_m.group(1)}"
            )
            if base:
                out.setdefault(lib_id, {}).update(base)
            continue
        parse_symbol_block(lib_id, block)
    return out


def _pin_types_on_sheet(text: str) -> Dict[Tuple[str, str], Tuple[str, str]]:
    """{(ref, pin): (pin name, electrical type)} for every placed instance pin."""
    lib_types = _pin_types_from_lib_symbols(text)
    out: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for inst in _symbol_instances(text):
        types = lib_types.get(inst["lib_id"])
        if not types:
            continue
        for pin, name_type in types.items():
            out.setdefault((inst["ref"], pin), name_type)
    return out


def _sheet_wire_segments(text: str) -> List[Tuple[float, float, float, float]]:
    """All sheet wire segments ((x1, y1, x2, y2)), any polyline length."""
    segs: List[Tuple[float, float, float, float]] = []
    for m in re.finditer(r"\(\s*wire\s*\(pts((?:\s*\(xy [\d.\-]+ [\d.\-]+\))+)", text):
        pts = re.findall(r"\(xy ([\d.\-]+) ([\d.\-]+)", m.group(1))
        coords = [(float(a), float(b)) for a, b in pts]
        for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
            segs.append((x1, y1, x2, y2))
    return segs


def _unconnected_pins(
    text: str,
    pin_positions: Dict[Tuple[str, str], Tuple[float, float]],
    pin_types: Dict[Tuple[str, str], Tuple[str, str]],
) -> List[Dict[str, Any]]:
    """Placed component pins with nothing at their position.

    A pin counts as connected when a wire segment passes through its
    position, or a label / power-symbol pin / existing no-connect anchors
    exactly there. Power-symbol instances (#PWR/#FLG) themselves are not
    reported.
    """
    segs = _sheet_wire_segments(text)

    # KiCad connects a pin to a wire only when the pin's point coincides
    # with a wire ENDPOINT, or with an explicit junction on the wire's
    # interior - a wire merely passing through a pin does nothing.
    endpoints: Set[Tuple[float, float]] = set()
    for x1, y1, x2, y2 in segs:
        endpoints.add((x1, y1))
        endpoints.add((x2, y2))
    junctions: Set[Tuple[float, float]] = set()
    for m in re.finditer(r"\(\s*junction\b[^)]*?\(\s*at\s+([\d.\-]+)\s+([\d.\-]+)", text):
        junctions.add((float(m.group(1)), float(m.group(2))))

    def on_wire(px: float, py: float) -> bool:
        return (px, py) in endpoints or (px, py) in junctions

    anchors: Set[Tuple[float, float]] = set()
    for m in re.finditer(
        r"\(\s*(?:label|global_label|no_connect)\b[^)]*?\(\s*at\s+([\d.\-]+)\s+([\d.\-]+)", text
    ):
        anchors.add((float(m.group(1)), float(m.group(2))))
    power_pins = {
        pos for (ref, _pin), pos in pin_positions.items() if ref.startswith("#")
    }

    out: List[Dict[str, Any]] = []
    for (ref, pin), (px, py) in pin_positions.items():
        if ref.startswith("#"):
            continue
        if on_wire(px, py) or (px, py) in anchors or (px, py) in power_pins:
            continue
        name, etype = pin_types.get((ref, pin), ("", ""))
        out.append({"ref": ref, "pin": pin, "name": name, "etype": etype, "x": px, "y": py})
    return out


def _inject_no_connects(text: str, points: List[Tuple[float, float]]) -> str:
    """Append (no_connect (at x y)) stanzas just before the root close."""
    if not points:
        return text
    stanzas = []
    for x, y in points:
        u = uuid.uuid4()
        stanzas.append(f'\t(no_connect (at {x:g} {y:g}) (uuid "{u}"))\n')
    stripped = text.rstrip()
    if not stripped.endswith(")"):
        return text
    return stripped[:-1] + "\n" + "".join(stanzas) + ")\n"


# ---------------------------------------------------------------------------
# netlist validation gate

def _matching_paren(text: str, start: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return idx
    return -1


def _parse_netlist_nets(net_text: str) -> List[Tuple[str, Set[Tuple[str, str]]]]:
    """Return [(net_name, {(ref, pin), ...}), ...] from a kicadsexpr netlist."""
    nets_start = net_text.find("(nets")
    if nets_start < 0:
        return []
    nets_end = _matching_paren(net_text, net_text.find("(", nets_start))
    block = net_text[nets_start:nets_end]

    result: List[Tuple[str, Set[Tuple[str, str]]]] = []
    pos = 0
    while True:
        match = re.search(r"\((?:net|net\s)\b", block[pos:])
        if not match:
            break
        net_open = pos + match.start()
        net_close = _matching_paren(block, net_open)
        if net_close < 0:
            break
        body = block[net_open:net_close]
        pos = net_close + 1
        name_match = re.search(r'\(name\s+"([^"]*)"', body)
        nodes = {
            (m.group(1), m.group(2))
            for m in re.finditer(r'\(node\s*\(ref\s+"([^"]+)"\)\s*\(pin\s+"([^"]+)"\)', body)
        }
        result.append((name_match.group(1) if name_match else "", nodes))
    return result


def _connectivity_matches(
    ir_nets: List[Dict[str, Any]],
    placed_refs: Set[str],
    exported: List[Tuple[str, Set[Tuple[str, str]]]],
    pin_positions: Dict[Tuple[str, str], Tuple[float, float]],
    aliases: Dict[str, Dict[str, str]],
    dropped_pins: Set[Tuple[str, str]],
) -> bool:
    """Compare the IR's net partition with the exported netlist partition.

    Pins of components that were placed take part; power symbols (#PWR/#FLG)
    and unconnected pins are ignored. Pins that share a coordinate on the
    same symbol (e.g. stacked GND pins on some MCUs) are physically one node
    and are merged on both sides before comparing.
    """
    ir_pin_nets: Dict[Tuple[str, str], str] = {}
    for net in ir_nets:
        if not isinstance(net, dict):
            continue
        name = str(net.get("name") or "NET")
        for conn in net.get("connections", []) or []:
            ref, _, pin = str(conn).rpartition(".")
            if not ref or not pin:
                continue
            if ref not in placed_refs:
                continue
            if (ref, pin) in dropped_pins:
                continue  # pin does not exist on the symbol; already warned
            pin = aliases.get(ref, {}).get(pin, pin)
            ir_pin_nets.setdefault((ref, pin), name)

    exported_pin_nets: Dict[Tuple[str, str], str] = {}
    for _name, nodes in exported:
        for ref, pin in nodes:
            if ref.startswith("#"):
                continue
            exported_pin_nets.setdefault((ref, pin), _name)

    nodes = set(ir_pin_nets)
    parent: Dict[Tuple[str, str], Tuple[str, str]] = {n: n for n in nodes}

    def find(n: Tuple[str, str]) -> Tuple[str, str]:
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    def union(a: Tuple[str, str], b: Tuple[str, str]) -> None:
        parent[find(a)] = find(b)

    # IR side: pins sharing a net are one node.
    nets_of: Dict[str, List[Tuple[str, str]]] = {}
    for node, net_name in ir_pin_nets.items():
        nets_of.setdefault(net_name, []).append(node)
    for members in nets_of.values():
        for other in members[1:]:
            union(members[0], other)

    # Symbol side: pins sharing a coordinate are physically one node.
    by_coord: Dict[Tuple[float, float], List[Tuple[str, str]]] = {}
    for node in nodes:
        pos = pin_positions.get(node)
        if pos is not None:
            by_coord.setdefault(pos, []).append(node)
    for members in by_coord.values():
        for other in members[1:]:
            union(members[0], other)

    # Realized side: exported netlist membership (a pin placed but missing
    # from the export stayed unconnected, which breaks its IR net).
    for node in nodes:
        if node not in exported_pin_nets:
            exported_pin_nets[node] = f"__missing__{node[0]}_{node[1]}"
    realized: Dict[str, List[Tuple[str, str]]] = {}
    for node, net_name in exported_pin_nets.items():
        if node in nodes:
            realized.setdefault(net_name, []).append(node)
    for members in realized.values():
        for other in members[1:]:
            union(members[0], other)

    expected: Dict[Tuple[str, str], frozenset] = {}
    for n in nodes:
        expected.setdefault(find(n), set()).add(n)
    groups = {frozenset(members) for members in expected.values()}

    # The realized membership must refine... rather, equal the merged IR
    # partition: every expected group must appear as one realized net and no
    # realized net may join pins across expected groups.
    ok = True
    for net_name, members in realized.items():
        roots = {find(m) for m in members}
        if len(roots) > 1:
            logger.warning(
                "MCP netlist mismatch on %s: joins %s across different IR nets",
                net_name, sorted(members),
            )
            ok = False
    for members in groups:
        realized_nets = {
            exported_pin_nets.get(m) or f"__missing__{m[0]}_{m[1]}" for m in members
        }
        if len(realized_nets) > 1:
            logger.warning(
                "MCP netlist mismatch: %s split across realized nets %s",
                sorted(members), sorted(realized_nets),
            )
            ok = False
    return ok


# ---------------------------------------------------------------------------
# wire routing
#
# Signal nets get real wires: a vertical trunk in a routing gutter between
# component columns, one horizontal stub per member pin, junctions where
# stubs meet the trunk. Power nets keep their power symbols. Nets whose
# geometry would collide with foreign pins, labels, or other nets' wires
# (collinear overlap, T-junction) fall back to label connectivity.

_EPS = 0.01


def _seg_horizontal(seg) -> bool:
    return abs(seg[1] - seg[3]) < _EPS


def _point_on_segment(px: float, py: float, seg) -> bool:
    x1, y1, x2, y2 = seg
    if _seg_horizontal(seg):
        return (
            abs(py - y1) < _EPS
            and min(x1, x2) - _EPS <= px <= max(x1, x2) + _EPS
        )
    return (
        abs(px - x1) < _EPS
        and min(y1, y2) - _EPS <= py <= max(y1, y2) + _EPS
    )


def _segs_conflict(a, b) -> bool:
    """True if the two wire segments would form an unintended connection.

    Mid-wire crossings of perpendicular segments do not connect in KiCad;
    any shared point that is an endpoint of either segment does (T-junction
    or corner). Parallel segments connect when collinear ranges overlap.
    """
    def is_end(seg, px: float, py: float) -> bool:
        return (
            (abs(seg[0] - px) < _EPS and abs(seg[1] - py) < _EPS)
            or (abs(seg[2] - px) < _EPS and abs(seg[3] - py) < _EPS)
        )

    ha, hb = _seg_horizontal(a), _seg_horizontal(b)
    if ha != hb:
        if ha:
            h, v = a, b
        else:
            h, v = b, a
        cx, cy = v[0], h[1]
        if not _point_on_segment(cx, cy, h) or not _point_on_segment(cx, cy, v):
            return False
        return is_end(h, cx, cy) or is_end(v, cx, cy)
    if ha:
        if abs(a[1] - b[1]) >= _EPS:
            return False
        return not (max(a[0], a[2]) < min(b[0], b[2]) + _EPS or max(b[0], b[2]) < min(a[0], a[2]) + _EPS)
    if abs(a[0] - b[0]) >= _EPS:
        return False
    return not (max(a[1], a[3]) < min(b[1], b[3]) + _EPS or max(b[1], b[3]) < min(a[1], a[3]) + _EPS)


def _plan_wire_routes(
    ir_nets: List[Dict[str, Any]],
    placed_refs: Set[str],
    aliases: Dict[str, Dict[str, str]],
    pin_positions: Dict[Tuple[str, str], Tuple[float, float]],
    columns_x: List[float],
) -> Dict[str, Dict[str, Any]]:
    """Plan wire routes for signal nets; conflicts fall back to labels."""
    all_pin_points: Set[Tuple[float, float]] = set(pin_positions.values())

    # Per-symbol horizontal extent: a horizontal stub may never cross the
    # symbol that owns the pin (its other pins would be shorted). Pins on the
    # right half of a symbol may only reach slots right of the whole symbol;
    # left-half pins only slots left of it.
    ref_extent: Dict[str, Tuple[float, float]] = {}
    for (r, _p), (px, _py) in pin_positions.items():
        lo, hi = ref_extent.get(r, (px, px))
        ref_extent[r] = (min(lo, px), max(hi, px))

    net_points: Dict[str, List[Tuple[float, float]]] = {}
    point_owner: Dict[Tuple[float, float], str] = {}
    for net in ir_nets:
        if not isinstance(net, dict):
            continue
        name = str(net.get("name") or "")
        if not name or _is_gnd(name) or _rail_symbol(name):
            continue
        points: List[Tuple[float, float]] = []
        for conn in net.get("connections", []) or []:
            ref, _, pin = str(conn).rpartition(".")
            if ref and pin and ref in placed_refs:
                pin = aliases.get(ref, {}).get(pin, pin)
                pos = pin_positions.get((ref, pin))
                if pos is not None:
                    points.append(pos)
                    point_owner.setdefault(pos, ref)
        unique = sorted(set(points))
        if len(unique) >= 2:
            net_points[name] = unique

    def corridor_clear(p1: Tuple[float, float], p2: Tuple[float, float], own: Set[Tuple[float, float]]) -> bool:
        """Straight horizontal run p1->p2 passes no foreign pin."""
        seg = (p1[0], p1[1], p2[0], p2[1])
        for px, py in all_pin_points:
            if (px, py) in own:
                continue
            if _point_on_segment(px, py, seg):
                return False
        return True

    plans: Dict[str, Dict[str, Any]] = {}
    routed_pins: Set[Tuple[float, float]] = set()

    # Pass 1 — series wires: a two-pin net whose facing pins sit on the same
    # row with a clear corridor gets one straight wire (classic R->LED look).
    for name in sorted(net_points):
        pts = net_points[name]
        if len(pts) != 2:
            continue
        (ax, ay), (bx, by) = pts
        if abs(ay - by) > _EPS:
            continue
        a_ref, b_ref = point_owner[(ax, ay)], point_owner[(bx, by)]
        if a_ref == b_ref:
            continue
        if not corridor_clear((ax, ay), (bx, by), set(pts)):
            continue
        plans[name] = {
            "segments": [(ax, ay, bx, by)],
            "junctions": [],
            "points": set(pts),
        }
        routed_pins.update(pts)

    # Gutter trunk slots between (and beside) the component columns. Trunk
    # x positions must sit on KiCad's 1.27 mm connection grid: ERC flags
    # every off-grid wire endpoint (endpoint_off_grid), and pin coordinates
    # are already grid-clean because they come from the placed symbols.
    def _snap_grid(v: float) -> float:
        return round(round(v / 1.27) * 1.27, 2)

    slots: List[float] = []
    centers = sorted(columns_x) or [100.0]
    for off in (25.0, 35.0, 45.0, 55.0):
        slots.append(_snap_grid(centers[0] - off))
    for a, b in zip(centers, centers[1:]):
        middle = _snap_grid((a + b) / 2.0)
        for off in (0.0, 2.54, -2.54, 5.08, -5.08, 7.62, -7.62):
            slots.append(round(middle + off, 2))
    for off in (25.0, 35.0, 45.0, 55.0):
        slots.append(_snap_grid(centers[-1] + off))
    slots = sorted(set(slots))

    def side_ok(slot: float, px: float, ref: str) -> bool:
        lo, hi = ref_extent.get(ref, (px - 1.0, px + 1.0))
        if hi - lo < 2.0:
            # 竖直窄条符号（R/C/LED 上下引脚同 x）：水平走线不会穿过
            # 自身其他引脚，两侧槽位都可用。
            return True
        mid = (lo + hi) / 2.0
        if px >= mid:   # right-edge pin: corridor must clear the whole symbol
            return slot > hi + _EPS
        return slot < lo - _EPS

    used_slots: Set[float] = set()
    for name in sorted(net_points, key=lambda n: -len(net_points[n])):
        if name in plans:
            continue
        points = net_points[name]
        best_slot, best_cost = None, None
        for slot in slots:
            if slot in used_slots:
                continue
            if not all(side_ok(slot, px, point_owner[(px, py)]) for px, py in points):
                continue
            cost = sum(abs(px - slot) for px, _py in points)
            if best_cost is None or cost < best_cost:
                best_slot, best_cost = slot, cost
        if best_slot is None:
            continue
        used_slots.add(best_slot)

        segments = []
        ys = {py for _px, py in points}
        for px, py in points:
            if abs(px - best_slot) > _EPS:
                segments.append((px, py, best_slot, py))
        trunk = (best_slot, min(ys), best_slot, max(ys))
        if abs(trunk[1] - trunk[3]) > _EPS:
            segments.append(trunk)
        junctions = [(best_slot, py) for py in ys]
        plans[name] = {"segments": segments, "junctions": junctions, "points": set(points)}

    # Conflict resolution: drop nets whose geometry would touch foreign pins
    # or other nets' wires, then drop anything that conflicts with what
    # remains, until stable.
    while True:
        conflicted = set()
        names = list(plans)
        for name in names:
            own = plans[name]["points"]
            for seg in plans[name]["segments"]:
                for px, py in all_pin_points:
                    if (px, py) in own:
                        continue
                    if _point_on_segment(px, py, seg):
                        conflicted.add(name)
                        break
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if a in conflicted or b in conflicted:
                    continue
                for seg_a in plans[a]["segments"]:
                    for seg_b in plans[b]["segments"]:
                        if _segs_conflict(seg_a, seg_b):
                            conflicted.add(a)
                            conflicted.add(b)
                            break
                    if a in conflicted or b in conflicted:
                        break
        if not conflicted:
            break
        for name in conflicted:
            logger.info("MCP wiring: net %s falls back to labels (geometry conflict)", name)
            del plans[name]

    return plans

def _crop_svg_to_content(svg: str) -> str:
    """Crop KiCad's page-sized SVG viewBox down to visible schematic content."""
    if not svg:
        return svg

    number = r"[-+]?(?:\d+\.\d+|\d+|\.\d+)(?:[eE][-+]?\d+)?"
    points: List[Tuple[float, float]] = []

    def add_point(x: Any, y: Any) -> None:
        try:
            points.append((float(x), float(y)))
        except (TypeError, ValueError):
            pass

    def attr(tag: str, name: str) -> Optional[str]:
        match = re.search(rf'\b{name}="([^"]+)"', tag)
        return match.group(1) if match else None

    def hidden(tag: str) -> bool:
        return (
            'opacity="0"' in tag
            or 'stroke-opacity="0"' in tag
            or 'display="none"' in tag
            or 'visibility="hidden"' in tag
        )

    for tag in re.findall(r"<path\b[^>]*>", svg, flags=re.IGNORECASE | re.DOTALL):
        if hidden(tag):
            continue
        values = re.findall(number, attr(tag, "d") or "")
        for i in range(0, len(values) - 1, 2):
            add_point(values[i], values[i + 1])

    for tag in re.findall(r"<(?:polyline|polygon)\b[^>]*>", svg, flags=re.IGNORECASE | re.DOTALL):
        if hidden(tag):
            continue
        values = re.findall(number, attr(tag, "points") or "")
        for i in range(0, len(values) - 1, 2):
            add_point(values[i], values[i + 1])

    for tag in re.findall(r"<line\b[^>]*>", svg, flags=re.IGNORECASE | re.DOTALL):
        if hidden(tag):
            continue
        add_point(attr(tag, "x1"), attr(tag, "y1"))
        add_point(attr(tag, "x2"), attr(tag, "y2"))

    for tag in re.findall(r"<rect\b[^>]*>", svg, flags=re.IGNORECASE | re.DOTALL):
        if hidden(tag):
            continue
        try:
            x, y = float(attr(tag, "x") or 0), float(attr(tag, "y") or 0)
            w, h = float(attr(tag, "width") or 0), float(attr(tag, "height") or 0)
        except ValueError:
            continue
        if x == 0 and y == 0 and w > 200 and h > 150:
            continue
        add_point(x, y)
        add_point(x + w, y + h)

    for tag in re.findall(r"<circle\b[^>]*>", svg, flags=re.IGNORECASE | re.DOTALL):
        if hidden(tag):
            continue
        try:
            cx, cy = float(attr(tag, "cx") or 0), float(attr(tag, "cy") or 0)
            r = float(attr(tag, "r") or 0)
        except ValueError:
            continue
        add_point(cx - r, cy - r)
        add_point(cx + r, cy + r)

    for tag in re.findall(r"<text\b[^>]*>", svg, flags=re.IGNORECASE | re.DOTALL):
        if hidden(tag):
            continue
        add_point(attr(tag, "x"), attr(tag, "y"))

    if not points:
        return svg

    min_x = min(x for x, _ in points)
    min_y = min(y for _, y in points)
    max_x = max(x for x, _ in points)
    max_y = max(y for _, y in points)
    if max_x <= min_x or max_y <= min_y:
        return svg

    pad = 4.0
    min_x, min_y, max_x, max_y = min_x - pad, min_y - pad, max_x + pad, max_y + pad
    width, height = max_x - min_x, max_y - min_y
    svg = re.sub(r'\swidth="[^"]+"', f' width="{width:.4f}mm"', svg, count=1)
    svg = re.sub(r'\sheight="[^"]+"', f' height="{height:.4f}mm"', svg, count=1)
    svg = re.sub(
        r'\sviewBox="[^"]+"',
        f' viewBox="{min_x:.4f} {min_y:.4f} {width:.4f} {height:.4f}"',
        svg,
        count=1,
    )
    return svg


def _summarize_erc(erc_text: str) -> Dict[str, Any]:
    if not erc_text:
        return {"status": "unknown", "errors": 0, "warnings": 0, "violations": []}
    try:
        data = json.loads(erc_text)
    except json.JSONDecodeError:
        return {"status": "unknown", "errors": 0, "warnings": 0, "violations": []}

    violations: List[Dict[str, Any]] = []
    errors = 0
    warnings = 0
    for sheet in data.get("sheets", []):
        for violation in sheet.get("violations", []):
            if violation.get("type") == "lib_symbol_mismatch":
                # the vendored MCP wheel embeds patched symbols (unit-0 pin
                # folding); the intentional divergence from the stock library
                # is not a schematic defect
                continue
            severity = violation.get("severity", "warning")
            if severity == "error":
                errors += 1
            else:
                warnings += 1
            violations.append(
                {
                    "type": violation.get("type"),
                    "severity": severity,
                    "description": violation.get("description"),
                }
            )
    status = "passed" if errors == 0 else "failed"
    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "violations": violations[:20],
    }


# ---------------------------------------------------------------------------
# main entry point

async def generate_kicad_artifacts_via_mcp(ir: Dict[str, Any]) -> Dict[str, Any]:
    """Generate KiCad schematic artifacts from CircuitIR through the KiCad MCP server."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    if not ir.get("supported", False):
        raise McpSchematicError("Unsupported CircuitIR cannot be exported to KiCad")
    if not mcp_backend_available():
        raise McpSchematicError("mcp-kicad-sch-api is not installed in this venv")

    kicad_root, kicad_cli = _find_kicad()

    work_root = Path(tempfile.gettempdir()) / "cirgpt_kicad"
    work_root.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="mcp_", dir=str(work_root)))

    circuit_type = str(ir.get("circuit_type") or "circuit")
    safe_name = "".join(ch if ch.isalnum() else "_" for ch in circuit_type) or "circuit"
    sch_path = work_dir / f"{safe_name}_{os.getpid()}.kicad_sch"
    svg_dir = work_dir / "svg"
    svg_dir.mkdir(exist_ok=True)
    erc_path = work_dir / f"{safe_name}.erc.json"
    net_path = work_dir / f"{safe_name}.net"

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_kicad_sch_api"],
        env=_server_env(kicad_root, kicad_cli),
    )

    # supplies are placed too (as Simulation_SPICE source symbols): a
    # schematic whose 9V battery exists only as VCC labels reads as
    # "missing the power source"
    base_warnings = list(ir.get("warnings") or [])
    ir, real_part_drops = _expand_real_part_connections(ir)
    # deterministic IR fixes (net merges) add their own disclosures to the
    # expanded IR's warnings; surface them to the caller
    ir_adjustments = [str(w) for w in (ir.get("warnings") or [])[len(base_warnings):]]
    components = [
        comp for comp in ir.get("components", []) if isinstance(comp, dict)
    ]
    placed: List[Tuple[Dict[str, Any], str, str]] = []  # (comp, lib, sym)
    skipped: List[str] = list(real_part_drops)
    for comp in components:
        lib_sym = _symbol_for(comp)
        if lib_sym is None:
            skipped.append(str(comp.get("ref") or comp.get("type")))
            continue
        placed.append((comp, lib_sym[0], lib_sym[1]))
    if not placed:
        raise McpSchematicError("No IR components mapped onto KiCad library symbols")

    placed_refs = {str(comp.get("ref")) for comp, _lib, _sym in placed if comp.get("ref")}

    # Multi-unit symbols (dual opamps, MCUs with per-bank units...): the IR
    # references pins by number, so look up which unit owns each pin and
    # place every unit that owns at least one IR-referenced pin, stacked
    # below unit 1 under the same reference.
    symbol_dir = kicad_root / "share" / "kicad" / "symbols"
    unit_pins = _symbol_units_from_lib(
        symbol_dir, [f"{lib}:{sym}" for _comp, lib, sym in placed]
    )
    ref_pins: Dict[str, Set[str]] = {}
    for net in ir.get("nets") or []:
        if not isinstance(net, dict):
            continue
        for conn in net.get("connections") or []:
            r, _, p = str(conn).rpartition(".")
            if r and p:
                ref_pins.setdefault(r, set()).add(p)

    def needed_units(ref: str, lib_id: str) -> List[int]:
        # Every unit of a multi-unit symbol goes on the sheet - the unused
        # halves (LM358 unit B, an MCU's spare banks) sit next to the used
        # ones with no-connect flags instead of raising ERC missing_unit.
        units = unit_pins.get(lib_id) or {}
        return sorted(units) or [1]

    UNIT_STACK_DY = 25.4
    stack_extra: Dict[str, float] = {}
    for comp, lib, sym in placed:
        ref = str(comp.get("ref") or "")
        stack_extra[ref] = (len(needed_units(ref, f"{lib}:{sym}")) - 1) * UNIT_STACK_DY

    # Layout: one column per subsystem (IR order), components stacked. Wide
    # ICs (28-pin DIPs etc.) need generous pitch; retries with larger spacing
    # if any two placed pins land on the same coordinate. Subsystem groups are
    # packed into a balanced grid (target ~sqrt(n) columns) so an IR whose
    # groups are tiny or missing still gets a sane sheet instead of one
    # giant column.
    groups: List[Tuple[str, List[Dict[str, Any]]]] = []
    by_sub: Dict[str, List[Dict[str, Any]]] = {}
    for comp, _lib, _sym in placed:
        sub = _subsystem_of(comp)
        if sub not in by_sub:
            by_sub[sub] = []
            groups.append((sub, by_sub[sub]))
        by_sub[sub].append(comp)

    n = len(placed)
    target_cols = 2
    while target_cols * target_cols < n:
        target_cols += 1
    max_rows = max((n + target_cols - 1) // target_cols, max(len(g) for _s, g in groups))

    columns: List[List[Dict[str, Any]]] = [[]]
    for _sub, comps in groups:
        if columns[-1] and len(columns[-1]) + len(comps) > max_rows:
            columns.append([])
        columns[-1].extend(comps)

    def layout_positions(col_dx: float, row_dy: float) -> Dict[str, Tuple[float, float]]:
        positions: Dict[str, Tuple[float, float]] = {}
        for col_idx, column in enumerate(columns):
            y = 60.0
            for comp in column:
                ref = str(comp.get("ref"))
                positions[ref] = (50.0 + col_idx * col_dx, y)
                y += row_dy + stack_extra.get(ref, 0.0)
        return positions

    pwr_i = 0
    pin_positions: Dict[Tuple[str, str], Tuple[float, float]] = {}
    columns_x: List[float] = []

    async with asyncio.timeout(240):
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                mcp = _McpSession(session)

                placed_ok = False
                for col_dx, row_dy in ((55.0, 42.0), (75.0, 60.0), (100.0, 80.0)):
                    columns_x = [50.0 + i * col_dx for i in range(len(columns))]
                    await mcp.call("create_schematic", {"name": safe_name})
                    positions = layout_positions(col_dx, row_dy)
                    for idx, (comp, lib, sym) in enumerate(placed):
                        ref = str(comp.get("ref") or f"U{idx + 1}")
                        x, y = positions.get(ref, (50.0, 60.0))
                        lib_id = f"{lib}:{sym}"
                        for u_i, unit_no in enumerate(needed_units(ref, lib_id)):
                            args = {
                                "lib_id": lib_id,
                                "reference": ref,
                                "value": _fmt_value(comp),
                                "position": [
                                    round(x, 3),
                                    round(y + u_i * UNIT_STACK_DY, 3),
                                ],
                                "footprint": _footprint_for(lib, sym, comp),
                            }
                            if unit_no != 1:
                                args["unit"] = unit_no
                            await mcp.call("add_component", args)

                    # Save so the exact (grid-snapped) symbol geometry is on
                    # disk, then compute pin positions from the file itself:
                    # the server's pin-position tool applies a buggy transform.
                    await mcp.call("save_schematic", {"file_path": str(sch_path)})
                    pin_positions = _pin_positions_from_sch(
                        sch_path.read_text(encoding="utf-8", errors="replace")
                    )

                    by_point: Dict[Tuple[float, float], Tuple[str, str]] = {}
                    collision = False
                    for node, pos in pin_positions.items():
                        other = by_point.get(pos)
                        if other is not None and other != node:
                            # Same-symbol coincident pins (stacked GND pins on
                            # some MCUs) are the symbol's own design, not a
                            # layout failure.
                            if other[0] != node[0]:
                                logger.info(
                                    "MCP layout collision at %s: %s vs %s; widening grid",
                                    pos, other, node,
                                )
                                collision = True
                                break
                        else:
                            by_point[pos] = node
                    if not collision:
                        placed_ok = True
                        break

                if not placed_ok:
                    raise McpSchematicError(
                        "Could not place components without pin collisions"
                    )

                aliases = _pin_aliases(placed, ir.get("nets") or [], pin_positions)
                # pin electrical types (power_in / output / ...) decide the
                # ERC clean-up passes below; instances do not change during
                # wiring so the placement-time text stays valid
                _placed_text = sch_path.read_text(encoding="utf-8", errors="replace")
                pin_types = _pin_types_on_sheet(_placed_text)
                pin_anchors = _pin_anchors(_placed_text)
                wired_nets, _gate_dropped = _remap_power_pins(
                    ir.get("nets") or [], pin_types, pin_positions
                )
                wire_plans = _plan_wire_routes(
                    wired_nets, placed_refs, aliases, pin_positions, columns_x
                )
                # pins the net loop below wired (directly or via stubs); the
                # power-attach pass takes the power_in pins not in here
                claimed_pins: Set[Tuple[str, str]] = set()
                # non-rail nets feeding power inputs without any driver:
                # each gets a PWR_FLAG once all wires are drawn
                power_needy_nets: List[Tuple[str, Tuple[str, str, Tuple[float, float]]]] = []
                flagged_rails: Set[str] = set()
                comp_pin_points: Set[Tuple[float, float]] = {
                    pos for (r, _p), pos in pin_positions.items() if not r.startswith("#")
                }
                drawn_segments: List[Tuple[float, float, float, float, str]] = []

                def on_any_wire(px: float, py: float, net: str) -> bool:
                    """A pin or power symbol landing anywhere on a wire - even
                    mid-segment - joins that net in KiCad. Wires of the SAME
                    net are fine (that is what connects the flag)."""
                    for x1, y1, x2, y2, seg_net in drawn_segments:
                        if seg_net == net:
                            continue
                        if abs(x1 - x2) < _EPS and abs(x2 - px) < _EPS:
                            if min(y1, y2) - _EPS <= py <= max(y1, y2) + _EPS:
                                return True
                        elif abs(y1 - y2) < _EPS and abs(y1 - py) < _EPS:
                            if min(x1, x2) - _EPS <= px <= max(x1, x2) + _EPS:
                                return True
                    return False
                label_anchor_points: Set[Tuple[float, float]] = set()
                power_stub_points: Dict[Tuple[float, float], str] = {}
                pending_flags: List[Tuple[str, float, float, Tuple[float, float]]] = []
                # Layout midline: vertical stubs (pins above/below a symbol)
                # carry their label sideways; pointing the text at the
                # nearer outside margin keeps it off the IC body, the trunk
                # channels, and neighboring symbols in the middle.
                xs = [p[0] for p in positions.values()] or [0.0]
                mid_x = (min(xs) + max(xs)) / 2.0

                def pin_pos(ref: str, pin: str) -> Optional[Tuple[float, float]]:
                    pos = pin_positions.get((ref, pin))
                    if pos is None:
                        pos = pin_positions.get((ref, aliases.get(ref, {}).get(pin, pin)))
                    return pos

                # Connectivity: signal nets routed above get real wires;
                # power nets get power symbols on each member pin (they merge
                # globally by value); the rest get local labels. Pins that do
                # not exist on the mapped symbol are dropped with a warning.
                dropped_pins: Set[Tuple[str, str]] = set(_gate_dropped)
                for net in wired_nets:
                    if not isinstance(net, dict):
                        continue
                    net_name = str(net.get("name") or "")
                    members = []
                    seen_points: Set[Tuple[float, float]] = set()
                    for conn in net.get("connections", []) or []:
                        ref, _, pin = str(conn).rpartition(".")
                        if ref and pin and ref in placed_refs:
                            pos = pin_pos(ref, pin)
                            if pos is None:
                                dropped_pins.add((ref, pin))
                                logger.warning(
                                    "MCP builder: pin %s.%s not found on symbol; skipped", ref, pin
                                )
                            elif pos not in seen_points:
                                # Coincident pins (same point) need one label
                                # only; every pin at that point joins the net.
                                seen_points.add(pos)
                                members.append((ref, pin, pos))
                                claimed_pins.add((ref, pin))
                    if not members:
                        continue
                    if len(members) == 1 and pin_types.get(
                        (members[0][0], members[0][1]), ("", "")
                    )[1] not in ("power_in", "power_out"):
                        # A one-pin net connects nothing; leave the pin to
                        # the no-connect pass so ERC reads it as intentional
                        # instead of an isolated label.
                        logger.info(
                            "MCP wiring: net %s has a single non-supply pin; marking no-connect",
                            net_name,
                        )
                        continue

                    # Non-rail net that carries power inputs but no power
                    # output (a connector-fed rail with a custom name like
                    # VBUS_F): ERC flags every such pin as undriven. The
                    # rail branch flags named rails; remember these for the
                    # same PWR_FLAG treatment after all wires are drawn.
                    if _is_gnd(net_name) or _rail_symbol(net_name):
                        pass  # named rails flag themselves below
                    elif (
                        any(pin_types.get((r, p), ("", ""))[1] == "power_in" for r, p, _pos in members)
                        and not any(pin_types.get((r, p), ("", ""))[1] == "power_out" for r, p, _pos in members)
                    ):
                        power_needy_nets.append((net_name, members[0]))

                    route = wire_plans.get(net_name)
                    if route is not None:
                        # Real wires: stubs from member pins to a per-net trunk.
                        for seg in route["segments"]:
                            await mcp.call(
                                "add_wire",
                                {
                                    "start_pos": [seg[0], seg[1]],
                                    "end_pos": [seg[2], seg[3]],
                                },
                            )
                            drawn_segments.append((seg[0], seg[1], seg[2], seg[3], net_name))
                        for jx, jy in route["junctions"]:
                            await mcp.call("add_junction", {"position": [jx, jy]})
                        continue

                    rail = "GND" if _is_gnd(net_name) else _rail_symbol(net_name)
                    if rail is None and members and all(
                        pin_types.get((r, p), ("", ""))[1] == "power_in"
                        for r, p, _pos in members
                    ):
                        # a lone power-input pin names its own net (old IRs
                        # emit pin-number nets); give it the rail its own
                        # pin name asks for, flagged like any other rail
                        pname = pin_types.get((members[0][0], members[0][1]), ("VCC", ""))[0]
                        u = str(pname).upper()
                        rail = (
                            "GND"
                            if ("GND" in u or u in {"VSS", "V-", "VEE"})
                            else (_rail_symbol(pname) or "VCC")
                        )
                        # the renamed rail is power plumbing, not IR
                        # connectivity the gate must verify
                        dropped_pins.update((r, p) for r, p, _pos in members)

                    def stub_end(
                        ref: str, pin: str, pos: Tuple[float, float]
                    ) -> Tuple[float, float]:
                        """Pin position shifted outward from its symbol.

                        The outward direction is judged against the instance
                        anchor of the unit that OWNS the pin - a multi-unit
                        symbol stacks its units, so unit 1's anchor would
                        turn side pins of lower units into bottom pins and
                        send stubs straight through neighbouring pins.

                        Power symbols and their value text sitting one grid
                        off the pin still render over the pin-number column
                        and the neighboring pin names (KiCad 10 always draws
                        label/symbol text left-to-right from its anchor), so
                        rail stubs clear the whole pin-name strip.
                        """
                        cx, cy = pin_anchors.get((ref, pin), positions.get(ref, pos))
                        dx, dy = pos[0] - cx, pos[1] - cy
                        if abs(dx) >= abs(dy):
                            return (pos[0] + (7.62 if dx >= 0 else -7.62), pos[1])
                        return (pos[0], pos[1] + (7.62 if dy >= 0 else -7.62))

                    if rail:
                        for ref, pin, pos in members:
                            ex, ey = stub_end(ref, pin, pos)
                            await mcp.call(
                                "add_wire",
                                {"start_pos": [pos[0], pos[1]], "end_pos": [ex, ey]},
                            )
                            drawn_segments.append((pos[0], pos[1], ex, ey, rail))
                            power_stub_points[(ex, ey)] = rail
                            pwr_i += 1
                            await mcp.call(
                                "add_component",
                                {
                                    "lib_id": f"power:{rail}",
                                    "reference": f"#PWR{pwr_i:02d}",
                                    "value": rail,
                                    "position": [ex, ey],
                                    "footprint": "",
                                },
                            )
                        # One PWR_FLAG per power net keeps ERC quiet about
                        # undriven power inputs - unless a member already
                        # drives the rail (a regulator's power-output pin,
                        # which would clash with the flag's power output).
                        net_has_driver = any(
                            pin_types.get((r, p), ("", ""))[1] == "power_out"
                            for r, p, _pos in members
                        )
                        if not net_has_driver:
                            # flags are placed after ALL nets are wired, when
                            # every label anchor and wire endpoint is known -
                            # an in-loop flag can otherwise land on a label
                            # drawn later and join the wrong net
                            ref, _pin, pos = members[0]
                            ex, ey = stub_end(ref, _pin, pos)
                            pending_flags.append((rail, ex, ey, pos))
                    else:
                        label = _safe_label(net_name)
                        # KiCad draws label text left-to-right starting at
                        # the anchor, whatever the label's rotation. Size
                        # the stub so the text stops short of the pin it
                        # labels instead of running over the pin number,
                        # pin name, or symbol body.
                        stub = _label_stub_len(label)
                        for _ref, _pin, pos in members:
                            cx, cy = pin_anchors.get(
                                (_ref, _pin), positions.get(_ref, pos)
                            )
                            dx, dy = pos[0] - cx, pos[1] - cy
                            if abs(dx) >= abs(dy):
                                # Side pin: straight stub away from the body.
                                step = stub if dx >= 0 else -stub
                                seg_pts = [(pos[0], pos[1]), (pos[0] + step, pos[1])]
                            else:
                                # Top/bottom pin: dogleg one grid off the
                                # pin, then toward the outside margin, so
                                # the text reads across clear space.
                                step = 2.54 if dy >= 0 else -2.54
                                out = -stub if pos[0] < mid_x else stub
                                seg_pts = [
                                    (pos[0], pos[1]),
                                    (pos[0], pos[1] + step),
                                    (pos[0] + out, pos[1] + step),
                                ]
                            end = seg_pts[-1]
                            for a, b in zip(seg_pts, seg_pts[1:]):
                                await mcp.call(
                                    "add_wire",
                                    {"start_pos": [a[0], a[1]], "end_pos": [b[0], b[1]]},
                                )
                                drawn_segments.append((a[0], a[1], b[0], b[1], net_name))
                            await mcp.call(
                                "add_label",
                                {"text": label, "position": [end[0], end[1]]},
                            )
                            label_anchor_points.add(end)

                # PWR_FLAG for non-rail nets that feed power inputs (e.g. a
                # connector-fed VBUS_F): the flag's power output satisfies
                # ERC's "input power pin not driven". Anchored at the member
                # pin; the deferred-flag stepper below walks it to a free
                # spot while laying a connecting wire.
                for flag_net, (fref, fpin, fpos) in power_needy_nets:
                    if flag_net in flagged_rails:
                        continue
                    pending_flags.append((flag_net, fpos[0], fpos[1], fpos))

                # Power-input pins the IR never mapped (LM358 V+/V-, an
                # MCU's AVCC): tie them to their rail so ERC sees a driven
                # supply instead of dangling power inputs. Positive pins go
                # to the design's own main rail when one exists.
                main_pos_rail = "VCC"
                for net in wired_nets:
                    if isinstance(net, dict) and not _is_gnd(net.get("name")):
                        sym = _rail_symbol(net.get("name"))
                        if sym:
                            main_pos_rail = sym
                            break
                for (ref, pin), (pname, etype) in sorted(pin_types.items()):
                    if etype != "power_in" or ref.startswith("#"):
                        continue
                    if (ref, pin) in claimed_pins or (ref, pin) not in pin_positions:
                        continue
                    pos = pin_positions[(ref, pin)]
                    upper = str(pname).upper()
                    if _is_gnd(pname) or "GND" in upper or upper in {"VSS", "V-", "VEE", "VGND"}:
                        rail = "GND"
                    else:
                        rail = main_pos_rail
                    ex, ey = stub_end(ref, pin, pos)
                    await mcp.call(
                        "add_wire",
                        {"start_pos": [pos[0], pos[1]], "end_pos": [ex, ey]},
                    )
                    drawn_segments.append((pos[0], pos[1], ex, ey, rail))
                    power_stub_points[(ex, ey)] = rail
                    pwr_i += 1
                    await mcp.call(
                        "add_component",
                        {
                            "lib_id": f"power:{rail}",
                            "reference": f"#PWR{pwr_i:02d}",
                            "value": rail,
                            "position": [ex, ey],
                            "footprint": "",
                        },
                    )
                    if rail not in flagged_rails:
                        pending_flags.append((rail, ex, ey, pos))

                # Place deferred PWR_FLAGs with full knowledge of every
                # label anchor, wire endpoint and power stub. The flag sits
                # at a rail's power-symbol stub end, stepping along the stub
                # axis only - never diagonally, and never onto a foreign
                # anchor (that would steal the flag into another net).
                for rail, ex, ey, pos in pending_flags:
                    if rail in flagged_rails:
                        continue
                    horizontal = abs(ey - pos[1]) < _EPS
                    step = 2.54 * (
                        1 if (ex >= pos[0] if horizontal else ey >= pos[1]) else -1
                    )
                    fx, fy = ex, ey

                    def spot_blocked(px: float, py: float) -> bool:
                        stub_rail = power_stub_points.get((px, py))
                        return (
                            (px, py) in comp_pin_points
                            or (px, py) in label_anchor_points
                            or (stub_rail is not None and stub_rail != rail)
                            or on_any_wire(px, py, rail)
                        )

                    for _n in range(20):
                        if not spot_blocked(fx, fy):
                            break
                        fx, fy = (fx + step, fy) if horizontal else (fx, fy + step)
                        await mcp.call(
                            "add_wire",
                            {"start_pos": [ex, ey], "end_pos": [fx, fy]},
                        )
                        drawn_segments.append((ex, ey, fx, fy, rail))
                        ex, ey = fx, fy
                    if not spot_blocked(fx, fy):
                        pwr_i += 1
                        await mcp.call(
                            "add_component",
                            {
                                "lib_id": "power:PWR_FLAG",
                                "reference": f"#FLG{pwr_i:02d}",
                                "value": rail,
                                "position": [fx, fy],
                                "footprint": "",
                            },
                        )
                        flagged_rails.add(rail)
                    else:
                        logger.info(
                            "MCP wiring: no free spot for PWR_FLAG on %s; skipped", rail
                        )

                await mcp.call("save_schematic", {"file_path": str(sch_path)})

    if not sch_path.exists():
        raise McpSchematicError("MCP server did not save a schematic file")

    # No-connect flags for every pin still without a wire/label/power stub
    # (spare MCU GPIOs, the unused half of a dual opamp, spare connector
    # pins): ERC reads them as intentionally open, not dangling.
    final_text = sch_path.read_text(encoding="utf-8", errors="replace")
    pin_positions_final = _pin_positions_from_sch(final_text)
    nc_points = [
        (p["x"], p["y"])
        for p in _unconnected_pins(final_text, pin_positions_final, pin_types)
    ]
    if nc_points:
        sch_path.write_text(
            _inject_no_connects(final_text, nc_points), encoding="utf-8"
        )
        pin_positions = pin_positions_final

    # Gate: the exported netlist must preserve the IR's connectivity before
    # the artifacts are accepted.
    net_run = _run_cli(
        [str(kicad_cli), "sch", "export", "netlist", "--format", "kicadsexpr",
         "-o", str(net_path), str(sch_path)],
    )
    if net_run.returncode != 0 or not net_path.exists():
        raise McpSchematicError(f"kicad-cli netlist export failed: {net_run.stderr[:300]}")
    exported_nets = _parse_netlist_nets(net_path.read_text(encoding="utf-8", errors="replace"))
    if not _connectivity_matches(
        ir.get("nets") or [], placed_refs, exported_nets, pin_positions, aliases, dropped_pins
    ):
        raise McpSchematicError(
            "MCP schematic connectivity does not match the CircuitIR nets; rejected"
        )

    svg_run = _run_cli(
        [str(kicad_cli), "sch", "export", "svg", "--exclude-drawing-sheet",
         "--no-background-color", "-o", str(svg_dir), str(sch_path)],
    )
    svg_files = sorted(svg_dir.glob("*.svg"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not svg_files:
        raise McpSchematicError(f"kicad-cli SVG export produced nothing: {svg_run.stderr[:300]}")
    svg = _crop_svg_to_content(
        svg_files[0].read_text(encoding="utf-8", errors="replace")
    )
    if not svg:
        raise McpSchematicError("SVG export is empty")

    # ERC is advisory for the artifact itself; a tool timeout must not
    # discard the finished schematic — but it is reported as skipped, never
    # presented as a pass.
    erc_run = _run_cli(
        [str(kicad_cli), "sch", "erc", "--format", "json", "-o", str(erc_path), str(sch_path)],
    )
    erc_json = erc_path.read_text(encoding="utf-8", errors="replace") if erc_path.exists() else ""
    erc_summary = _summarize_erc(erc_json)
    if erc_run.returncode != 0 or not erc_json:
        erc_summary = {
            "status": "skipped_tool_failure",
            "errors": None,
            "warnings": None,
            "note": f"kicad-cli ERC unavailable (rc={erc_run.returncode}); NOT a pass — rerun ERC before fabrication.",
        }

    result = {
        "success": True,
        "svg": svg,
        "kicad_schematic": sch_path.read_text(encoding="utf-8", errors="replace"),
        "skidl_netlist": net_path.read_text(encoding="utf-8", errors="replace"),
        "erc_json": erc_json,
        "erc_summary": erc_summary,
        "paths": {
            "schematic": str(sch_path),
            "netlist": str(net_path),
            "svg": str(svg_files[0]),
            "erc": str(erc_path) if erc_path.exists() else None,
        },
        "commands": {
            "svg_returncode": svg_run.returncode,
            "svg_stderr": svg_run.stderr,
            "erc_returncode": erc_run.returncode,
            "erc_stderr": erc_run.stderr,
            "netlist_returncode": net_run.returncode,
        },
        "generator": "mcp:mcp-kicad-sch-api",
        "layout": "mcp-trunk-wired",
        "toolchain": {
            "mcp_server": "mcp-kicad-sch-api",
            "mcp_tool_calls": len(placed) + pwr_i,
            "kicad_cli": str(kicad_cli),
        },
        "working_directory": str(work_dir),
        "skipped_components": skipped,
        "ir_adjustments": ir_adjustments,
    }
    return result
