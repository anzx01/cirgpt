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
from typing import Any, Dict, List, Optional, Tuple

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
"""

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

    def __init__(self, ir: Dict[str, Any]):
        self.ir = ir
        self.lines: List[str] = []
        self.assumptions: List[str] = []
        self.skipped: List[str] = []
        self.actuators: List[Dict[str, Any]] = []  # {ref,type,element,kind}
        self.sources: List[str] = []
        self.nodes: List[str] = []          # measurement nodes (safe names)
        self.sensor: Optional[Dict[str, Any]] = None
        self.sensor_signal_node: Optional[str] = None

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
                line.append(f"D{ref} {nd[0]} {nd[1]} PW_LED")
                # ngspice diode current parameter is 'id' (resistors use 'i')
                self.actuators.append({"ref": comp.get("ref"), "type": "led", "element": f"@d{ref.lower()}[id]", "kind": "led"})
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

        if t in {"timer_ic", "microcontroller", "mcu"}:
            raise ValueError(f"{t} 暂不支持自动建模，已从通电测试中排除")

        if t in _ACTUATOR_TYPES:
            if len(nd) < 2:
                raise ValueError("执行器引脚不足")
            coil = _num(comp.get("value"), _ACTUATOR_COIL[t])
            if t == "buzzer" or t == "speaker":
                coil = _ACTUATOR_COIL[t]  # numeric value is a rating, not ohms
            line.append(f"R{ref} {nd[0]} {nd[1]} {_fmt(coil)}")
            self.actuators.append({"ref": comp.get("ref"), "type": t, "element": f"@r{ref.lower()}[i]", "kind": "load"})
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


def _deck_for(builder: _Builder, rsense: Optional[float]) -> Tuple[str, List[str]]:
    """One ngspice deck (op point) + the wrdata vector list."""
    vecs = [f"v({n})" for n in builder.nodes[:12]]
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


def _transient_deck(builder: _Builder, rsense: Optional[float]) -> Tuple[str, List[str]]:
    """Power-on transient deck: supplies ramp 0->V, cap currents settle."""
    vecs = [f"v({n})" for n in builder.nodes[:8]]
    for a in builder.actuators:
        vecs.append(a["element"])
    for src in builder.sources:
        vecs.append(f"@{src.lower()}[i]")
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
        f"tran {_fmt(_TRAN_TSTEP_US / 1e6)} {_fmt(_TRAN_TSTOP_MS / 1000)}",
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
            node_count = min(len(builder.nodes), 12)
            for i, node in enumerate(builder.nodes[:node_count]):
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
    for j, a in enumerate(builder.actuators):
        states = [r["actuators"][j]["on"] for r in results if j < len(r["actuators"])]
        if any(states) and not all(states):
            resp = "随输入条件正确切换"
        elif all(states):
            resp = "持续动作（未随输入切换，请检查设计意图）"
        else:
            resp = "始终未动作（请检查驱动链路）"
        response.append({"ref": a["ref"], "type": a["type"], "response": resp})

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

    builder = _Builder(ir)
    builder.build()
    if not builder.lines:
        raise ValueError("没有可建模的元件")

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
        deck, vecs = _transient_deck(builder, rsense)
        time_axis, series = _run_ngspice_tran(ngspice, deck, workdir, len(vecs))

    node_count = min(len(builder.nodes), 8)
    voltages = {
        node: series[i]
        for i, node in enumerate(builder.nodes[:node_count])
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
        "nodes": list(builder.nodes[:node_count]),
        "summary": summary,
        "assumptions": builder.assumptions or ["所有元件按 IR 原值建模"],
        "skipped": builder.skipped,
    }
