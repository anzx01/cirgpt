"""Power-on testing: simulate a CircuitIR's DC behaviour across input scenarios.

Bridges the gap between the schematic's connectivity netlist (which carries no
SPICE models) and a real "switch it on and see what happens" answer:

1. IR components are mapped onto a small engineering model library - open
   collector comparator, behavioural opamp, logic-level MOS/BJT switches,
   diode/LED/zener models, resistive actuator coils (motor/relay/buzzer).
2. A sensor-ish connector (soil moisture, LDR, thermistor ...) becomes a
   swept resistor so each scenario is one input condition (wet/dry soil,
   bright/dark, ...).
3. Each scenario is a ngspice ``.op`` run (batch, wrdata output); node
   voltages and actuator currents come back as structured JSON for the UI.

ngspice is located project-relative first (Spice64/bin, put on PATH by
START.bat), then via PATH.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

_REPO_SPICE64 = Path(__file__).resolve().parents[1] / "Spice64" / "bin"
_NGSPICE_CANDIDATES = ["ngspice_con", "ngspice"]


def find_ngspice() -> Optional[str]:
    env = os.environ.get("NGSPICE_BIN")
    if env and Path(env).is_file():
        return env
    for name in ("ngspice_con.exe", "ngspice.exe"):
        candidate = _REPO_SPICE64 / name
        if candidate.is_file():
            return str(candidate)
    for name in _NGSPICE_CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    return None


_GND_NAMES = {"0", "gnd", "vss", "-vcc", "-vs"}
_RAIL_RE = re.compile(r"^(\+?\d+(\.\d+)?v|vcc|vdd|v\+|vbatt|vbat|vin.*)$", re.I)


def _is_gnd(name: Any) -> bool:
    return str(name).strip().lower() in _GND_NAMES


def _is_rail(name: Any) -> bool:
    n = str(name).strip().lower()
    return bool(_RAIL_RE.match(n)) and not _is_gnd(n)


def _safe_node(name: Any) -> str:
    n = str(name).strip()
    if _is_gnd(n):
        return "0"
    return re.sub(r"[^A-Za-z0-9_]", "_", n) or "N?"


_MODELS = """
* ---- engineering model library (power-on test) ----
.model PW_NNMOS NMOS(VTO=2.0 KP=8.0 L=100u W=200m RD=0.15 RS=0.05)
.model PW_NPMOS PMOS(VTO=-2.0 KP=8.0 L=100u W=200m RD=0.15 RS=0.05)
.model PW_NPN  NPN(BF=150)
.model PW_PNP  PNP(BF=150)
.model PW_D    D(IS=1e-14 N=1.05 RS=0.01 BV=100)
.model PW_SCH  D(IS=200u  N=1.6  RS=0.04 BV=40)
.model PW_LED  D(IS=1e-12 N=3.4  RS=5)
.subckt PW_LM393 INP INN OUT VCC VGND
* open-collector comparator: pulls OUT low (2R) when IN- > IN+
BDRV NCTL VGND V = (V(INN,INP) > 1m) ? 1 : 0
S1   OUT VGND NCTL VGND PW_SWOC
.model PW_SWOC SW(VT=0.5 VH=0.05 RON=2 ROFF=100MEG)
.ends
.subckt PW_OPAMP INP INN OUT VCC VGND
RIN INP INN 1MEG
BOUT OUT VGND V = limit(200k*V(INP,INN), 0.2, V(VCC,VGND)-0.2)
.ends
.subckt PW_555 TRIG THR DIS OUT RST CTRL VCC VGND
* astable behavioural NE555. Latch state lives on CNQ: set/reset conditions
* each drive a voltage source that steers current through a diode into the
* state cap; while neither condition holds both diodes are reverse-biased
* and the charge (logic level) is held. A self-referenced B voltage source
* instead would make the matrix singular, and a B current source with a DC
* bleed resistor poisons the initial op point with I*R = ~100 kV.
BSET  NS VGND V = (V(TRIG,VGND) < V(VCC,VGND)/3) ? V(VCC,VGND) : 0
BRST  NR VGND V = (V(THR,VGND) > 2*V(VCC,VGND)/3) ? 0 : V(VCC,VGND)
RS1   NS NQS 1k
RS2   NQR NR 1k
DSET  NQS NQ PW_555D
DRST  NQ NQR PW_555D
CNQ   NQ VGND 1u
RNQ   NQ VGND 10MEG
BOUT  OUT VGND V = (V(NQ,VGND) > 2) ? V(VCC,VGND) : 0
BNDIS NDH VGND V = (V(NQ,VGND) > 2) ? 0 : 1
S1    DIS VGND NDH VGND PW_555SW
.model PW_555SW SW(VT=0.5 VH=0.05 RON=10 ROFF=100MEG)
.model PW_555D D(IS=1e-12 N=0.5 RS=1)
RCTL  CTRL VGND 10K
.ends
"""

_TIMER_TYPES = {"timer_ic", "ne555", "555", "ic_555", "ne555_timer", "timer"}
# NE555 DIP8 pin -> logical name
_555_PINS = {1: "gnd", 2: "trig", 3: "out", 4: "rst", 5: "ctrl", 6: "thr", 7: "dis", 8: "vcc"}

_MOS_TYPES = {
    "mosfet", "transistor_mosfet", "fet", "power_mosfet", "nmos", "n_mosfet",
    "n_channel_mosfet", "n_channel_fet", "logic_level_nmos",
}
_PMOS_TYPES = {
    "pmos", "p_mosfet", "p_channel_mosfet", "p_channel_fet",
    "logic_level_pmos",
}
_ACTUATOR_COIL = {  # default coil resistance per actuator type
    "motor": 20.0, "pump": 20.0, "relay": 120.0, "buzzer": 2000.0,
    "speaker": 8.0, "solenoid": 50.0, "fan": 20.0,
}
_ACTUATOR_TYPES = set(_ACTUATOR_COIL)
_LED_ON_A = 0.3e-3   # A above which an LED counts as lit
_LOAD_ON_A = 10e-3   # A above which a coil/actuator counts as running
_SENSOR_HINTS = ("sensor", "moisture", "湿度", "ldr", "photores", "thermis", "photocell")
# polarity-sensitive sensor labels: ascending R order meaning
_SENSOR_LABELS = {
    "soil": ("湿", "干"), "moisture": ("湿", "干"), "湿度": ("湿", "干"),
    "photo": ("亮", "暗"), "light": ("亮", "暗"), "photores": ("亮", "暗"),
    "thermis": ("冷", "热"),
}


def _num(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt(v: float) -> str:
    return f"{v:g}" if abs(v) < 1e6 else f"{v:.3g}"


def _fmt_amp(a: float) -> str:
    x = abs(a)
    if x >= 0.1:
        return f"{x:.2f}A"
    if x >= 1e-3:
        return f"{x * 1e3:.1f}mA"
    return f"{x * 1e6:.0f}uA"


class _Builder:
    """Turns one CircuitIR into a SPICE deck + scenario metadata."""

    def __init__(self, ir: Dict[str, Any], transient: bool = False):
        self.ir = ir
        self.transient = transient  # transient mode may model timer ICs
        self.lines: List[str] = []
        self.assumptions: List[str] = []
        self.skipped: List[str] = []
        self.skipped_refs: Set[str] = set()  # refs behind self.skipped entries
        self.actuators: List[Dict[str, Any]] = []  # {ref,type,element,kind,nodes}
        self.sources: List[str] = []
        self.nodes: List[str] = []          # measurement nodes (safe names)
        self.sensor: Optional[Dict[str, Any]] = None
        self.sensor_signal_node: Optional[str] = None
        self.has_timer = False

    def build(self) -> None:
        comps = [c for c in self.ir.get("components", []) if isinstance(c, dict)]
        # collect measurement nodes from IR nets
        for net in self.ir.get("nets", []) or []:
            if isinstance(net, dict) and net.get("name") is not None:
                safe = _safe_node(net["name"])
                if safe != "0" and safe not in self.nodes:
                    self.nodes.append(safe)
        for comp in comps:
            try:
                self._emit(comp)
            except Exception as exc:  # a single odd component must not kill the test
                logger.warning("power-on: failed to model %s: %s", comp.get("ref"), exc)
                self.skipped.append(f"{comp.get('ref') or comp.get('type')}: {exc}")
                self.skipped_refs.add(str(comp.get("ref") or ""))
        if not self.sources:
            self.lines.append("V1 VCC 0 DC 12")
            self.sources.append("V1")
            self.assumptions.append("IR 未提供电源，默认按 V1=12V DC 上电")

    # -- component mapping ---------------------------------------------------
    def _nodes(self, comp: Dict[str, Any]) -> List[str]:
        return [_safe_node(n) for n in (comp.get("nodes") or [])]

    def _ref(self, comp: Dict[str, Any]) -> str:
        return re.sub(r"\W", "_", str(comp.get("ref") or "N"))

    def _emit(self, comp: Dict[str, Any]) -> None:
        t = str(comp.get("type") or "").strip().lower()
        v = str(comp.get("value") or "")
        vu = v.upper()
        ref = self._ref(comp)
        nd = self._nodes(comp)
        line = self.lines

        if t in {"voltage_source", "dc_voltage_source", "dc_source", "battery", "supply"}:
            volts = _num(comp.get("value"), 12.0)
            if len(nd) < 2:
                raise ValueError("电源缺少两个节点")
            line.append(f"V{ref} {nd[0]} {nd[1]} DC {_fmt(volts)}")
            self.sources.append(f"V{ref}")
            return

        if t == "resistor":
            ohms = _num(comp.get("value"), 10000.0)
            if _num(comp.get("value")) is None:
                self.assumptions.append(f"{ref} 阻值非数值({v or '空'})，按 10kΩ 建模")
            if len(nd) >= 2:
                line.append(f"R{ref} {nd[0]} {nd[1]} {_fmt(ohms)}")
                return
            raise ValueError("电阻引脚不足")

        if t in {"capacitor", "cap"}:
            farads = _num(comp.get("value"), 100e-9)
            if len(nd) >= 2:
                line.append(f"C{ref} {nd[0]} {nd[1]} {_fmt(farads)}")
                return
            raise ValueError("电容引脚不足")

        if t == "inductor":
            henries = _num(comp.get("value"), 1e-3)
            if len(nd) >= 2:
                line.append(f"L{ref} {nd[0]} {nd[1]} {_fmt(henries)}")
                return
            raise ValueError("电感引脚不足")

        if t == "led":
            if len(nd) >= 2:
                if self.transient:
                    # @d..[id] device vectors freeze in transient wrdata output;
                    # a 0V sense source keeps the current a live time vector
                    s_node = f"{nd[0]}_S{ref}"
                    line.append(f"V{ref}S {nd[0]} {s_node} 0")
                    line.append(f"D{ref} {s_node} {nd[1]} PW_LED")
                    element = f"i(v{ref.lower()}s)"
                else:
                    line.append(f"D{ref} {nd[0]} {nd[1]} PW_LED")
                    # ngspice diode current parameter is 'id' (resistors use 'i')
                    element = f"@d{ref.lower()}[id]"
                self.actuators.append({"ref": comp.get("ref"), "type": "led", "element": element, "kind": "led", "nodes": [nd[0], nd[1]]})
                return
            raise ValueError("LED 引脚不足")

        if t == "zener_diode":
            if len(nd) < 2:
                raise ValueError("稳压管引脚不足")
            bv = _num(re.sub(r"[^0-9.]", "", v), 5.1)
            line.append(f".model PW_Z_{ref} D(IS=1e-14 N=1.05 RS=0.01 BV={_fmt(bv)})")
            line.append(f"D{ref} {nd[0]} {nd[1]} PW_Z_{ref}")
            return

        if t in {"diode", "tvs_diode"}:
            model = "PW_SCH" if any(k in vu for k in ("SS", "1N58", "SK", "BAT", "MBR")) else "PW_D"
            if len(nd) >= 2:
                line.append(f"D{ref} {nd[0]} {nd[1]} {model}")
                return
            raise ValueError("二极管引脚不足")

        if t in _MOS_TYPES or t in _PMOS_TYPES:
            if len(nd) < 3:
                raise ValueError("MOS 管引脚不足（需 D/G/S）")
            model = "PW_NPMOS" if t in _PMOS_TYPES else "PW_NNMOS"
            bulk = nd[2]
            line.append(f"M{ref} {nd[0]} {nd[1]} {nd[2]} {bulk} {model}")
            return

        if t in {"bjt", "transistor", "transistor_npn", "transistor_pnp", "npn", "pnp"}:
            if len(nd) < 3:
                raise ValueError("三极管引脚不足（需 C/B/E）")
            model = "PW_PNP" if ("PNP" in vu or t.endswith("pnp")) else "PW_NPN"
            line.append(f"Q{ref} {nd[0]} {nd[1]} {nd[2]} {model}")
            return

        if t in {"comparator", "comparator_ic", "opamp"}:
            rails = [n for n in nd if _is_rail(n)]
            gnds = [n for n in nd if _is_gnd(n)]
            signals = [n for n in nd if not _is_rail(n) and not _is_gnd(n)]
            if len(signals) < 3 or not rails:
                raise ValueError("IC 引脚无法区分输入/输出/电源")
            subckt = "PW_LM393" if t.startswith("comp") else "PW_OPAMP"
            vcc = rails[0]
            vgnd = gnds[0] if gnds else "0"
            # IR order for signal pins: IN+, IN-, OUT
            line.append(f"X{ref} {signals[0]} {signals[1]} {signals[2]} {vcc} {vgnd} {subckt}")
            self.assumptions.append(
                f"{comp.get('ref')} ({v or t}) 按{'开漏比较器' if subckt == 'PW_LM393' else '行为级运放'}模型连接（IN+ IN- OUT 顺序取自 IR）"
            )
            return

        if t in _TIMER_TYPES:
            if not self.transient:
                raise ValueError("555 定时器仅在上电瞬态仿真中建模，直流工况测试中排除")
            self._emit_timer(comp)
            return

        if t in {"microcontroller", "mcu"}:
            raise ValueError(f"{t} 暂不支持自动建模，已从通电测试中排除")

        if t in _ACTUATOR_TYPES:
            if len(nd) < 2:
                raise ValueError("执行器引脚不足")
            coil = _num(comp.get("value"), _ACTUATOR_COIL[t])
            if t == "buzzer" or t == "speaker":
                coil = _ACTUATOR_COIL[t]  # numeric value is a rating, not ohms
            if self.transient:
                s_node = f"{nd[0]}_S{ref}"
                line.append(f"V{ref}S {nd[0]} {s_node} 0")
                line.append(f"R{ref} {s_node} {nd[1]} {_fmt(coil)}")
                element = f"i(v{ref.lower()}s)"
            else:
                line.append(f"R{ref} {nd[0]} {nd[1]} {_fmt(coil)}")
                element = f"@r{ref.lower()}[i]"
            self.actuators.append({"ref": comp.get("ref"), "type": t, "element": element, "kind": "load", "nodes": [nd[0], nd[1]]})
            self.assumptions.append(f"{comp.get('ref')} ({t}) 按 {_fmt(coil)}Ω 阻性线圈建模")
            return

        if t in {"connector", "test_point", "header"} or not t:
            if self._sensor_like(comp):
                self._emit_sensor(comp)
                return
            self.skipped.append(f"{comp.get('ref')} ({t or 'connector'})：连接器不参与电气仿真")
            return

        raise ValueError(f"未识别的元件类型 {t}")

    def _sensor_like(self, comp: Dict[str, Any]) -> bool:
        hay = f"{comp.get('value')} {comp.get('role')} {comp.get('ref')}".lower()
        return any(h in hay for h in _SENSOR_HINTS)

    def _pin_net_map(self) -> Dict[str, Dict[int, str]]:
        """{ref: {pin_number: net_name}} from the IR nets' connections."""
        pin_map: Dict[str, Dict[int, str]] = {}
        for net in self.ir.get("nets") or []:
            if not isinstance(net, dict):
                continue
            name = str(net.get("name"))
            for conn in net.get("connections") or []:
                ref, _, pin = str(conn).rpartition(".")
                if ref and pin.isdigit():
                    pin_map.setdefault(ref, {})[int(pin)] = name
        return pin_map

    def _emit_timer(self, comp: Dict[str, Any]) -> None:
        """Place the behavioural NE555 (DIP8 pin order from the IR nets)."""
        ref = self._ref(comp)
        raw_ref = str(comp.get("ref") or "")
        pins: Dict[str, str] = {}
        by_pin = self._pin_net_map().get(raw_ref) or {}
        if len(by_pin) >= 6:
            for num, logical in _555_PINS.items():
                if num in by_pin:
                    pins[logical] = _safe_node(by_pin[num])
        if len(pins) < 6:
            # positional fallback: nodes listed in DIP8 order
            nd = self._nodes(comp)
            if len(nd) >= 8 and nd[1] == nd[5]:  # astable ties TRIG to THR
                for num, logical in _555_PINS.items():
                    pins[logical] = nd[num - 1]
        need = ("trig", "thr", "dis", "out", "vcc")
        if any(k not in pins for k in need):
            raise ValueError("555 引脚无法从 IR 的 nets/节点中映射")
        pins.setdefault("rst", pins["vcc"])
        pins.setdefault("ctrl", "NC_555_CTRL")
        pins.setdefault("gnd", "0")
        self.lines.append(
            f"X{ref} {pins['trig']} {pins['thr']} {pins['dis']} {pins['out']} "
            f"{pins['rst']} {pins['ctrl']} {pins['vcc']} {pins['gnd']} PW_555"
        )
        self.has_timer = True
        self.assumptions.append(
            f"{raw_ref} ({comp.get('value') or '555'}) 按 555 无稳态行为模型连接"
            "（2/3-1/3 VCC 施密特阈值 + 开漏放电，DIP8 引脚取自 IR）"
        )

    def _emit_sensor(self, comp: Dict[str, Any]) -> None:
        nd = self._nodes(comp)
        signal = next((n for n in nd if n != "0" and not _is_rail(n)), None)
        if not signal:
            self.skipped.append(f"{comp.get('ref')}：传感器连接器找不到信号节点")
            return
        self.sensor = {"ref": comp.get("ref"), "signal_node": signal}
        self.sensor_signal_node = signal
        self.lines.append(f"R{self._ref(comp)} {signal} 0 {{RSENSE}}")
        hay = (f"{comp.get('value')} {comp.get('role')}".lower())
        for key, (low_label, high_label) in _SENSOR_LABELS.items():
            if key in hay:
                self.sensor["labels"] = (low_label, high_label)
                break


