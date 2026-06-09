"""
CircuitService - Handles circuit design CRUD operations and orchestration
"""
import logging
import inspect
import json
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from models import CircuitDesign, DesignHistory
from schemas import CircuitDesignCreate, CircuitDesignUpdate
from app.config import settings
from app.utils.http_client import get_http_client
from app.websocket import notify_progress, notify_complete, notify_error

logger = logging.getLogger(__name__)


class CircuitService:
    """Service for managing circuit designs"""

    def __init__(self, db: Session):
        """
        Initialize circuit service

        Args:
            db: Database session
        """
        self.db = db
        self.ai_service_url = settings.AI_SERVICE_URL.rstrip("/")
        self.eda_service_url = settings.EDA_SERVICE_URL.rstrip("/")

    async def create_design(self, design_data: CircuitDesignCreate) -> CircuitDesign:
        """
        Create a new circuit design

        Args:
            design_data: Design creation data

        Returns:
            Created circuit design
        """
        logger.info(f"Creating new circuit design: {design_data.description[:50]}...")

        design = CircuitDesign(
            description=design_data.description,
            status="pending",
            progress=0,
            current_step="Waiting to start"
        )

        self.db.add(design)
        self.db.commit()
        self.db.refresh(design)

        logger.info(f"✓ Created circuit design with ID: {design.id}")
        return design

    async def get_design(self, design_id: int) -> Optional[CircuitDesign]:
        """
        Get circuit design by ID

        Args:
            design_id: Design ID

        Returns:
            Circuit design or None
        """
        return self.db.query(CircuitDesign).filter(CircuitDesign.id == design_id).first()

    async def list_designs(self, skip: int = 0, limit: int = 100) -> List[CircuitDesign]:
        """
        List all circuit designs

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of circuit designs
        """
        return self.db.query(CircuitDesign).offset(skip).limit(limit).all()

    async def update_design(self, design_id: int,
                           update_data: CircuitDesignUpdate) -> Optional[CircuitDesign]:
        """
        Update circuit design

        Args:
            design_id: Design ID
            update_data: Update data

        Returns:
            Updated circuit design or None
        """
        design = await self.get_design(design_id)
        if not design:
            return None

        # Update fields
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(design, field, value)

        design.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(design)

        logger.info(f"✓ Updated circuit design {design_id}")
        return design

    async def delete_design(self, design_id: int) -> bool:
        """
        Delete circuit design

        Args:
            design_id: Design ID

        Returns:
            True if deleted, False if not found
        """
        design = await self.get_design(design_id)
        if not design:
            return False

        # Save to history before deleting
        self._save_to_history(design, "Deleted")

        self.db.delete(design)
        self.db.commit()

        logger.info(f"✓ Deleted circuit design {design_id}")
        return True

    async def generate_circuit(self, design_id: int,
                              progress_callback=None) -> Dict[str, Any]:
        """
        Generate complete circuit design from description

        Args:
            design_id: Design ID
            progress_callback: Optional callback for progress updates

        Returns:
            Generation results
        """
        logger.info(f"Starting circuit generation for design {design_id}")

        design = await self.get_design(design_id)
        if not design:
            raise ValueError(f"Design {design_id} not found")

        try:
            # Update status to processing
            design.status = "processing"
            design.progress = 0
            design.current_step = "Starting generation"
            design.job_id = design.job_id or f"local-{design_id}-{uuid.uuid4().hex[:8]}"
            design.error_message = None
            self.db.commit()

            # Step 1: Parse natural language into CircuitIR
            await self._update_progress(progress_callback, design_id,
                                       "Parsing natural language into CircuitIR", 10)
            circuit_ir = await self._parse_description(design.description)
            if not circuit_ir.get("supported", False):
                warnings = circuit_ir.get("warnings") or ["Unsupported circuit request"]
                raise ValueError(warnings[0])

            # Step 2: Generate netlist from IR
            await self._update_progress(progress_callback, design_id,
                                       "Generating SPICE netlist", 30)
            netlist = await self._generate_netlist_from_ir(circuit_ir)

            # Step 3: Generate schematic
            await self._update_progress(progress_callback, design_id,
                                       "Generating schematic", 50)
            schematic_result = await self._generate_schematic(netlist)

            # Step 4: Run simulation
            await self._update_progress(progress_callback, design_id,
                                       "Running circuit simulation", 70)
            simulation_result = await self._simulate_circuit(netlist)

            # Step 5: Generate PCB
            await self._update_progress(progress_callback, design_id,
                                       "Generating experimental PCB preview", 85)
            pcb_result = await self._generate_pcb(netlist, circuit_ir)

            # Step 6: Generate BOM
            await self._update_progress(progress_callback, design_id,
                                       "Generating bill of materials", 95)
            bom_result = await self._generate_bom(netlist, f"Circuit_{design_id}")

            validation = self._build_validation_report(circuit_ir, simulation_result, pcb_result)
            artifacts = self._build_artifacts(
                netlist=netlist,
                schematic_svg=schematic_result.get("svg"),
                simulation_result=simulation_result.get("results"),
                pcb_layout=pcb_result.get("layout"),
                bom=bom_result.get("bom"),
                validation=validation,
            )

            # Update design with results
            design.circuit_ir = circuit_ir
            design.parsed_requirements = circuit_ir
            design.netlist = netlist
            design.schematic_svg = schematic_result.get("svg")
            design.simulation_results = simulation_result.get("results")
            design.simulation_status = simulation_result.get("results", {}).get("status")
            design.pcb_layout = pcb_result.get("layout")
            design.pcb_image = pcb_result.get("layout", {}).get("visualization")
            design.pcb_gerber_files = None
            design.bom = bom_result.get("bom")
            design.estimated_cost = bom_result.get("bom", {}).get("summary", {}).get("total_cost")
            design.validation = validation
            design.artifacts = artifacts
            design.status = "completed"
            design.progress = 100
            design.current_step = "Design generation complete"
            design.completed_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(design)

            await self._update_progress(progress_callback, design_id,
                                       "Design generation complete", 100)

            logger.info(f"✓ Circuit generation complete for design {design_id}")
            await notify_complete(design_id)
            return {"success": True, "design_id": design_id, "job_id": design.job_id}

        except Exception as e:
            logger.error(f"✗ Error generating circuit {design_id}: {e}")
            design.status = "failed"
            design.progress = 0
            design.current_step = "Generation failed"
            design.error_message = str(e)
            design.validation = {
                "status": "failed",
                "errors": [str(e)],
                "warnings": [],
            }
            self.db.commit()

            await self._update_progress(progress_callback, design_id,
                                       f"Error: {str(e)}", 0, error=True)

            raise

    async def _parse_description(self, description: str) -> Dict[str, Any]:
        """
        Parse natural language description using AI service

        Args:
            description: Natural language description

        Returns:
            Parsed requirements
        """
        logger.info("Parsing description with AI service")

        http_client = get_http_client()
        response = await http_client.post(
            f"{self.ai_service_url}/ai/parse",
            json={"description": description}
        )

        if response.status_code != 200:
            raise Exception(f"AI service error: {response.status_code}")

        data = response.json()
        return data["requirements"]

    async def _generate_netlist_from_ir(self, circuit_ir: Dict[str, Any]) -> str:
        """
        Generate netlist from CircuitIR using EDA service

        Args:
            circuit_ir: Structured circuit IR

        Returns:
            SPICE netlist
        """
        logger.info("Generating netlist with EDA service")

        http_client = get_http_client()
        response = await http_client.post(
            f"{self.eda_service_url}/eda/netlist",
            json={"circuit_ir": circuit_ir}
        )

        if response.status_code != 200:
            raise Exception(f"EDA service error: {response.status_code} {response.text}")

        data = response.json()
        return data["netlist"]

    async def _generate_schematic(self, netlist: str) -> Dict[str, Any]:
        """
        Generate schematic from netlist using EDA service

        Args:
            netlist: SPICE netlist

        Returns:
            Schematic data
        """
        logger.info("Generating schematic with EDA service")

        http_client = get_http_client()
        response = await http_client.post(
            f"{self.eda_service_url}/eda/schematic",
            json={"netlist": netlist}
        )

        if response.status_code != 200:
            raise Exception(f"EDA service error: {response.status_code}")

        return response.json()

    async def _simulate_circuit(self, netlist: str) -> Dict[str, Any]:
        """
        Simulate circuit using EDA service

        Args:
            netlist: SPICE netlist

        Returns:
            Simulation results
        """
        logger.info("Simulating circuit with EDA service")

        http_client = get_http_client()
        response = await http_client.post(
            f"{self.eda_service_url}/eda/simulation",
            json={"netlist": netlist}
        )

        if response.status_code != 200:
            raise Exception(f"EDA service error: {response.status_code}")

        return response.json()

    async def _generate_pcb(self, netlist: str, circuit_ir: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate PCB layout using EDA service

        Args:
            netlist: SPICE netlist

        Returns:
            PCB layout data
        """
        logger.info("Generating PCB with EDA service")

        http_client = get_http_client()
        response = await http_client.post(
            f"{self.eda_service_url}/eda/pcb",
            json={"netlist": netlist, "circuit_ir": circuit_ir}
        )

        if response.status_code != 200:
            raise Exception(f"EDA service error: {response.status_code}")

        return response.json()

    async def _generate_bom(self, netlist: str, design_name: str) -> Dict[str, Any]:
        """
        Generate BOM using EDA service

        Args:
            netlist: SPICE netlist
            design_name: Design name

        Returns:
            BOM data
        """
        logger.info("Generating BOM with EDA service")

        http_client = get_http_client()
        response = await http_client.post(
            f"{self.eda_service_url}/eda/bom",
            json={"netlist": netlist, "design_name": design_name}
        )

        if response.status_code != 200:
            raise Exception(f"EDA service error: {response.status_code}")

        return response.json()

    async def _update_progress(self, callback, design_id: int,
                              message: str, progress: int,
                              error: bool = False):
        """
        Update progress via callback and Socket.io

        Args:
            callback: Progress callback function (optional)
            design_id: Design ID
            message: Progress message
            progress: Progress percentage (0-100)
            error: Whether this is an error message
        """
        # Send Socket.io notification
        if error:
            await notify_error(design_id, message)
        else:
            await notify_progress(design_id, message, progress)

        design = await self.get_design(design_id)
        if design:
            design.progress = progress
            design.current_step = message
            design.updated_at = datetime.utcnow()
            self.db.commit()

        # Call callback if provided
        if callback:
            result = callback(design_id, message, progress, error)
            if inspect.isawaitable(result):
                await result

    def _build_validation_report(
        self,
        circuit_ir: Dict[str, Any],
        simulation_result: Dict[str, Any],
        pcb_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build an explicit validation/degraded-capability report."""
        simulation = simulation_result.get("results", {})
        pcb_layout = pcb_result.get("layout", {})

        warnings = list(circuit_ir.get("warnings") or [])
        if simulation.get("message"):
            warnings.append(simulation["message"])
        warnings.extend(pcb_layout.get("warnings") or [])

        status = "passed"
        if simulation.get("status") == "degraded" or pcb_layout.get("manufacturing_status") == "experimental_preview_only":
            status = "degraded"
        if simulation.get("status") == "failed":
            status = "failed"

        return {
            "status": status,
            "circuit_type": circuit_ir.get("circuit_type"),
            "checks": {
                "circuit_ir_supported": circuit_ir.get("supported", False),
                "spice_netlist_generated": True,
                "simulation_status": simulation.get("status", "unknown"),
                "pcb_status": pcb_layout.get("manufacturing_status", "preview"),
                "gerber_export": "disabled_in_v1",
            },
            "warnings": [warning for warning in warnings if warning],
            "errors": [] if status != "failed" else [simulation.get("error", "Simulation failed")],
        }

    def _build_artifacts(
        self,
        netlist: str,
        schematic_svg: Optional[str],
        simulation_result: Optional[Dict[str, Any]],
        pcb_layout: Optional[Dict[str, Any]],
        bom: Optional[Dict[str, Any]],
        validation: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """Create downloadable artifact records stored with the design."""
        artifacts: Dict[str, Dict[str, Any]] = {
            "netlist": {
                "filename": "circuit.spice",
                "media_type": "text/plain",
                "content": netlist,
            },
            "validation_json": {
                "filename": "validation.json",
                "media_type": "application/json",
                "content": json.dumps(validation, indent=2),
            },
        }

        if schematic_svg:
            artifacts["schematic_svg"] = {
                "filename": "schematic.svg",
                "media_type": "image/svg+xml",
                "content": schematic_svg,
            }
        if bom and bom.get("csv"):
            artifacts["bom_csv"] = {
                "filename": "bom.csv",
                "media_type": "text/csv",
                "content": bom["csv"],
            }
        if pcb_layout and pcb_layout.get("kicad_pcb"):
            artifacts["kicad_pcb"] = {
                "filename": "preview.kicad_pcb",
                "media_type": "application/octet-stream",
                "content": pcb_layout["kicad_pcb"],
            }
        if simulation_result:
            artifacts["simulation_json"] = {
                "filename": "simulation.json",
                "media_type": "application/json",
                "content": json.dumps(simulation_result, indent=2),
            }

        return artifacts

    def _save_to_history(self, design: CircuitDesign, change_description: str):
        """
        Save design snapshot to history

        Args:
            design: Circuit design
            change_description: Description of the change
        """
        # Get version number
        history_count = self.db.query(DesignHistory).filter(
            DesignHistory.design_id == design.id
        ).count()

        history = DesignHistory(
            design_id=design.id,
            version=history_count + 1,
            description=design.description,
            netlist=design.netlist,
            schematic_svg=design.schematic_svg,
            simulation_results=design.simulation_results,
            pcb_layout=design.pcb_layout,
            bom=design.bom,
            change_description=change_description
        )

        self.db.add(history)

    async def get_design_status(self, design_id: int) -> Dict[str, Any]:
        """
        Get design generation status

        Args:
            design_id: Design ID

        Returns:
            Status information
        """
        design = await self.get_design(design_id)
        if not design:
            return {"error": "Design not found"}

        return {
            "id": design.id,
            "status": design.status,
            "job_id": design.job_id,
            "current_step": design.current_step,
            "progress": design.progress,
            "error_message": design.error_message,
            "created_at": design.created_at.isoformat() if design.created_at else None,
            "completed_at": design.completed_at.isoformat() if design.completed_at else None
        }
