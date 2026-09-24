"""
CircuitService - Handles circuit design CRUD operations and orchestration
"""
import logging
import inspect
import json
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import func
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
            name=design_data.name or self._derive_name(design_data.description),
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

    async def list_design_summaries(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        q: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List lightweight project summaries ordered by most recently updated.

        Selects only list-page columns so heavy payloads (schematic images,
        artifacts, netlists) are never loaded for the overview.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Optional status filter (pending/processing/completed/failed)
            q: Optional substring filter on name or description

        Returns:
            {"total": int, "items": List[dict]}
        """
        query = self.db.query(
            CircuitDesign.id,
            CircuitDesign.name,
            CircuitDesign.description,
            CircuitDesign.status,
            CircuitDesign.progress,
            CircuitDesign.current_step,
            CircuitDesign.estimated_cost,
            CircuitDesign.created_at,
            CircuitDesign.updated_at,
            CircuitDesign.completed_at,
            CircuitDesign.error_message,
            func.json_extract(CircuitDesign.validation, "$.status").label("validation_status"),
            func.json_extract(CircuitDesign.validation, "$.circuit_type").label("validation_circuit_type"),
        )

        if status:
            query = query.filter(CircuitDesign.status == status)
        if q:
            pattern = f"%{q}%"
            query = query.filter(
                (CircuitDesign.name.like(pattern)) | (CircuitDesign.description.like(pattern))
            )

        total = query.count()
        rows = (
            query.order_by(CircuitDesign.updated_at.desc(), CircuitDesign.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        items = [
            {
                "id": row.id,
                "name": row.name,
                "description": self._snippet(row.description, 200),
                "status": row.status,
                "progress": row.progress,
                "current_step": row.current_step,
                "estimated_cost": row.estimated_cost,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "completed_at": row.completed_at,
                "error_message": row.error_message,
                "validation_status": row.validation_status,
                "validation_circuit_type": row.validation_circuit_type,
            }
            for row in rows
        ]
        return {"total": total, "items": items}

    @staticmethod
    def _derive_name(description: str) -> str:
        """First line of the description, trimmed to 60 chars."""
        first_line = (description or "").strip().splitlines()[0] if description else ""
        return first_line[:60]

    @staticmethod
    def _snippet(text: Optional[str], max_len: int) -> Optional[str]:
        if text is None:
            return None
        text = " ".join(text.split())
        return text if len(text) <= max_len else text[:max_len] + "…"

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
            schematic_result = await self._generate_schematic(netlist, circuit_ir)

            # Step 4: Run simulation
            await self._update_progress(progress_callback, design_id,
                                       "Running circuit simulation", 70)
            simulation_result = await self._simulate_circuit(netlist, circuit_ir)

            # Step 5: Generate PCB
            await self._update_progress(progress_callback, design_id,
                                       "Generating experimental PCB preview", 85)
            pcb_result = await self._generate_pcb(netlist, circuit_ir)

            # Step 6: Generate BOM
            await self._update_progress(progress_callback, design_id,
                                       "Generating bill of materials", 95)
            bom_result = await self._generate_bom(netlist, circuit_ir, f"Circuit_{design_id}")

            validation = self._build_validation_report(
                circuit_ir,
                simulation_result,
                pcb_result,
                schematic_result,
                skipped_components=schematic_result.get("skipped_components") or [],
            )
            artifacts = self._build_artifacts(
                netlist=netlist,
                schematic_svg=schematic_result.get("svg"),
                kicad_schematic=schematic_result.get("kicad_schematic"),
                skidl_netlist=schematic_result.get("skidl_netlist"),
                erc_json=schematic_result.get("erc_json"),
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
            design.schematic_pages = schematic_result.get("schematic_pages")
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
        requirements = data["requirements"]

        # The AI service surfaces the raw DeepSeek payload at
        # requirements["raw_deepseek_response"]. Move it into source so the
        # /raw-deepseek endpoint finds it there (source is what we look up).
        raw_deepseek = requirements.pop("raw_deepseek_response", None)
        if raw_deepseek is not None:
            source = requirements.get("source") or {}
            source["raw_response"] = raw_deepseek
            requirements["source"] = source

        return requirements

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

    async def _generate_schematic(self, netlist: str, circuit_ir: Dict[str, Any]) -> Dict[str, Any]:
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
            json={"netlist": netlist, "circuit_ir": circuit_ir}
        )

        if response.status_code != 200:
            raise Exception(f"EDA service error: {response.status_code}")

        return response.json()

    async def power_on_test(self, circuit_ir: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a power-on (DC scenario) test via the EDA service.
        """
        logger.info("Running power-on test with EDA service")

        http_client = get_http_client()
        response = await http_client.post(
            f"{self.eda_service_url}/eda/poweron",
            json={"circuit_ir": circuit_ir},
        )

        if response.status_code != 200:
            raise Exception(f"EDA service error: {response.status_code} {response.text}")

        return response.json()

    async def _simulate_circuit(
        self, netlist: str, circuit_ir: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Simulate circuit using EDA service

        Args:
            netlist: SPICE netlist
            circuit_ir: CircuitIR; lets the EDA service build an engineering
                model transient when the netlist is connectivity-only

        Returns:
            Simulation results
        """
        logger.info("Simulating circuit with EDA service")

        http_client = get_http_client()
        response = await http_client.post(
            f"{self.eda_service_url}/eda/simulation",
            json={"netlist": netlist, "circuit_ir": circuit_ir}
        )

        if response.status_code != 200:
            raise Exception(f"EDA service error: {response.status_code}")

        return response.json()

    async def rerun_simulation(self, design_id: int) -> Dict[str, Any]:
        """Re-run simulation for a stored design and persist the result."""
        design = await self.get_design(design_id)
        if not design:
            raise ValueError(f"Design {design_id} not found")
        if not design.netlist:
            raise ValueError("该设计没有网表，请先生成设计")

        simulation_result = await self._simulate_circuit(
            design.netlist, design.circuit_ir
        )
        design.simulation_results = simulation_result.get("results")
        design.simulation_status = simulation_result.get("results", {}).get("status")
        self.db.commit()
        self.db.refresh(design)
        return simulation_result

    async def generate_explanation(self, design_id: int, refresh: bool = False) -> Dict[str, Any]:
        """Generate (or return cached) circuit explanation for a design.

        The explanation is produced by the AI service from the stored
        CircuitIR and persisted on the design so it is only generated once.
        ``refresh=True`` regenerates even when a cached one exists.
        """
        design = await self.get_design(design_id)
        if not design:
            raise ValueError(f"Design {design_id} not found")
        if not design.circuit_ir:
            raise ValueError("该设计还没有 CircuitIR，请先生成设计")

        if design.circuit_explanation and not refresh:
            return {
                "explanation": design.circuit_explanation,
                "source": design.circuit_explanation.get("source", "unknown"),
                "cached": True,
            }

        http_client = get_http_client()
        response = await http_client.post(
            f"{self.ai_service_url}/ai/explain",
            json={
                "description": design.description,
                "circuit_ir": design.circuit_ir,
            },
        )
        if response.status_code != 200:
            raise Exception(f"AI service error: {response.status_code} {response.text}")

        data = response.json()
        explanation = data.get("explanation") or {}
        design.circuit_explanation = explanation
        self.db.commit()
        logger.info(
            f"Stored circuit explanation for design {design_id} "
            f"(source={data.get('source')})"
        )
        return {
            "explanation": explanation,
            "source": data.get("source"),
            "cached": False,
        }

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

    async def _generate_bom(
        self, netlist: str, circuit_ir: Optional[Dict[str, Any]], design_name: str
    ) -> Dict[str, Any]:
        """
        Generate BOM using EDA service

        Args:
            netlist: SPICE netlist (fallback when no CircuitIR exists)
            circuit_ir: CircuitIR - the single source of truth when present
            design_name: Design name

        Returns:
            BOM data
        """
        logger.info("Generating BOM with EDA service")

        http_client = get_http_client()
        payload: Dict[str, Any] = {"design_name": design_name}
        if circuit_ir:
            payload["circuit_ir"] = circuit_ir
        else:
            payload["netlist"] = netlist
        response = await http_client.post(
            f"{self.eda_service_url}/eda/bom",
            json=payload
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
        schematic_result: Dict[str, Any],
        skipped_components: List[str] = None,
    ) -> Dict[str, Any]:
        """Build an explicit validation/degraded-capability report."""
        simulation = simulation_result.get("results", {})
        pcb_layout = pcb_result.get("layout", {})
        erc_summary = schematic_result.get("erc_summary") or {}

        warnings = list(circuit_ir.get("warnings") or [])
        warnings.extend(schematic_result.get("warnings") or [])
        # full-fidelity schematics come from either KiCad authoring path;
        # the mcp: generator is the current primary one
        generator = str(schematic_result.get("generator") or "unknown")
        kicad_authored = generator == "skidl+kicad-cli" or generator.startswith("mcp:")
        if not kicad_authored:
            warnings.append(
                f"原理图由 '{generator}' 草稿渲染生成，没有 KiCad 工程文件（.kicad_sch）。"
            )
        if erc_summary.get("errors"):
            warnings.append(f"KiCad ERC 报告 {erc_summary.get('errors')} 个错误。")
        if erc_summary.get("warnings"):
            warnings.append(f"KiCad ERC 报告 {erc_summary.get('warnings')} 个警告。")
        if simulation.get("message"):
            warnings.append(simulation["message"])
        warnings.extend(pcb_layout.get("warnings") or [])

        status = "passed"
        if simulation.get("status") == "degraded" or pcb_layout.get("manufacturing_status") == "experimental_preview_only":
            status = "degraded"
        if not kicad_authored:
            status = "degraded"
        if erc_summary.get("status") in {"warning", "failed"}:
            status = "degraded"
        if simulation.get("status") == "failed":
            status = "failed"

        # 结果是否兑现了原始需求：generic_circuit 意味着规则兜底生成的占位
        # 拓扑，它不代表用户描述里要求的电路。这是与 PCB 实验性预览等
        # "能力降级" 完全不同的诚实性问题，必须单独标记并在 UI 置顶提示。
        # 个别元件/引脚掉队属于"部分未实现"，不能把整个设计混同成占位
        # 草稿——那会让 UI 说出与事实相反的话。
        generic_draft = circuit_ir.get("circuit_type") == "generic_circuit"
        unfulfilled_items: List[str] = []
        if generic_draft:
            unfulfilled_items.append(
                "整体为通用规则兜底生成的占位草稿，不代表描述中要求的电路，不可直接使用"
            )
        # 器件/引脚没能在原理图里画出来 = 部分需求未兑现，必须可见
        # （eda 路由已就同一份数据追加过"未出现"措辞的警告，这里只在
        # 尚未披露时补充，避免用户看到两条几乎相同的警告）
        skipped_components = skipped_components or []
        if skipped_components and not any(
            "未能映射到 KiCad 符号" in str(w) for w in warnings
        ):
            unfulfilled_items.append(
                "以下元件/引脚未能映射到 KiCad 符号，原理图中缺失："
                + "、".join(str(s) for s in skipped_components)
            )
        warnings.extend(unfulfilled_items)

        return {
            "status": status,
            "requirements_fulfilled": not generic_draft,
            "unfulfilled_items": unfulfilled_items,
            "circuit_type": circuit_ir.get("circuit_type"),
            "checks": {
                "circuit_ir_supported": circuit_ir.get("supported", False),
                "spice_netlist_generated": True,
                "schematic_generator": schematic_result.get("generator", "unknown"),
                "kicad_schematic_generated": bool(schematic_result.get("kicad_schematic")),
                "kicad_erc_status": erc_summary.get("status", "not_run"),
                "simulation_status": simulation.get("status", "unknown"),
                "pcb_status": pcb_layout.get("manufacturing_status", "preview"),
                "gerber_export": "disabled_in_v1",
            },
            "erc": erc_summary,
            "warnings": [warning for warning in warnings if warning],
            "errors": [] if status != "failed" else [simulation.get("error", "Simulation failed")],
        }

    def _build_artifacts(
        self,
        netlist: str,
        schematic_svg: Optional[str],
        kicad_schematic: Optional[str],
        skidl_netlist: Optional[str],
        erc_json: Optional[str],
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
        if kicad_schematic:
            artifacts["kicad_schematic"] = {
                "filename": "schematic.kicad_sch",
                "media_type": "application/octet-stream",
                "content": kicad_schematic,
            }
        if skidl_netlist:
            artifacts["skidl_netlist"] = {
                "filename": "schematic.net",
                "media_type": "text/plain",
                "content": skidl_netlist,
            }
        if erc_json:
            artifacts["erc_json"] = {
                "filename": "erc.json",
                "media_type": "application/json",
                "content": erc_json,
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
