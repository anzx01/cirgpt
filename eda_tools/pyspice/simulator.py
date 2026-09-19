"""
ngspice subprocess wrapper for circuit simulation.
Replaces the PySpice (GPLv3) dependency with a direct ngspice call.
ngspice is distributed under BSD/ISC-compatible terms.
"""
import logging
import subprocess
import tempfile
import os
import re
import numpy as np
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# ngspice_con first: the windowed ngspice.exe shipped in official Windows
# builds hangs on "--version" (no console), so probing it always times out.
_NGSPICE_CANDIDATES = ["ngspice_con", "ngspice", "ngspice-64", "ngspice64"]


def _find_ngspice() -> Optional[str]:
    """Return the first usable ngspice executable, or None."""
    for candidate in _NGSPICE_CANDIDATES:
        try:
            subprocess.run(
                [candidate, "--version"],
                capture_output=True, timeout=15
            )
            return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


NGSPICE_BIN = _find_ngspice()
if NGSPICE_BIN:
    logger.info(f"ngspice found: {NGSPICE_BIN}")
else:
    logger.warning("ngspice not found in PATH. Simulation will use degraded analytical previews.")


def _ngspice_bin() -> Optional[str]:
    """Resolve ngspice on demand; retries discovery if the import-time probe failed.

    The first run of an unsigned exe can exceed the probe timeout (e.g. a cold
    antivirus scan right after service start), which would otherwise pin
    NGSPICE_BIN to None for the life of the process.
    """
    global NGSPICE_BIN
    if NGSPICE_BIN is None:
        NGSPICE_BIN = _find_ngspice()
        if NGSPICE_BIN:
            logger.info(f"ngspice found on retry: {NGSPICE_BIN}")
    return NGSPICE_BIN


_NODE_TOKEN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NON_NODE_KEYWORDS = {"dc", "ac", "pulse", "sin", "tran", "led", "0"}


def _extract_nodes(netlist: str) -> List[str]:
    """Collect node names from two-terminal element lines (heuristic).

    Element lines look like ``R1 N1 N2 1k`` / ``V1 N1 0 DC 5`` / ``D1 N1 N2 MODEL``:
    tokens 1 and 2 are the nodes. Ground ('0') and value/model keywords are skipped.
    """
    nodes: List[str] = []
    seen = set()
    for line in netlist.splitlines():
        s = line.strip()
        if not s or s[0] in "*+.xX":
            continue
        tokens = s.split()
        if not _NODE_TOKEN_RE.match(tokens[0]):
            continue
        for t in tokens[1:3]:
            if _NODE_TOKEN_RE.match(t) and t.lower() not in _NON_NODE_KEYWORDS and t not in seen:
                seen.add(t)
                nodes.append(t)
    return nodes


def _parse_rawspice(raw_text: str) -> Dict[str, Any]:
    """
    Parse ngspice plain-text output (.print tran) into structured data.
    Returns dict with keys: time, voltages, currents.

    ngspice batch ASCII tables are "Index <tab> time <tab> values...";
    the index column is skipped so the time axis is real seconds.
    """
    time_vals: List[float] = []
    node_data: Dict[str, List[float]] = {}

    for line in raw_text.splitlines():
        line = line.strip()
        if not line or line.startswith("*") or line.startswith("."):
            continue
        parts = line.split()
        if len(parts) < 3:  # index + time + at least one value
            continue
        try:
            vals = [float(p) for p in parts]
        except ValueError:
            continue
        t = vals[1]
        if not time_vals or t >= time_vals[-1]:
            time_vals.append(t)
            for i, v in enumerate(vals[2:], start=1):
                key = f"node_{i}"
                node_data.setdefault(key, []).append(v)

    voltages = {k: v for k, v in node_data.items() if not k.startswith("i_")}
    currents = {k[2:]: v for k, v in node_data.items() if k.startswith("i_")}
    return {"time": time_vals, "voltages": voltages, "currents": currents}


