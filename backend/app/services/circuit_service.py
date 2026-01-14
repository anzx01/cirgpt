"""
CircuitService - Handles circuit design CRUD operations and orchestration
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from models import CircuitDesign, DesignHistory
from schemas import CircuitDesignCreate, CircuitDesignUpdate
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
        self.ai_service_url = "http://localhost:8001"
        self.eda_service_url = "http://localhost:8002"

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
            status="pending"
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
            self.db.commit()

            # Step 1: Parse natural language
            await self._update_progress(progress_callback, design_id,
                                       "Parsing natural language", 10)
            parsed_requirements = await self._parse_description(design.description)

            # Step 2: Generate netlist
            await self._update_progress(progress_callback, design_id,
                                       "Generating circuit netlist", 30)
            netlist = await self._generate_netlist(parsed_requirements)

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
                                       "Generating PCB layout", 85)
            pcb_result = await self._generate_pcb(netlist)

            # Step 6: Generate BOM
            await self._update_progress(progress_callback, design_id,
                                       "Generating bill of materials", 95)
            bom_result = await self._generate_bom(netlist, f"Circuit_{design_id}")

            # Update design with results
            design.parsed_requirements = parsed_requirements
            design.netlist = netlist
            design.schematic_svg = schematic_result.get("svg")
            design.simulation_results = simulation_result.get("results")
            design.simulation_status = simulation_result.get("results", {}).get("status")
            design.pcb_layout = pcb_result.get("layout")
            design.pcb_image = pcb_result.get("layout", {}).get("visualization")
            design.bom = bom_result.get("bom")
            design.estimated_cost = bom_result.get("bom", {}).get("summary", {}).get("total_cost")
            design.status = "completed"
            design.completed_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(design)

            await self._update_progress(progress_callback, design_id,
                                       "Design generation complete", 100)

            logger.info(f"✓ Circuit generation complete for design {design_id}")
            return {"success": True, "design_id": design_id}

        except Exception as e:
            logger.error(f"✗ Error generating circuit {design_id}: {e}")
            design.status = "failed"
            design.error_message = str(e)
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

    async def _generate_netlist(self, requirements: Dict[str, Any]) -> str:
        """
        Generate netlist from requirements using AI service

        Args:
            requirements: Parsed requirements

        Returns:
            SPICE netlist
        """
        logger.info("Generating netlist with AI service")

        http_client = get_http_client()
        response = await http_client.post(
            f"{self.ai_service_url}/ai/generate",
            json={"requirements": requirements}
        )

        if response.status_code != 200:
            raise Exception(f"AI service error: {response.status_code}")

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

    async def _generate_pcb(self, netlist: str) -> Dict[str, Any]:
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
            json={"netlist": netlist}
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

        # Call callback if provided
        if callback:
            await callback(design_id, message, progress, error)

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
            "error_message": design.error_message,
            "created_at": design.created_at.isoformat() if design.created_at else None,
            "completed_at": design.completed_at.isoformat() if design.completed_at else None
        }