_SWEEP = [5, 15, 25, 35, 45, 60, 80, 110, 150, 200, 300, 400, 500]  # kOhm


def _live_nodes(builder: _Builder, limit: int) -> List[str]:
    """Measurement nodes that actually exist in the emitted deck.

    An IR net whose every member component was skipped (e.g. an MCU-only
    DIG_IO bus) leaves the node unconnected; asking wrdata for it aborts the
    whole run with 'no such vector'.
    """
    body = "\n" + "\n".join(builder.lines) + " "
    live = [n for n in builder.nodes if re.search(rf"\s{re.escape(n)}\s", body)]
    return live[:limit]


# Two-terminal components the driver search walks through; anything else
# on a net (source, transistor, opamp/comparator, ...) can actively drive it.
_PASSIVE_TYPES = {
    "resistor", "res", "capacitor", "cap", "inductor", "ind",
    "diode", "led", "zener_diode", "switch",
}


def _driver_excluded(
    ir: Dict[str, Any],
    act: Dict[str, Any],
    excluded_refs: Set[str],
) -> Optional[str]:
    """Refs of excluded components standing between an actuator and its driver.

    Walks outward from the actuator's non-ground nodes through included
    passive components. Returns None when an included active component (or a
    supply) can still drive the actuator in this deck; returns the excluded
    refs the walk dead-ended on otherwise, so the caller can report a
    "not assessable here" verdict instead of a drive-chain failure.
    """
    members: Dict[str, List[Dict[str, Any]]] = {}
    for comp in ir.get("components", []) or []:
        if not isinstance(comp, dict):
            continue
        for node in comp.get("nodes") or []:
            members.setdefault(_safe_node(node), []).append(comp)

    act_ref = str(act.get("ref"))
    act_comp = next(
        (c for c in ir.get("components", []) or []
         if isinstance(c, dict) and str(c.get("ref")) == act_ref),
        None,
    )
    queue = [n for n in (act.get("nodes") or []) if not _is_gnd(n)]
    seen_nets = set(queue)
    blocked: List[str] = []
    while queue:
        net = queue.pop()
        for comp in members.get(net, []):
            if comp is act_comp:
                continue
            ref = str(comp.get("ref") or "")
            t = str(comp.get("type") or "").lower()
            if ref in excluded_refs:
                if ref and ref not in blocked:
                    blocked.append(ref)
                continue
            if t in _PASSIVE_TYPES:
                for node in comp.get("nodes") or []:
                    s = _safe_node(node)
                    if s not in seen_nets and not _is_gnd(s):
                        seen_nets.add(s)
                        queue.append(s)
                continue
            return None  # an included active component can drive this net
    return "、".join(blocked) if blocked else None


