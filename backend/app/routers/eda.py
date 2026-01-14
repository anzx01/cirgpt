from fastapi import APIRouter, Depends, HTTPException
from schemas.eda import NetlistRequest, NetlistResponse, SchematicRequest, SchematicResponse
from app.services.eda import EDAService

router = APIRouter()

@router.post("/netlist", response_model=NetlistResponse, summary="生成网表")
async def generate_netlist(netlist_request: NetlistRequest, eda_service: EDAService = Depends()):
    return await eda_service.generate_netlist(netlist_request)

@router.post("/schematic", response_model=SchematicResponse, summary="生成原理图")
async def generate_schematic(schematic_request: SchematicRequest, eda_service: EDAService = Depends()):
    return await eda_service.generate_schematic(schematic_request)

@router.post("/simulation", summary="运行仿真")
async def run_simulation(simulation_request: dict, eda_service: EDAService = Depends()):
    return await eda_service.run_simulation(simulation_request)

@router.post("/pcb", summary="生成PCB布局")
async def generate_pcb(pcb_request: dict, eda_service: EDAService = Depends()):
    return await eda_service.generate_pcb(pcb_request)