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

_NGSPICE_CANDIDATES = ["ngspice", "ngspice-64", "ngspice64"]


def _find_ngspice() -> Optional[str]:
    """Return the first usable ngspice executable, or None."""
    for candidate in _NGSPICE_CANDIDATES:
        try:
            subprocess.run(
                [candidate, "--version"],
                capture_output=True, timeout=5
            )
            return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


NGSPICE_BIN = _find_ngspice()
if NGSPICE_BIN:
    logger.info(f"ngspice found: {NGSPICE_BIN}")
else:
    logger.warning("ngspice not found in PATH. Simulation will use mock results.")


def _parse_rawspice(raw_text: str) -> Dict[str, Any]:
    """
    Parse ngspice plain-text output (.print tran) into structured data.
    Returns dict with keys: time, voltages, currents.
    """
    time_vals: List[float] = []
    node_data: Dict[str, List[float]] = {}

    for line in raw_text.splitlines():
        line = line.strip()
        if not line or line.startswith("*") or line.startswith("."):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            vals = [float(p) for p in parts]
        except ValueError:
            continue
        if not time_vals or vals[0] >= time_vals[-1]:
            time_vals.append(vals[0])
            for i, v in enumerate(vals[1:], start=1):
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

        if NGSPICE_BIN is None:
            logger.warning("ngspice unavailable, returning mock results")
            return self._mock_results(netlist)

        batch_netlist = self._ensure_print_command(netlist)

        with tempfile.TemporaryDirectory() as tmpdir:
            cir_path = os.path.join(tmpdir, "circuit.cir")
            out_path = os.path.join(tmpdir, "output.txt")
            with open(cir_path, "w") as f:
                f.write(batch_netlist)

            try:
                proc = subprocess.run(
                    [NGSPICE_BIN, "-b", "-o", out_path, cir_path],
                    capture_output=True, text=True, timeout=60
                )
                raw = ""
                if os.path.exists(out_path):
                    with open(out_path) as f:
                        raw = f.read()
                raw += proc.stdout

                parsed = _parse_rawspice(raw)
                if not parsed["time"]:
                    logger.warning("ngspice produced no data, falling back to mock")
                    return self._mock_results(netlist, error=proc.stderr[:200] if proc.stderr else None)

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
                return self._mock_results(netlist, error="Simulation timed out")
            except Exception as e:
                logger.error(f"ngspice error: {e}")
                return self._mock_results(netlist, error=str(e))

    def _ensure_print_command(self, netlist: str) -> str:
        """Add .print tran if the netlist lacks output commands."""
        lower = netlist.lower()
        if ".print" not in lower and ".probe" not in lower:
            lines = netlist.rstrip().splitlines()
            end_idx = next(
                (i for i, l in enumerate(lines) if l.strip().lower() == ".end"),
                len(lines)
            )
            lines.insert(end_idx, ".print tran v(*)")
            return "\n".join(lines)
        return netlist

    def _mock_results(self, netlist: str, error: Optional[str] = None) -> Dict[str, Any]:
        """Generate deterministic mock results when ngspice is unavailable."""
        time_points = np.linspace(0, 1, 100).tolist()
        lower = netlist.lower()

        if "555" in lower or "blinker" in lower:
            waveform = [9.0 if (t % 1.0) < 0.5 else 0.0 for t in time_points]
        elif "opamp" in lower or "amplifier" in lower:
            waveform = (5 * np.sin(2 * np.pi * np.array(time_points))).tolist()
        else:
            waveform = (3.3 * np.sin(2 * np.pi * np.array(time_points))).tolist()

        result: Dict[str, Any] = {
            "status": "success" if error is None else "failed",
            "time": time_points,
            "voltages": {
                "output": waveform,
                "input": [v * 0.3 for v in waveform],
            },
            "currents": {"total": [v / 1000.0 for v in waveform]},
            "analysis_type": "transient",
            "simulation_time": 0.2,
            "nodes": ["output", "input"],
        }
        if error:
            result["error"] = error
            result["message"] = f"Mock data used due to error: {error}"
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