def _classify_transient(flags: List[bool], duration: float) -> Dict[str, Any]:
    """Verdict one actuator's on/off series over the transient window.

    Three or more edge crossings mean the actuator repeats (555-class
    blinker); a single on-pulse is a one-shot, not a period.
    """
    transitions = sum(1 for x, y in zip(flags, flags[1:]) if x != y)
    cycles = transitions // 2
    freq_hz = (cycles / duration) if duration > 0 and cycles else 0.0
    on_fraction = (sum(flags) / len(flags)) if flags else 0.0
    entry = {
        "on_fraction": round(on_fraction, 4),
        "transitions": transitions,
        "freq_hz": round(freq_hz, 3),
    }
    if transitions >= 3:
        extra = f"约{freq_hz:.2f}Hz 闪烁" if freq_hz >= 0.01 else "交替动作"
        entry["verdict"] = f"瞬态上电后周期动作（{extra}）"
    elif on_fraction >= 0.95:
        entry["verdict"] = "瞬态上电后持续动作（未随时间切换，请检查设计意图）"
    elif on_fraction > 0:
        entry["verdict"] = "瞬态上电后短暂动作后停止"
    else:
        entry["verdict"] = "瞬态上电后仍未动作（请检查驱动链路）"
    return entry


def _ref_transient_modelable(ir: Dict[str, Any], refs: List[str]) -> bool:
    """True when every blocking ref is a component the transient deck models."""
    refset = set(refs)
    types = {
        str(c.get("type") or "").lower()
        for c in ir.get("components") or []
        if isinstance(c, dict) and str(c.get("ref")) in refset
    }
    return bool(types) and types <= _TIMER_TYPES


