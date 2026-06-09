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
from pyspice.simulator import simulate_circuit
from kicad.pcb_generator import generate_pcb
from bom.bom_generator import generate_bom
from circuit_ir import generate_kicad_pcb_preview, generate_spice_netlist

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/eda", tags=["EDA"])


class SchematicRequest(BaseModel):
    """Request for schematic generation"""
    netlist: str


class NetlistRequest(BaseModel):
    """Request for SPICE netlist generation from CircuitIR"""
    circuit_ir: Dict[str, Any]


class SimulationRequest(BaseModel):
    """Request for circuit simulation"""
    netlist: str


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
            "svg": svg,
            "summary": summary
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
        return {
            "tools": [
                {
                    "name": "SKiDL",
                    "version": "2.0",
                    "description": "Schematic generation",
                    "status": "active"
                },
                {
                    "name": "ngspice",
                    "version": "system",
                    "description": "Circuit simulation via ngspice subprocess",
                    "status": "active"
                },
                {
                    "name": "KiCad",
                    "version": "7.0",
                    "description": "PCB layout generation",
                    "status": "active"
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