class CircuitSimulator:
    """Simulate circuits using ngspice subprocess."""

    def simulate_circuit(self, netlist: str) -> Dict[str, Any]:
        """
        Simulate circuit from SPICE netlist string.

        Returns simulation results dict with keys:
          status, time, voltages, currents, analysis_type, simulation_time, nodes.
        """
        logger.info("Starting circuit simulation")

        ngspice_bin = _ngspice_bin()
        if ngspice_bin is None:
            logger.warning("ngspice unavailable, returning degraded analytical preview")
            return self._degraded_results(netlist, "ngspice executable not found in PATH")

        batch_netlist = self._ensure_print_command(netlist)

        with tempfile.TemporaryDirectory() as tmpdir:
            cir_path = os.path.join(tmpdir, "circuit.cir")
            out_path = os.path.join(tmpdir, "output.txt")
            with open(cir_path, "w") as f:
                f.write(batch_netlist)

            try:
                proc = subprocess.run(
                    [ngspice_bin, "-b", "-o", out_path, cir_path],
                    capture_output=True, text=True, timeout=60
                )
                raw = ""
                if os.path.exists(out_path):
                    with open(out_path) as f:
                        raw = f.read()
                raw += proc.stdout

                parsed = _parse_rawspice(raw)
                if not parsed["time"]:
                    logger.warning("ngspice produced no data, returning degraded analytical preview")
                    return self._degraded_results(netlist, error=proc.stderr[:200] if proc.stderr else "ngspice produced no data")

                result = {
                    "status": "success",
                    "time": parsed["time"],
                    "voltages": parsed["voltages"],
                    "currents": parsed["currents"],
                    "analysis_type": "transient",
                    "simulation_time": parsed["time"][-1] if parsed["time"] else 0,
                    "nodes": list(parsed["voltages"].keys()),
                }
                logger.info(f"Simulation completed: {len(result['time'])} time points")
                return result

            except subprocess.TimeoutExpired:
                logger.error("ngspice simulation timed out")
                return self._degraded_results(netlist, error="Simulation timed out")
            except Exception as e:
                logger.error(f"ngspice error: {e}")
                return self._degraded_results(netlist, error=str(e))

    def _ensure_print_command(self, netlist: str) -> str:
        """Add .print tran if the netlist lacks output commands.

        ngspice batch mode does not accept the v(*) wildcard in .print, so the
        node names are enumerated from the element lines explicitly.
        """
        lower = netlist.lower()
        if ".print" not in lower and ".probe" not in lower:
            nodes = _extract_nodes(netlist)[:8] or ["out"]
            lines = netlist.rstrip().splitlines()
            end_idx = next(
                (i for i, l in enumerate(lines) if l.strip().lower() == ".end"),
                len(lines)
            )
            print_cmd = ".print tran " + " ".join(f"v({n})" for n in nodes)
            lines.insert(end_idx, print_cmd)
            return "\n".join(lines)
        return netlist

    def _degraded_results(self, netlist: str, error: Optional[str] = None) -> Dict[str, Any]:
        """Generate deterministic preview data and mark it as degraded."""
        time_points = np.linspace(0, 1, 100).tolist()
        lower = netlist.lower()

        if "555" in lower or "blinker" in lower:
            waveform = [9.0 if (t % 1.0) < 0.5 else 0.0 for t in time_points]
        elif "opamp" in lower or "amplifier" in lower:
            waveform = (5 * np.sin(2 * np.pi * np.array(time_points))).tolist()
        else:
            waveform = (3.3 * np.sin(2 * np.pi * np.array(time_points))).tolist()

        result: Dict[str, Any] = {
            "status": "degraded",
            "time": time_points,
            "voltages": {
                "output": waveform,
                "input": [v * 0.3 for v in waveform],
            },
            "currents": {"total": [v / 1000.0 for v in waveform]},
            "analysis_type": "transient",
            "simulation_time": 0.2,
            "nodes": ["output", "input"],
            "degraded": True,
            "message": f"Analytical preview used because real ngspice simulation was unavailable: {error}",
        }
        if error:
            result["error"] = error
        return result

    def analyze_operating_point(self, netlist: str) -> Dict[str, Any]:
        """Analyze DC operating point (returns representative mock data)."""
        return {
            "node_voltages": {"1": 9.0, "2": 4.5, "3": 0.0},
            "device_currents": {"V1": 0.01, "R1": 0.005},
            "power_dissipation": 0.09,
        }

    def generate_waveform_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Summarise voltage/current waveform statistics."""
        voltages = results.get("voltages", {}).get("output", [])
        currents = results.get("currents", {}).get("total", [])
        if not voltages:
            return {}
        v_max, v_min = max(voltages), min(voltages)
        v_avg = sum(voltages) / len(voltages)
        return {
            "voltage": {
                "max": v_max, "min": v_min, "avg": v_avg,
                "peak_to_peak": v_max - v_min,
            },
            "current": {"max": max(currents) if currents else 0},
            "estimated_frequency": 1.0,
            "power": {
                "avg": v_avg * (sum(currents) / len(currents)) if currents else 0
            },
        }


def simulate_circuit(netlist: str) -> Dict[str, Any]:
    """Simulate a SPICE netlist and return results with waveform summary."""
    sim = CircuitSimulator()
    results = sim.simulate_circuit(netlist)
    results["summary"] = sim.generate_waveform_summary(results)
    return results
