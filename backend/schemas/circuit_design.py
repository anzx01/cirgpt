from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class CircuitDesignCreate(BaseModel):
    """Schema for creating a circuit design"""
    description: str = Field(..., description="Natural language description of the circuit")
    name: Optional[str] = Field(None, max_length=200, description="Display name; auto-derived from description when omitted")


class CircuitDesignUpdate(BaseModel):
    """Schema for updating a circuit design"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[int] = None
    current_step: Optional[str] = None
    job_id: Optional[str] = None
    circuit_ir: Optional[Dict[str, Any]] = None
    parsed_requirements: Optional[Dict[str, Any]] = None
    netlist: Optional[str] = None
    schematic_svg: Optional[str] = None
    schematic_png: Optional[str] = None
    schematic_pages: Optional[Dict[str, Any]] = None
    simulation_results: Optional[Dict[str, Any]] = None
    simulation_status: Optional[str] = None
    pcb_layout: Optional[Dict[str, Any]] = None
    pcb_gerber_files: Optional[Dict[str, str]] = None
    pcb_image: Optional[str] = None
    bom: Optional[Dict[str, Any]] = None
    estimated_cost: Optional[float] = None
    validation: Optional[Dict[str, Any]] = None
    artifacts: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class CircuitDesignResponse(BaseModel):
    """Schema for circuit design response"""
    id: int
    name: Optional[str] = None
    description: str
    status: str
    progress: Optional[int] = 0
    current_step: Optional[str] = None
    job_id: Optional[str] = None
    circuit_ir: Optional[Dict[str, Any]] = None
    parsed_requirements: Optional[Dict[str, Any]] = None
    netlist: Optional[str] = None
    schematic_svg: Optional[str] = None
    schematic_png: Optional[str] = None
    schematic_pages: Optional[Dict[str, Any]] = None
    simulation_results: Optional[Dict[str, Any]] = None
    simulation_status: Optional[str] = None
    pcb_layout: Optional[Dict[str, Any]] = None
    pcb_gerber_files: Optional[Dict[str, str]] = None
    pcb_image: Optional[str] = None
    bom: Optional[Dict[str, Any]] = None
    estimated_cost: Optional[float] = None
    validation: Optional[Dict[str, Any]] = None
    artifacts: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class CircuitDesignSummary(BaseModel):
    """Lightweight schema for project lists (excludes heavy result payloads)"""
    id: int
    name: Optional[str] = None
    description: Optional[str] = None
    status: str
    progress: Optional[int] = 0
    current_step: Optional[str] = None
    estimated_cost: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    validation_status: Optional[str] = None
    validation_circuit_type: Optional[str] = None


class CircuitDesignList(BaseModel):
    """Schema for list of circuit designs"""
    designs: List[CircuitDesignResponse]
    total: int
    page: int
    page_size: int


class BatchDeleteRequest(BaseModel):
    """IDs of designs to delete in one call (project list multi-select)"""
    ids: List[int] = Field(..., description="Design IDs to delete; empty list is rejected")
