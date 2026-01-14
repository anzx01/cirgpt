from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class CircuitDesignCreate(BaseModel):
    """Schema for creating a circuit design"""
    description: str = Field(..., description="Natural language description of the circuit")


class CircuitDesignUpdate(BaseModel):
    """Schema for updating a circuit design"""
    description: Optional[str] = None
    status: Optional[str] = None
    parsed_requirements: Optional[Dict[str, Any]] = None
    netlist: Optional[str] = None
    schematic_svg: Optional[str] = None
    schematic_png: Optional[str] = None
    simulation_results: Optional[Dict[str, Any]] = None
    simulation_status: Optional[str] = None
    pcb_layout: Optional[Dict[str, Any]] = None
    pcb_gerber_files: Optional[Dict[str, str]] = None
    pcb_image: Optional[str] = None
    bom: Optional[List[Dict[str, Any]]] = None
    estimated_cost: Optional[float] = None
    error_message: Optional[str] = None


class CircuitDesignResponse(BaseModel):
    """Schema for circuit design response"""
    id: int
    description: str
    status: str
    parsed_requirements: Optional[Dict[str, Any]] = None
    netlist: Optional[str] = None
    schematic_svg: Optional[str] = None
    schematic_png: Optional[str] = None
    simulation_results: Optional[Dict[str, Any]] = None
    simulation_status: Optional[str] = None
    pcb_layout: Optional[Dict[str, Any]] = None
    pcb_gerber_files: Optional[Dict[str, str]] = None
    pcb_image: Optional[str] = None
    bom: Optional[List[Dict[str, Any]]] = None
    estimated_cost: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class CircuitDesignList(BaseModel):
    """Schema for list of circuit designs"""
    designs: List[CircuitDesignResponse]
    total: int
    page: int
    page_size: int
