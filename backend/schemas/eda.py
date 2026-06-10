"""
EDA service schemas
"""
from pydantic import BaseModel
from typing import Dict, Any, Optional


class NetlistRequest(BaseModel):
    """Netlist generation request"""
    description: Optional[str] = None
    requirements: Optional[Dict[str, Any]] = None
    circuit_ir: Optional[Dict[str, Any]] = None


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
    circuit_ir: Optional[Dict[str, Any]] = None


class SchematicResponse(BaseModel):
    """Schematic generation response"""
    success: bool
    message: str
    svg: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    generator: Optional[str] = None
    kicad_schematic: Optional[str] = None
    skidl_netlist: Optional[str] = None
    erc_json: Optional[str] = None
    erc_summary: Optional[Dict[str, Any]] = None
    toolchain: Optional[Dict[str, Any]] = None
    kicad_paths: Optional[Dict[str, Any]] = None
    layout: Optional[str] = None
