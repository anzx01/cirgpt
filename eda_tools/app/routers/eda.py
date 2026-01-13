"""
EDA tools router for circuit design operations
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import logging

from skidl.schematic_generator import generate_schematic
from pyspice.simulator import simulate_circuit
from kicad.pcb_generator import generate_pcb
from bom.bom_generator import generate_bom

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/eda", tags=["EDA"])


class SchematicRequest(BaseModel):
    """Request for schematic generation"""
    netlist: str


class SimulationRequest(BaseModel):
    """Request for circuit simulation"""
    netlist: str


class PCBRequest(BaseModel):
    """Request for PCB generation"""
    netlist: str


class BOMRequest(BaseModel):
    """Request for BOM generation"""
    netlist: str
    design_name: str = "Circuit"


@router.post("/schematic")
async def generate_schematic_endpoint(request: SchematicRequest) -> Dict[str, Any]:
    """
    Generate circuit schematic from netlist

    Args:
        request: Schematic generation request

    Returns:
        Schematic data
    """
    try:
        logger.info("Generating schematic")

        svg, summary = generate_schematic(request.netlist)

        return {
            "success": True,
            "svg": svg,
            "summary": summary
        }

    except Exception as e:
        logger.error(f"Error generating schematic: {e}")
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

        layout = generate_pcb(request.netlist)

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
                    "name": "PySpice",
                    "version": "1.5",
                    "description": "Circuit simulation",
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
