from fastapi import APIRouter, Depends

from app.services.eda import EDAService
from schemas.eda import NetlistRequest, NetlistResponse, SchematicRequest, SchematicResponse


router = APIRouter()


@router.post("/netlist", response_model=NetlistResponse, summary="Generate SPICE netlist")
async def generate_netlist(netlist_request: NetlistRequest, eda_service: EDAService = Depends()):
    return await eda_service.generate_netlist(netlist_request)


@router.post("/schematic", response_model=SchematicResponse, summary="Generate schematic")
async def generate_schematic(schematic_request: SchematicRequest, eda_service: EDAService = Depends()):
    return await eda_service.generate_schematic(schematic_request)


@router.post("/simulation", summary="Run simulation")
async def run_simulation(simulation_request: dict, eda_service: EDAService = Depends()):
    return await eda_service.run_simulation(simulation_request)


@router.post("/pcb", summary="Generate experimental PCB preview")
async def generate_pcb(pcb_request: dict, eda_service: EDAService = Depends()):
    return await eda_service.generate_pcb(pcb_request)


@router.post("/bom", summary="Generate BOM")
async def generate_bom(bom_request: dict, eda_service: EDAService = Depends()):
    return await eda_service.generate_bom(bom_request)
