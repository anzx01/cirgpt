from fastapi import APIRouter, Depends, HTTPException
from app.schemas.circuit import CircuitCreate, CircuitResponse, CircuitUpdate
from app.services.circuit import CircuitService
from app.utils.database import get_db
from sqlalchemy.orm import Session

router = APIRouter()

@router.post("/", response_model=CircuitResponse, summary="创建电路设计")
async def create_circuit(circuit: CircuitCreate, db: Session = Depends(get_db), circuit_service: CircuitService = Depends()):
    return await circuit_service.create_circuit(circuit, db)

@router.get("/{circuit_id}", response_model=CircuitResponse, summary="获取电路设计详情")
async def get_circuit(circuit_id: int, db: Session = Depends(get_db), circuit_service: CircuitService = Depends()):
    return await circuit_service.get_circuit(circuit_id, db)

@router.get("/", response_model=list[CircuitResponse], summary="获取电路设计列表")
async def get_circuits(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), circuit_service: CircuitService = Depends()):
    return await circuit_service.get_circuits(skip, limit, db)

@router.put("/{circuit_id}", response_model=CircuitResponse, summary="更新电路设计")
async def update_circuit(circuit_id: int, circuit: CircuitUpdate, db: Session = Depends(get_db), circuit_service: CircuitService = Depends()):
    return await circuit_service.update_circuit(circuit_id, circuit, db)

@router.delete("/{circuit_id}", summary="删除电路设计")
async def delete_circuit(circuit_id: int, db: Session = Depends(get_db), circuit_service: CircuitService = Depends()):
    return await circuit_service.delete_circuit(circuit_id, db)