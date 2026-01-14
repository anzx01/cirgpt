"""
AI service schemas
"""
from pydantic import BaseModel
from typing import Dict, Any, Optional


class AIRequest(BaseModel):
    """AI service request"""
    description: str
    requirements: Optional[Dict[str, Any]] = None


class AIResponse(BaseModel):
    """AI service response"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class ParseRequest(BaseModel):
    """Parse natural language request"""
    description: str


class ParseResponse(BaseModel):
    """Parse response"""
    requirements: Dict[str, Any]
    success: bool
    message: str


class GenerateRequest(BaseModel):
    """Generate circuit request"""
    requirements: Dict[str, Any]


class GenerateResponse(BaseModel):
    """Generate response"""
    netlist: str
    success: bool
    message: str
