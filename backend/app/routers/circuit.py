"""
Circuit design router
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import logging

from schemas import CircuitDesignCreate, CircuitDesignUpdate, CircuitDesignResponse, DesignStatus
from app.services.circuit_service import CircuitService
from app.utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["circuit"])


def get_circuit_service(db: Session = Depends(get_db)) -> CircuitService:
    """Dependency to get circuit service"""
    return CircuitService(db)


@router.post("/", response_model=CircuitDesignResponse, summary="Create circuit design")
async def create_circuit(
    design_data: CircuitDesignCreate,
    service: CircuitService = Depends(get_circuit_service)
):
    """
    Create a new circuit design from natural language description

    The design will be created with status 'pending' and can be generated
    using the POST /circuit/{id}/generate endpoint
    """
    try:
        design = await service.create_design(design_data)
        return design
    except Exception as e:
        logger.error(f"Error creating circuit design: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[CircuitDesignResponse], summary="List circuit designs")
async def list_circuits(
    skip: int = 0,
    limit: int = 100,
    service: CircuitService = Depends(get_circuit_service)
):
    """Get list of all circuit designs"""
    try:
        designs = await service.list_designs(skip, limit)
        return designs
    except Exception as e:
        logger.error(f"Error listing circuits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{design_id}", response_model=CircuitDesignResponse, summary="Get circuit design")
async def get_circuit(
    design_id: int,
    service: CircuitService = Depends(get_circuit_service)
):
    """Get circuit design by ID"""
    design = await service.get_design(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Circuit design not found")
    return design


@router.put("/{design_id}", response_model=CircuitDesignResponse, summary="Update circuit design")
async def update_circuit(
    design_id: int,
    update_data: CircuitDesignUpdate,
    service: CircuitService = Depends(get_circuit_service)
):
    """Update circuit design"""
    try:
        design = await service.update_design(design_id, update_data)
        if not design:
            raise HTTPException(status_code=404, detail="Circuit design not found")
        return design
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating circuit {design_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{design_id}", summary="Delete circuit design")
async def delete_circuit(
    design_id: int,
    service: CircuitService = Depends(get_circuit_service)
):
    """Delete circuit design"""
    try:
        success = await service.delete_design(design_id)
        if not success:
            raise HTTPException(status_code=404, detail="Circuit design not found")
        return {"message": "Circuit design deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting circuit {design_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{design_id}/generate", summary="Generate circuit design")
async def generate_circuit(
    design_id: int,
    background_tasks: BackgroundTasks,
    service: CircuitService = Depends(get_circuit_service)
):
    """
    Generate complete circuit design (schematic, simulation, PCB, BOM)

    This is an async operation. Use GET /circuit/{id}/status to check progress.
    """
    design = await service.get_design(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Circuit design not found")

    if design.status == "processing":
        return {"message": "Circuit generation is already in progress"}

    # Add background task for generation
    background_tasks.add_task(service.generate_circuit, design_id)

    return {
        "message": "Circuit generation started",
        "design_id": design_id,
        "status": "processing"
    }


@router.get("/{design_id}/status", response_model=DesignStatus, summary="Get generation status")
async def get_circuit_status(
    design_id: int,
    service: CircuitService = Depends(get_circuit_service)
):
    """Get circuit generation status"""
    status = await service.get_design_status(design_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status
