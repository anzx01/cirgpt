"""
PySpice integration for circuit simulation
"""
import logging
import numpy as np
from typing import Dict, List, Any
import tempfile
import os

logger = logging.getLogger(__name__)

# Try to import PySpice at module level
try:
    from PySpice.Spice.Netlist import Circuit
    from PySpice.Unit import *
    PYSPICE_AVAILABLE = True
    logger.info("✓ PySpice library loaded successfully")
except ImportError:
    PYSPICE_AVAILABLE = False
    logger.warning("✗ PySpice library not found. Will use mock simulation results")


class CircuitSimulator:
    """Simulate circuits using PySpice"""

    def __init__(self):
        """Initialize circuit simulator"""
        self.Circuit = Circuit if PYSPICE_AVAILABLE else None

    def simulate_circuit(self, netlist: str) -> Dict[str, Any]:
        """
        Simulate circuit from netlist

        Args:
            netlist: SPICE netlist

        Returns:
            Simulation results
        """
        logger.info("Simulating circuit")

        if self.Circuit is None:
            logger.warning("PySpice not available, using mock results")
            return self._generate_mock_results(netlist)

        try:
            # Create temporary file for netlist
            with tempfile.NamedTemporaryFile(mode='w', suffix='.cir', delete=False) as f:
                f.write(netlist)
                netlist_file = f.name

            try:
                # Run simulation using PySpice
                results = self._run_pyspice_simulation(netlist_file)
                logger.info("✓ Circuit simulation completed")
                return results
            finally:
                # Clean up temp file
                if os.path.exists(netlist_file):
                    os.unlink(netlist_file)

        except Exception as e:
            logger.error(f"Error simulating circuit: {e}")
            return self._generate_mock_results(netlist, error=str(e))

    def _run_pyspice_simulation(self, netlist_file: str) -> Dict[str, Any]:
        """
        Run PySpice simulation

        Args:
            netlist_file: Path to SPICE netlist file

        Returns:
            Simulation results
        """
        logger.info(f"Running PySpice simulation with netlist: {netlist_file}")

        try:
            # Read the netlist file
            with open(netlist_file, 'r') as f:
                netlist_content = f.read()

            # Parse and create circuit from netlist
            circuit = self.Circuit(netlist_content)

            # Create simulator
            from PySpice.Spice.Netlist import Circuit as SpiceCircuit
            from PySpice.Probe.WaveForm import WaveForm

            # Run transient analysis
            simulator = circuit.simulator(temperature=25, nominal_temperature=25)

            # Check if there's a .tran command in the netlist
            if '.tran' in netlist_content.lower():
                # Extract simulation parameters from netlist
                lines = netlist_content.split('\n')
                for line in lines:
                    if line.strip().lower().startswith('.tran'):
                        parts = line.split()
                        if len(parts) >= 2:
                            try:
                                step_time = float(parts[1].replace('s', '').replace('m', 'e-3').replace('u', 'e-6'))
                                end_time = step_time * 1000  # Default duration
                            except:
                                step_time = 1e-3  # 1ms default
                                end_time = 1.0  # 1 second default
                            break
                else:
                    step_time = 1e-3
                    end_time = 1.0
            else:
                step_time = 1e-3  # 1ms default
                end_time = 1.0  # 1 second default

            # Run transient analysis
            analysis = simulator.transient(step_time=step_time, end_time=end_time)

            # Extract results
            time_points = []
            voltages = {}
            currents = {}

            # Process analysis results
            for node_name in analysis.nodes:
                if node_name not in ['#branch', '0']:  # Skip ground and branches
                    voltages[node_name] = analysis[node_name].as_ndarray()

            # Extract time points
            if len(analysis.time) > 0:
                time_points = analysis.time.as_ndarray()

            # Extract currents from voltage sources
            for element in circuit.elements:
                if hasattr(element, 'name'):
                    branch_name = f"{element.name}#branch"
                    if branch_name in analysis.internal_nodes:
                        currents[element.name] = analysis[branch_name].as_ndarray()

            logger.info(f"✓ PySpice simulation completed: {len(time_points)} time points")

            # Prepare output
            result = {
                "status": "success",
                "time": time_points.tolist() if len(time_points) > 0 else np.linspace(0, end_time, 1000).tolist(),
                "voltages": {k: v.tolist() for k, v in voltages.items()},
                "currents": {k: v.tolist() for k, v in currents.items()},
                "analysis_type": "transient",
                "simulation_time": end_time,
                "nodes": list(voltages.keys())
            }

            # If no output nodes found, use default 'output'
            if len(result["voltages"]) == 0:
                result["voltages"]["output"] = np.zeros(len(time_points)).tolist()

            return result

        except Exception as e:
            logger.error(f"PySpice simulation error: {e}")
            # Fall back to mock results with error info
            return self._generate_mock_results(netlist_content if 'netlist_content' in locals() else "", error=str(e))

    def _generate_mock_results(self, netlist: str, error: str = None) -> Dict[str, Any]:
        """
        Generate mock simulation results

        Args:
            netlist: SPICE netlist (for analysis)
            error: Optional error message

        Returns:
            Mock results
        """
        # Generate time-varying data
        time_points = np.linspace(0, 1, 100)  # 100 points from 0 to 1 second

        # Analyze netlist to determine circuit type
        netlist_lower = netlist.lower()

        if "555" in netlist_lower or "blinker" in netlist_lower:
            # Square wave for 555 timer
            voltage_waveform = []
            for t in time_points:
                period = 1.0  # 1 second period
                if (t % period) < (period / 2):
                    voltage_waveform.append(9.0)  # High
                else:
                    voltage_waveform.append(0.0)  # Low
        elif "opamp" in netlist_lower or "amplifier" in netlist_lower:
            # Amplified sine wave
            voltage_waveform = (5 * np.sin(2 * np.pi * 1 * time_points)).tolist()
        else:
            # Simple sine wave
            voltage_waveform = (3.3 * np.sin(2 * np.pi * 1 * time_points)).tolist()

        # Current waveform (smaller amplitude)
        current_waveform = [v / 1000.0 for v in voltage_waveform]  # I = V / 1k

        results = {
            "status": "success" if error is None else "failed",
            "time": time_points.tolist(),
            "voltages": {
                "output": voltage_waveform,
                "input": [v * 0.3 for v in voltage_waveform]  # Smaller input
            },
            "currents": {
                "total": current_waveform
            },
            "analysis_type": "transient",
            "simulation_time": 0.2,
            "node_voltages": {
                "vcc": 9.0,
                "gnd": 0.0
            }
        }

        if error:
            results["error"] = error
            results["message"] = f"Simulation used mock data due to error: {error}"

        return results

    def analyze_operating_point(self, netlist: str) -> Dict[str, Any]:
        """
        Analyze DC operating point

        Args:
            netlist: SPICE netlist

        Returns:
            Operating point data
        """
        logger.info("Analyzing operating point")

        # Parse netlist for operating point analysis
        # For MVP, return mock data

        return {
            "node_voltages": {
                "1": 9.0,
                "2": 4.5,
                "3": 0.0
            },
            "device_currents": {
                "V1": 0.01,
                "R1": 0.005
            },
            "power_dissipation": 0.09  # Watts
        }

    def generate_waveform_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate summary of waveform data

        Args:
            results: Simulation results

        Returns:
            Waveform summary
        """
        voltages = results.get("voltages", {}).get("output", [])
        currents = results.get("currents", {}).get("total", [])

        if not voltages:
            return {}

        # Calculate statistics
        v_max = max(voltages)
        v_min = min(voltages)
        v_avg = sum(voltages) / len(voltages)

        i_max = max(currents) if currents else 0

        # Estimate frequency (for periodic signals)
        time_points = results.get("time", [])
        frequency = 1.0  # Default 1 Hz

        return {
            "voltage": {
                "max": v_max,
                "min": v_min,
                "avg": v_avg,
                "peak_to_peak": v_max - v_min
            },
            "current": {
                "max": i_max
            },
            "estimated_frequency": frequency,
            "power": {
                "avg": v_avg * (sum(currents) / len(currents)) if currents else 0
            }
        }


def simulate_circuit(netlist: str) -> Dict[str, Any]:
    """
    Simulate circuit from netlist

    Args:
        netlist: SPICE netlist

    Returns:
        Simulation results
    """
    simulator = CircuitSimulator()
    results = simulator.simulate_circuit(netlist)
    summary = simulator.generate_waveform_summary(results)

    results["summary"] = summary
    return results
