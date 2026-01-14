"""
EDA service schemas
"""
from pydantic import BaseModel
from typing import Dict, Any, Optional


class NetlistRequest(BaseModel):
    """Netlist generation request"""
    description: str
    requirements: Optional[Dict[str, Any]] = None


class NetlistResponse(BaseModel):
    """Netlist generation response"""
    success: bool
    message: str
    netlist: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class SchematicRequest(BaseModel):
    """Schematic generation request"""
    netlist: str
    format: str = "svg"


class SchematicResponse(BaseModel):
    """Schematic generation response"""
    success: bool
    message: str
    svg: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
