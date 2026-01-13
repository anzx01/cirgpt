"""
AI service router for circuit design
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import logging

from circuit_bert.model_loader import get_model
from nlp.circuit_generator import generate_circuit_design

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI"])


class ParseRequest(BaseModel):
    """Request for parsing natural language"""
    description: str


class GenerateRequest(BaseModel):
    """Request for generating circuit design"""
    requirements: Dict[str, Any]


class ParseResponse(BaseModel):
    """Response from parsing"""
    requirements: Dict[str, Any]
    success: bool
    message: str


class GenerateResponse(BaseModel):
    """Response from generating circuit"""
    netlist: str
    success: bool
    message: str


@router.post("/parse", response_model=ParseResponse)
async def parse_natural_language(request: ParseRequest) -> ParseResponse:
    """
    Parse natural language description into circuit requirements

    Args:
        request: Parse request with description

    Returns:
        Parsed requirements
    """
    try:
        logger.info(f"Parsing: {request.description[:100]}...")

        # Get model and parse requirements
        model = get_model()
        requirements = model.parse_requirements(request.description)

        logger.info(f"Successfully parsed requirements")
        return ParseResponse(
            requirements=requirements,
            success=True,
            message="Successfully parsed natural language description"
        )

    except Exception as e:
        logger.error(f"Error parsing natural language: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse description: {str(e)}"
        )


@router.post("/generate", response_model=GenerateResponse)
async def generate_circuit(request: GenerateRequest) -> GenerateResponse:
    """
    Generate circuit netlist from requirements

    Args:
        request: Generate request with requirements

    Returns:
        Generated netlist
    """
    try:
        logger.info("Generating circuit design")

        # Generate netlist from requirements
        netlist = generate_circuit_design(request.requirements)

        logger.info("Successfully generated netlist")
        return GenerateResponse(
            netlist=netlist,
            success=True,
            message="Successfully generated circuit design"
        )

    except Exception as e:
        logger.error(f"Error generating circuit: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate circuit: {str(e)}"
        )


@router.get("/models")
async def list_models() -> Dict[str, Any]:
    """
    List available AI models

    Returns:
        List of models
    """
    try:
        return {
            "models": [
                {
                    "name": "CircuitBERT",
                    "version": "1.0",
                    "description": "Circuit design understanding model",
                    "status": "active"
                }
            ]
        }
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list models: {str(e)}"
        )