def _transient_recheck(
    ir: Dict[str, Any], ngspice: str
) -> Optional[Dict[str, Any]]:
    """Power-on transient pass to verdict actuators the DC scan can't drive.

    Runs the same deck run_transient builds (supplies ramp 0->V, timer ICs
    modeled behaviorally) and classifies every actuator's current over time:
    a 555-driven LED should show periodic on/off swings. Returns None (and
    logs) when the transient run itself fails; callers then keep the neutral
    "refer to the transient tab" wording.
    """
    try:
        builder = _Builder(ir, transient=True)
        builder.build()
        if not builder.lines:
            return None
        if builder.sensor is not None:
            rsense = _SWEEP[len(_SWEEP) // 2] * 1000.0
        else:
            rsense = None
        if builder.has_timer:
            tstop_ms, tstep_us = _TRAN_TIMER_TSTOP_MS, _TRAN_TIMER_TSTEP_US
        else:
            tstop_ms, tstep_us = _TRAN_TSTOP_MS, _TRAN_TSTEP_US
        with tempfile.TemporaryDirectory(prefix="cirgpt_recheck_") as workdir:
            deck, vecs = _transient_deck(builder, rsense, tstop_ms, tstep_us)
            time_axis, series = _run_ngspice_tran(ngspice, deck, workdir, len(vecs))
    except Exception as exc:  # the DC result must survive a broken transient
        logger.warning("power-on transient recheck failed: %s", exc)
        return None

    node_count = len(_live_nodes(builder, 8))
    duration = (time_axis[-1] - time_axis[0]) if len(time_axis) > 1 else 0.0
    stats: Dict[str, Dict[str, Any]] = {}
    for j, a in enumerate(builder.actuators):
        idx = node_count + j
        cur = series[idx] if idx < len(series) else []
        threshold = _LED_ON_A if a["kind"] == "led" else _LOAD_ON_A
        flags = [abs(v) > threshold for v in cur]
        stats[str(a["ref"])] = _classify_transient(flags, duration)
    return {"performed": True, "tstop_ms": tstop_ms, "actuators": stats}


def _deck_for(builder: _Builder, rsense: Optional[float]) -> Tuple[str, List[str]]:
    """One ngspice deck (op point) + the wrdata vector list."""
    vecs = [f"v({n})" for n in _live_nodes(builder, 12)]
    for a in builder.actuators:
        vecs.append(a["element"])
    lines = ["* power-on test (auto-generated)"]
    lines.append(_MODELS)
    if builder.sensor is not None:
        lines.append(f".param RSENSE={_fmt(rsense or 100000)}")
    lines.extend(builder.lines)
    lines += ["", ".control", "set noaskquit", "op"]
    lines.append("wrdata poweron.dat " + " ".join(vecs))
    lines += [".endc", ".end"]
    return "\n".join(lines) + "\n", vecs


_TRAN_TSTEP_US = 20.0   # suggested step
_TRAN_TSTOP_MS = 20.0   # simulated window after power-on
_TRAN_RAMP_MS = 1.0     # supply ramp 0V -> full in this time
_MAX_POINTS = 800       # payload thinning for the JSON API
# a timer IC oscillates far slower than RC edges: widen the window to ~2
# periods of a 1 Hz-class blinker instead of millisecond-settling transients
_TRAN_TIMER_TSTOP_MS = 2200.0
_TRAN_TIMER_TSTEP_US = 2000.0


def _transient_deck(
    builder: _Builder,
    rsense: Optional[float],
    tstop_ms: float = _TRAN_TSTOP_MS,
    tstep_us: float = _TRAN_TSTEP_US,
) -> Tuple[str, List[str]]:
    """Power-on transient deck: supplies ramp 0->V, cap currents settle."""
    vecs = [f"v({n})" for n in _live_nodes(builder, 8)]
    for a in builder.actuators:
        vecs.append(a["element"])
    for src in builder.sources:
        # voltage-source branch currents are native time vectors; @src[i]
        # device vectors freeze in transient wrdata output
        vecs.append(f"i({src.lower()})")
    lines = ["* power-on transient (auto-generated)"]
    lines.append(_MODELS)
    if builder.sensor is not None:
        lines.append(f".param RSENSE={_fmt(rsense or 100000)}")
    for ln in builder.lines:
        m = re.match(r"^(V\S+)\s+(\S+)\s+(\S+)\s+DC\s+(\S+)$", ln)
        if m:
            lines.append(
                f"{m.group(1)} {m.group(2)} {m.group(3)} "
                f"PWL(0 0 {_fmt(_TRAN_RAMP_MS / 1000)} {m.group(4)})"
            )
        else:
            lines.append(ln)
    lines += [
        "", ".control", "set noaskquit",
        f"tran {_fmt(tstep_us / 1e6)} {_fmt(tstop_ms / 1000)}",
        "wrdata tran.dat " + " ".join(vecs),
        ".endc", ".end",
    ]
    return "\n".join(lines) + "\n", vecs


def _run_ngspice_tran(
    ngspice: str, deck: str, workdir: str, nvec: int
) -> Tuple[List[float], List[List[float]]]:
    """Run one transient deck; parse wrdata rows into (time, per-vector series).

    wrdata writes row-major: one row per time point, every vector owning a
    (scale, value) token pair - scales repeat per vector (verified against
    ngspice 41 batch output).
    """
    deck_path = os.path.join(workdir, "tran.cir")
    result_path = os.path.join(workdir, "tran.dat")
    if os.path.exists(result_path):
        os.remove(result_path)
    with open(deck_path, "w", encoding="utf-8") as fh:
        fh.write(deck)
    proc = subprocess.run(
        [ngspice, "-b", deck_path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=90, cwd=workdir,
    )
    if not os.path.exists(result_path):
        raise RuntimeError(
            "ngspice 未产出瞬态结果: " + (proc.stderr or proc.stdout or "")[-400:]
        )
    tokens = open(result_path, encoding="utf-8", errors="replace").read().split()
    row = 2 * nvec
    if not tokens or len(tokens) % row:
        raise RuntimeError(f"wrdata 输出长度异常（{len(tokens)} tokens / {nvec} 向量）")
    time_axis: List[float] = []
    series: List[List[float]] = [[] for _ in range(nvec)]
    for i in range(0, len(tokens), row):
        chunk = tokens[i:i + row]
        time_axis.append(float(chunk[0]))
        for j in range(nvec):
            series[j].append(float(chunk[2 * j + 1]))
    # thin to a JSON-friendly point count, keeping first/last
    if len(time_axis) > _MAX_POINTS:
        step = len(time_axis) / _MAX_POINTS
        keep = sorted({int(i * step) for i in range(_MAX_POINTS)} | {len(time_axis) - 1})
        time_axis = [time_axis[i] for i in keep]
        series = [[s[i] for i in keep] for s in series]
    return time_axis, series


def _run_ngspice(ngspice: str, deck: str, workdir: str) -> List[float]:
    deck_path = os.path.join(workdir, "deck.cir")
    result_path = os.path.join(workdir, "poweron.dat")
    if os.path.exists(result_path):
        os.remove(result_path)
    with open(deck_path, "w", encoding="utf-8") as fh:
        fh.write(deck)
    proc = subprocess.run(
        [ngspice, "-b", deck_path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60, cwd=workdir,
    )
    if not os.path.exists(result_path):
        raise RuntimeError(
            "ngspice 未产出结果: " + (proc.stderr or proc.stdout or "")[-400:]
        )
    parts = open(result_path, encoding="utf-8", errors="replace").read().split()
    values = [float(p) for p in parts]
    return values[1::2]  # (scale, value) pairs -> values


def run_power_on(ir: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate the IR's DC operating points across input scenarios."""
    if not ir or not ir.get("supported", False):
        raise ValueError("该设计的 CircuitIR 不受支持，无法通电测试")

    ngspice = find_ngspice()
    if not ngspice:
        raise RuntimeError(
            "未找到 ngspice。请安装到项目 Spice64/bin（见 NGSPICE_INSTALL.md）或加入 PATH"
        )

    builder = _Builder(ir)
    builder.build()
    if not builder.lines:
        raise ValueError("没有可建模的元件")

    # scenario list: sensor sweep, or a single nominal power-on
    scenarios: List[Dict[str, Any]] = []
    if builder.sensor is not None:
        labels = builder.sensor.get("labels")
        n = len(_SWEEP)
        for i, k in enumerate(_SWEEP):
            if labels:
                low_label, high_label = labels
                cond = low_label if i < n / 2 else high_label
            else:
                cond = f"R={k}kΩ"
            scenarios.append({"rsense": k * 1000.0, "label": f"{builder.sensor['ref']} {cond}（{k}kΩ）"})
    else:
        scenarios.append({"rsense": None, "label": "上电（标称工况）"})

    results: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="cirgpt_poweron_") as workdir:
        for sc in scenarios:
            deck, vecs = _deck_for(builder, sc["rsense"])
            values = _run_ngspice(ngspice, deck, workdir)
            # split node voltages vs actuator currents
            node_map = {}
            live_nodes = _live_nodes(builder, 12)
            node_count = len(live_nodes)
            for i, node in enumerate(live_nodes):
                node_map[node] = values[i] if i < len(values) else float("nan")
            act_states = []
            for j, a in enumerate(builder.actuators):
                cur = values[node_count + j] if node_count + j < len(values) else float("nan")
                threshold = _LED_ON_A if a["kind"] == "led" else _LOAD_ON_A
                act_states.append({
                    "ref": a["ref"], "type": a["type"],
                    "current_a": cur, "on": abs(cur) > threshold,
                })
            # verdict per scenario from actuators
            running = [s for s in act_states if s["on"]]
            if not builder.actuators:
                verdict = "无可判定的执行器（只有无源/电源元件）"
            elif running:
                names = "、".join(f"{s['ref']}({_fmt(abs(s['current_a']))}A)" for s in running)
                verdict = f"通电：{names} 动作"
            else:
                verdict = "通电：执行器全部待机"
            results.append({
                "label": sc["label"],
                "node_voltages": node_map,
                "actuators": act_states,
                "verdict": verdict,
            })

    # actuator response across scenarios
    response = []
    pending_transient: Dict[int, List[str]] = {}  # index -> blocking refs
    for j, a in enumerate(builder.actuators):
        states = [r["actuators"][j]["on"] for r in results if j < len(r["actuators"])]
        if any(states) and not all(states):
            resp = "随输入条件正确切换"
        elif all(states):
            resp = "持续动作（未随输入切换，请检查设计意图）"
        else:
            blocked = (
                _driver_excluded(ir, a, builder.skipped_refs)
                if builder.skipped_refs
                else None
            )
            if blocked:
                refs = blocked.split("、")
                if _ref_transient_modelable(ir, refs):
                    # the transient deck models this driver (555-class):
                    # re-check below for a real action verdict
                    pending_transient[j] = refs
                    resp = None
                else:
                    resp = f"直流工况无法判定（驱动源 {blocked} 未参与建模，无法自动判定）"
            else:
                resp = "始终未动作（请检查驱动链路）"
        response.append({"ref": a["ref"], "type": a["type"], "response": resp})

    # Actuators whose drivers only exist in the transient model: run one
    # power-on transient and verdict them from real current waveforms.
    transient_info: Optional[Dict[str, Any]] = None
    if pending_transient:
        recheck = _transient_recheck(ir, ngspice)
        if recheck is not None:
            transient_info = recheck
            for j in pending_transient:
                ref = str(builder.actuators[j]["ref"])
                entry = recheck["actuators"].get(ref)
                if entry:
                    response[j]["response"] = entry["verdict"]
        for j in pending_transient:
            if response[j]["response"] is None:
                response[j]["response"] = (
                    "直流工况无法判定（驱动源未参与直流测试，请以瞬态仿真为准）"
                )

    try:
        ver_out = subprocess.run(
            [ngspice, "-v"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=15,
        )
        m = re.search(r"ngspice-\d+", (ver_out.stdout or "") + (ver_out.stderr or ""))
        ngspice_version = m.group(0) if m else "ngspice"
    except Exception:
        ngspice_version = "ngspice"

    return {
        "success": True,
        "tool": ngspice_version,
        "scenarios": results,
        "actuator_response": response,
        "assumptions": builder.assumptions or ["所有元件按 IR 原值建模"],
        "skipped": builder.skipped,
        "sensor": builder.sensor,
        "transient": transient_info,
    }


def run_transient(ir: Dict[str, Any]) -> Dict[str, Any]:
    """Power-on transient from CircuitIR: supplies ramp 0->V, waveforms back.

    Output matches the EDA simulation result schema (time / voltages /
    currents / summary) so the generic SimulationViewer can render it; the
    representative input scenario is the middle of the sensor sweep (for a
    soil sensor that is the "dry, actuator running" side).
    """
    if not ir or not ir.get("supported", False):
        raise ValueError("该设计的 CircuitIR 不受支持，无法仿真")

    ngspice = find_ngspice()
    if not ngspice:
        raise RuntimeError(
            "未找到 ngspice。请安装到项目 Spice64/bin（见 NGSPICE_INSTALL.md）或加入 PATH"
        )

    builder = _Builder(ir, transient=True)
    builder.build()
    if not builder.lines:
        raise ValueError("没有可建模的元件")
    if builder.has_timer:
        tstop_ms, tstep_us = _TRAN_TIMER_TSTOP_MS, _TRAN_TIMER_TSTEP_US
    else:
        tstop_ms, tstep_us = _TRAN_TSTOP_MS, _TRAN_TSTEP_US

    if builder.sensor is not None:
        k = _SWEEP[len(_SWEEP) // 2]
        rsense = k * 1000.0
        labels = builder.sensor.get("labels")
        if labels:
            low_label, high_label = labels
            # same wet/dry split as run_power_on's scenario labels
            cond = low_label if len(_SWEEP) // 2 < len(_SWEEP) / 2 else high_label
        else:
            cond = f"R={k}kΩ"
        scenario_label = f"{builder.sensor['ref']} {cond}（{k}kΩ）"
    else:
        rsense = None
        scenario_label = "上电（标称工况）"

    with tempfile.TemporaryDirectory(prefix="cirgpt_tran_") as workdir:
        deck, vecs = _transient_deck(builder, rsense, tstop_ms, tstep_us)
        time_axis, series = _run_ngspice_tran(ngspice, deck, workdir, len(vecs))

    live_nodes = _live_nodes(builder, 8)
    node_count = len(live_nodes)
    voltages = {
        node: series[i]
        for i, node in enumerate(live_nodes)
        if i < len(series)
    }
    currents: Dict[str, List[float]] = {}
    for j, a in enumerate(builder.actuators):
        if node_count + j < len(series):
            currents[str(a["ref"])] = series[node_count + j]
    supply_idx = [node_count + len(builder.actuators) + k
                  for k in range(len(builder.sources))]
    total = [
        sum(series[i][p] for i in supply_idx if i < len(series))
        for p in range(len(time_axis))
    ]
    currents["total"] = total

    # Viewer-friendly aliases: "output" = the node that swings most (rails and
    # quiet nodes lose), "input" = the sensor signal node when present.
    def swing(vals: List[float]) -> float:
        return (max(vals) - min(vals)) if vals else 0.0

    if voltages and "output" not in voltages:
        main_node = max(voltages, key=lambda n: swing(voltages[n]))
        voltages["output"] = voltages[main_node]
    if builder.sensor_signal_node and builder.sensor_signal_node in voltages:
        voltages.setdefault("input", voltages[builder.sensor_signal_node])

    out_series = voltages.get("output") or []
    summary: Dict[str, Any] = {}
    if out_series:
        v_max, v_min = max(out_series), min(out_series)
        summary = {
            "voltage": {
                "max": v_max, "min": v_min,
                "avg": sum(out_series) / len(out_series),
                "peak_to_peak": v_max - v_min,
            },
            "current": {"max": max(total) if total else 0},
            "estimated_frequency": None,
        }

    return {
        "status": "success",
        "analysis_type": "transient",
        "scenario": scenario_label,
        "time": time_axis,
        "voltages": voltages,
        "currents": currents,
        "simulation_time": time_axis[-1] if time_axis else 0,
        "nodes": live_nodes,
        "summary": summary,
        "assumptions": builder.assumptions or ["所有元件按 IR 原值建模"],
        "skipped": builder.skipped,
    }
