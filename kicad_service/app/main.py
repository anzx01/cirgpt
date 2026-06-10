"""
KiCad Schematic Generation Service
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="KiCad Schematic Generator",
    version="1.0.0",
    description="Professional schematic generation using SKiDL and KiCad"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SchematicRequest(BaseModel):
    """Request to generate schematic"""
    circuit_ir: Dict[str, Any]

@app.get("/")
async def root():
    """Health check"""
    return {
        "message": "KiCad Schematic Generator Service",
        "version": "1.0.0",
        "status": "ready"
    }

@app.post("/generate")
async def generate_schematic(request: SchematicRequest):
    """
    Generate professional KiCad schematic from CircuitIR

    This endpoint uses SKiDL to generate:
    - Professional IC symbols (triangle op-amps, DIP packages)
    - Proper pin labeling
    - Standard KiCad .kicad_sch files
    - High-quality netlists
    """
    try:
        from app.services.schematic_generator import KiCadSchematicGenerator

        logger.info(f"Received schematic generation request")

        # Generate schematic
        generator = KiCadSchematicGenerator()
        result = generator.generate_from_circuit_ir(request.circuit_ir)

        logger.info(f"✅ Schematic generated successfully")

        return {
            "success": True,
            "schematic_path": result['schematic_path'],
            "netlist": result['netlist'],
            "message": result['message'],
            "generator": "SKiDL + KiCad"
        }

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate schematic: {str(e)}")

@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        # Test SKiDL import
        import skidl
        return {
            "status": "healthy",
            "skidl_version": skidl.__version__,
            "service": "KiCad Schematic Generator"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
