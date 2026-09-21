"""
EDA tools router for circuit design operations
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from spice_parser import SPICEParser
from svg_generator import SVGSchematicGenerator
from ir_schematic import generate_ir_schematic_svg
from kicad_artifacts import detect_kicad_toolchain, generate_kicad_artifacts
from mcp_schematic import generate_kicad_artifacts_via_mcp, mcp_backend_available
from pyspice.simulator import simulate_circuit
from kicad.pcb_generator import generate_pcb
from bom.bom_generator import generate_bom
from circuit_ir import generate_kicad_pcb_preview, generate_spice_netlist
from power_on import run_power_on, run_transient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/eda", tags=["EDA"])


def _schematic_backend() -> str:
    """Preferred schematic generator: mcp (default) | skidl."""
    return os.environ.get("CIRGPT_SCHEMATIC_BACKEND", "mcp").strip().lower() or "mcp"


class SchematicRequest(BaseModel):
    """Request for schematic generation"""
    netlist: str
    circuit_ir: Optional[Dict[str, Any]] = None


class NetlistRequest(BaseModel):
    """Request for SPICE netlist generation from CircuitIR"""
    circuit_ir: Dict[str, Any]


class SimulationRequest(BaseModel):
    """Request for circuit simulation"""
    netlist: str
    # Connectivity netlists carry no SPICE models; with the CircuitIR the
    # service can build an engineering-model transient instead.
    circuit_ir: Optional[Dict[str, Any]] = None


class PowerOnRequest(BaseModel):
    """Request for a power-on (DC scenario) test from CircuitIR"""
    circuit_ir: Dict[str, Any]


@router.post("/poweron")
async def power_on_endpoint(request: PowerOnRequest) -> Dict[str, Any]:
    """Power-on test: modelled DC operating points across input scenarios."""
    try:
        return run_power_on(request.circuit_ir)
    except Exception as e:
        logger.error(f"Power-on test failed: {e}")
        raise HTTPException(status_code=422, detail=f"通电测试失败: {e}")


class PCBRequest(BaseModel):
    """Request for PCB generation"""
    netlist: Optional[str] = None
    circuit_ir: Optional[Dict[str, Any]] = None


class BOMRequest(BaseModel):
    """Request for BOM generation"""
    netlist: str
    design_name: str = "Circuit"


@router.post("/netlist")
async def generate_netlist_endpoint(request: NetlistRequest) -> Dict[str, Any]:
    """
    Generate a SPICE netlist from CircuitIR.
    """
    try:
        logger.info("Generating SPICE netlist from CircuitIR")
        netlist = generate_spice_netlist(request.circuit_ir)
        return {
            "success": True,
            "netlist": netlist,
            "message": "SPICE netlist generated from CircuitIR",
        }
    except Exception as e:
        logger.error(f"Error generating netlist: {e}")
        raise HTTPException(
            status_code=422,
            detail=f"Failed to generate netlist: {str(e)}"
        )


@router.post("/schematic")
async def generate_schematic_endpoint(request: SchematicRequest) -> Dict[str, Any]:
    """
    Generate circuit schematic from netlist

    Uses industrial-grade SPICE parser and SVG generator with:
    - Component-specific parsing strategies
    - Force-directed graph layout for automatic component placement
    - Pin-to-pin Manhattan routing for wires

    Args:
        request: Schematic generation request

    Returns:
        Schematic data with SVG and summary
    """
    try:
        logger.info("Generating schematic with industrial-grade pipeline")

        if request.circuit_ir:
            # MCP-driven KiCad authoring first (validated against the IR's
            # nets), then the SKiDL pipeline, then the paged/generic SVG
            # renderers. CIRGPT_SCHEMATIC_BACKEND=skidl skips the MCP path.
            kicad_result = None
            backend = _schematic_backend()
            if backend != "skidl" and mcp_backend_available():
                try:
                    kicad_result = await generate_kicad_artifacts_via_mcp(request.circuit_ir)
                except Exception as e:
                    logger.warning(f"KiCad MCP schematic generation failed, falling back: {e}")
                    kicad_result = None
            if kicad_result is None:
                try:
                    kicad_result = generate_kicad_artifacts(request.circuit_ir)
                except Exception as e:
                    logger.warning(f"KiCad/SKiDL schematic generation failed, falling back: {e}")
                    kicad_result = None

            if kicad_result and kicad_result.get("svg"):
                draft_paged = None
                try:
                    paged = generate_ir_schematic_svg(request.circuit_ir)
                    if isinstance(paged, dict):
                        draft_paged = paged
                except Exception:
                    draft_paged = None

                pages = None
                if draft_paged:
                    pages = {
                        "pages": [
                            {"subsystem": "full_schematic", "svg": kicad_result["svg"]}
                        ] + (draft_paged.get("pages") or []),
                        "summary": draft_paged.get("summary"),
                        "component_to_subsystem": draft_paged.get("component_to_subsystem"),
                        "layout": "kicad",
                    }

                summary = {
                    "title": request.circuit_ir.get("title", "Circuit"),
                    "components": len(request.circuit_ir.get("components", [])),
                    "nets": len(request.circuit_ir.get("nets", [])),
                    "algorithm": (
                        "KiCad MCP server authoring + KiCad CLI SVG export"
                        if str(kicad_result.get("generator", "")).startswith("mcp:")
                        else "SKiDL circuit capture + KiCad CLI SVG export"
                    ),
                    "generator": kicad_result.get("generator", "skidl+kicad-cli"),
                    "erc": kicad_result.get("erc_summary"),
                    "layout": kicad_result.get("layout"),
                }
                warnings = [
                    "Full schematic uses standard KiCad symbols; review ERC output before layout."
                ]
                if draft_paged:
                    warnings.append("Draft subsystem pages attached below the full schematic for layered review.")
                return {
                    "success": True,
                    "message": "KiCad/SKiDL schematic generated",
                    "svg": kicad_result["svg"],
                    "schematic_svg": kicad_result["svg"],
                    "schematic_pages": pages,
                    "summary": summary,
                    "generator": kicad_result.get("generator"),
                    "kicad_schematic": kicad_result.get("kicad_schematic"),
                    "skidl_netlist": kicad_result.get("skidl_netlist"),
                    "erc_json": kicad_result.get("erc_json"),
                    "erc_summary": kicad_result.get("erc_summary"),
                    "toolchain": kicad_result.get("toolchain"),
                    "kicad_paths": kicad_result.get("paths"),
                    "layout": kicad_result.get("layout"),
                    "warnings": warnings,
                }

            if request.circuit_ir.get("circuit_type") == "generic_circuit" or request.circuit_ir.get("subsystems"):
                svg_or_paged = generate_ir_schematic_svg(request.circuit_ir)
                if svg_or_paged:
                    if isinstance(svg_or_paged, dict):
                        summary = {
                            "title": request.circuit_ir.get("title", "Circuit"),
                            "components": len(request.circuit_ir.get("components", [])),
                            "nets": len(request.circuit_ir.get("nets", [])),
                            "algorithm": "CircuitIR subsystem-paged renderer (v2 free-form)",
                            "generator": "subsystem-paged-ir-svg",
                            "layout": svg_or_paged.get("layout"),
                            "page_count": (svg_or_paged.get("summary") or {}).get("page_count"),
                            "subsystem_count": (svg_or_paged.get("summary") or {}).get("subsystem_count"),
                        }
                        return {
                            "success": True,
                            "message": "Subsystem-paged schematic generated",
                            "svg": (svg_or_paged.get("pages") or [{}])[0].get("svg", ""),
                            "schematic_svg": (svg_or_paged.get("pages") or [{}])[0].get("svg", ""),
                            "schematic_pages": svg_or_paged,
                            "summary": summary,
                            "generator": "subsystem-paged-ir-svg",
                            "warnings": [
                                "Subsystem-paged draft; engineering review required before PCB layout."
                            ],
                        }
                    summary = {
                        "title": request.circuit_ir.get("title", "Circuit"),
                        "components": len(request.circuit_ir.get("components", [])),
                        "nets": len(request.circuit_ir.get("nets", [])),
                        "algorithm": "CircuitIR generic block/connectivity renderer",
                        "generator": "generic-ir-svg",
                    }
                    return {
                        "success": True,
                        "message": "Generic CircuitIR schematic generated",
                        "svg": svg_or_paged,
                        "summary": summary,
                        "generator": "generic-ir-svg",
                        "warnings": [
                            "Generic schematic is a conceptual connectivity draft; run engineering review before implementation."
                        ],
                    }

            svg = generate_ir_schematic_svg(request.circuit_ir)
            if svg:
                summary = {
                    "title": request.circuit_ir.get("title", "Circuit"),
                    "components": len(request.circuit_ir.get("components", [])),
                    "nets": len(request.circuit_ir.get("nets", [])),
                    "algorithm": "CircuitIR dedicated schematic renderer",
                    "generator": "circuit-ir-svg-fallback",
                }
                return {
                    "success": True,
                    "message": "CircuitIR fallback schematic generated",
                    "svg": svg,
                    "summary": summary,
                    "generator": "circuit-ir-svg-fallback",
                    "warnings": ["KiCad/SKiDL generation failed; returned SVG fallback."],
                }

        # Step 1: Parse SPICE netlist
        parser = SPICEParser()
        spice_data = parser.parse(request.netlist)
        logger.info(f"Parsed {len(spice_data['components'])} components")

        # Step 2: Generate SVG with automatic layout and routing
        generator = SVGSchematicGenerator(spice_data)
        svg = generator.generate()
        logger.info(f"Generated SVG: {len(svg)} bytes")

        # Create summary
        summary = {
            "title": spice_data.get('title', 'Circuit'),
            "components": len(spice_data['components']),
            "nets": len(spice_data['nets']),
            "algorithm": "force-directed layout + Manhattan routing"
        }

        return {
            "success": True,
            "message": "SPICE fallback schematic generated",
            "svg": svg,
            "summary": summary,
            "generator": "spice-svg-fallback",
        }

    except Exception as e:
        logger.error(f"Error generating schematic: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate schematic: {str(e)}"
        )


@router.post("/simulation")
async def simulate_circuit_endpoint(request: SimulationRequest) -> Dict[str, Any]:
    """
    Simulate circuit from netlist

    Args:
        request: Simulation request

    Returns:
        Simulation results
    """
    try:
        logger.info("Running circuit simulation")

        if "CIRGPT_SIMULATION: not_available" in request.netlist:
            ir = request.circuit_ir or {}
            if ir.get("supported"):
                try:
                    results = run_transient(ir)
                    return {"success": True, "results": results}
                except Exception as exc:
                    logger.warning(f"IR transient simulation failed: {exc}")
                    message = f"IR 瞬态仿真失败: {exc}"
            else:
                message = "Simulation is not available for generic natural-language circuit drafts."
            return {
                "success": True,
                "results": {
                    "status": "degraded",
                    "analysis_type": "not_run",
                    "time": [],
                    "voltages": {},
                    "currents": {},
                    "simulation_time": 0,
                    "nodes": [],
                    "degraded": True,
                    "message": message,
                    "summary": {},
                },
            }

        results = simulate_circuit(request.netlist)

        return {
            "success": True,
            "results": results
        }

    except Exception as e:
        logger.error(f"Error simulating circuit: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to simulate circuit: {str(e)}"
        )


@router.post("/pcb")
async def generate_pcb_endpoint(request: PCBRequest) -> Dict[str, Any]:
    """
    Generate PCB layout from netlist

    Args:
        request: PCB generation request

    Returns:
        PCB layout data
    """
    try:
        logger.info("Generating PCB layout")

        netlist = request.netlist
        if not netlist and request.circuit_ir:
            netlist = generate_spice_netlist(request.circuit_ir)
        if not netlist:
            raise ValueError("Either netlist or circuit_ir is required")

        layout = generate_pcb(netlist)
        if request.circuit_ir:
            layout["kicad_pcb"] = generate_kicad_pcb_preview(request.circuit_ir)
            layout["manufacturing_status"] = "experimental_preview_only"

        return {
            "success": True,
            "layout": layout
        }

    except Exception as e:
        logger.error(f"Error generating PCB: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PCB: {str(e)}"
        )


@router.post("/bom")
async def generate_bom_endpoint(request: BOMRequest) -> Dict[str, Any]:
    """
    Generate BOM from netlist

    Args:
        request: BOM generation request

    Returns:
        BOM data
    """
    try:
        logger.info("Generating BOM")

        bom = generate_bom(request.netlist, request.design_name)

        return {
            "success": True,
            "bom": bom
        }

    except Exception as e:
        logger.error(f"Error generating BOM: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate BOM: {str(e)}"
        )


@router.get("/tools")
async def list_eda_tools() -> Dict[str, Any]:
    """
    List available EDA tools

    Returns:
        List of tools
    """
    try:
        kicad_toolchain = detect_kicad_toolchain()
        kicad_cli = kicad_toolchain.get("kicad_cli", {})
        skidl = kicad_toolchain.get("skidl", {})
        return {
            "tools": [
                {
                    "name": "KiCad MCP (mcp-kicad-sch-api)",
                    "version": "0.2.2" if mcp_backend_available() else "not installed",
                    "description": "KiCad schematic authoring through the KiCad MCP server",
                    "status": "active" if mcp_backend_available() else "degraded"
                },
                {
                    "name": "SKiDL",
                    "version": skidl.get("version", "unknown"),
                    "description": "Schematic capture and KiCad netlist generation (fallback)",
                    "status": "active" if skidl.get("status") == "ok" else "degraded"
                },
                {
                    "name": "ngspice",
                    "version": "system",
                    "description": "Circuit simulation via ngspice subprocess",
                    "status": "active"
                },
                {
                    "name": "KiCad",
                    "version": kicad_cli.get("version", "unknown"),
                    "description": "KiCad CLI schematic SVG export and ERC",
                    "status": "active" if kicad_cli.get("status") == "ok" else "degraded"
                },
                {
                    "name": "BOM Generator",
                    "version": "1.0",
                    "description": "Bill of materials generation",
                    "status": "active"
                }
            ]
        }
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list tools: {str(e)}"
        )
