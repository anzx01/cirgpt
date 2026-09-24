"""
Circuit design router
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import uuid

from schemas import (
    CircuitDesignCreate,
    CircuitDesignUpdate,
    CircuitDesignResponse,
    CircuitDesignSummary,
    BatchDeleteRequest,
    CircuitChatRequest,
    DesignStatus,
)
from app.services.circuit_service import CircuitService
from app.utils.database import get_db
from models import SessionLocal, CircuitDesign

logger = logging.getLogger(__name__)

router = APIRouter(tags=["circuit"])


def get_circuit_service(db: Session = Depends(get_db)) -> CircuitService:
    """Dependency to get circuit service"""
    return CircuitService(db)


async def run_generation_background(design_id: int):
    """Run generation with a fresh DB session outside request scope."""
    db = SessionLocal()
    try:
        service = CircuitService(db)
        await service.generate_circuit(design_id)
    finally:
        db.close()


async def run_revision_background(design_id: int, message: str, attachments=None):
    """Run a chat-driven circuit revision with a fresh DB session.

    The /chat endpoint claims the design (status=processing) before scheduling
    this task, so any failure here — including revise_circuit's own pre-checks
    raising before its recovery path kicks in — must release the claim, or the
    design stays stuck in processing forever.
    """
    db = SessionLocal()
    try:
        service = CircuitService(db)
        await service.revise_circuit(design_id, message, attachments=attachments)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Revision background task crashed for design {design_id}: {exc}")
        try:
            design = db.query(CircuitDesign).filter(CircuitDesign.id == design_id).first()
            if design and design.status == "processing":
                design.status = "completed"
                design.progress = 100
                design.current_step = "电路修改失败（已保留原电路）"
                db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
    finally:
        db.close()


@router.post("/", response_model=CircuitDesignResponse, summary="Create circuit design")
async def create_circuit(
    design_data: CircuitDesignCreate,
    service: CircuitService = Depends(get_circuit_service)
):
    """
    Create a new circuit design from natural language description

    The design will be created with status 'pending' and can be generated
    using the POST /circuit/{id}/generate endpoint
    """
    try:
        design = await service.create_design(design_data)
        return design
    except Exception as e:
        logger.error(f"Error creating circuit design: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[CircuitDesignSummary], summary="List circuit designs")
async def list_circuits(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    q: Optional[str] = None,
    service: CircuitService = Depends(get_circuit_service),
    response: Response = None,
):
    """List circuit designs as lightweight summaries (most recently updated first).

    Query params: `skip`/`limit` for paging, `status` (pending/processing/
    completed/failed) to filter by state, `q` to search name/description.
    The total number of matching designs is returned in the `X-Total-Count`
    response header.
    """
    if status and status not in ("pending", "processing", "completed", "failed"):
        raise HTTPException(status_code=400, detail="Invalid status filter")
    try:
        result = await service.list_design_summaries(skip=skip, limit=limit, status=status, q=q)
        response.headers["X-Total-Count"] = str(result["total"])
        return result["items"]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing circuits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{design_id}", response_model=CircuitDesignResponse, summary="Get circuit design")
async def get_circuit(
    design_id: int,
    service: CircuitService = Depends(get_circuit_service),
    response: Response = None,
):
    """Get circuit design by ID"""
    # Design state changes after every generation/revision; a heuristic
    # browser cache would freeze the UI on stale data.
    if response is not None:
        response.headers["Cache-Control"] = "no-store"
    design = await service.get_design(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Circuit design not found")
    return design


@router.put("/{design_id}", response_model=CircuitDesignResponse, summary="Update circuit design")
async def update_circuit(
    design_id: int,
    update_data: CircuitDesignUpdate,
    service: CircuitService = Depends(get_circuit_service)
):
    """Update circuit design"""
    try:
        design = await service.update_design(design_id, update_data)
        if not design:
            raise HTTPException(status_code=404, detail="Circuit design not found")
        return design
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating circuit {design_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-delete", summary="Batch delete circuit designs")
async def batch_delete_circuits(
    request: BatchDeleteRequest,
    service: CircuitService = Depends(get_circuit_service),
):
    """Delete several designs in one call (project list multi-select).

    Each ID is deleted independently: a missing or failing ID never blocks
    the others; per-ID outcomes are reported so the UI can show exactly
    what happened.
    """
    ids = list(dict.fromkeys(request.ids))  # dedupe, keep order
    if not ids:
        raise HTTPException(status_code=400, detail="ids must not be empty")

    deleted: List[int] = []
    failed: List[dict] = []
    for design_id in ids:
        try:
            if await service.delete_design(design_id):
                deleted.append(design_id)
            else:
                failed.append({"id": design_id, "error": "not found"})
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Error deleting circuit {design_id}: {exc}")
            failed.append({"id": design_id, "error": str(exc)[:200]})

    return {
        "deleted": deleted,
        "deleted_count": len(deleted),
        "failed": failed,
        "failed_count": len(failed),
    }


@router.delete("/{design_id}", summary="Delete circuit design")
async def delete_circuit(
    design_id: int,
    service: CircuitService = Depends(get_circuit_service)
):
    """Delete circuit design"""
    try:
        success = await service.delete_design(design_id)
        if not success:
            raise HTTPException(status_code=404, detail="Circuit design not found")
        return {"message": "Circuit design deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting circuit {design_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{design_id}/generate", summary="Generate circuit design")
async def generate_circuit(
    design_id: int,
    background_tasks: BackgroundTasks,
    service: CircuitService = Depends(get_circuit_service)
):
    """
    Generate complete circuit design (schematic, simulation, PCB, BOM)

    This is an async operation. Use GET /circuit/{id}/status to check progress.
    """
    design = await service.get_design(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Circuit design not found")

    if design.status == "processing":
        return {"message": "Circuit generation is already in progress"}

    job_id = f"local-{design_id}-{uuid.uuid4().hex[:8]}"
    design.status = "processing"
    design.progress = 0
    design.current_step = "Queued for generation"
    design.job_id = job_id
    design.error_message = None
    service.db.commit()

    background_tasks.add_task(run_generation_background, design_id)

    return {
        "message": "Circuit generation started",
        "design_id": design_id,
        "job_id": job_id,
        "status": "processing"
    }


@router.post("/{design_id}/chat", summary="Chat: revise the circuit with one instruction")
async def chat_revise_circuit(
    design_id: int,
    request: CircuitChatRequest,
    background_tasks: BackgroundTasks,
    service: CircuitService = Depends(get_circuit_service),
):
    """Apply one natural-language modification to the stored design.

    Accepts optional attachments: pasted/uploaded images (forwarded to the
    vision-capable model) and documents (plain text or PDF; extracted text
    becomes reference context for the revision).

    The revision runs asynchronously: the AI service rewrites the CircuitIR,
    then netlist / schematic / simulation / PCB / BOM / explanation are all
    regenerated. Progress arrives on the same design.progress / WebSocket
    channel as generation; the chat log persists on the design. If the
    revision fails, the previous circuit is kept untouched and the reason is
    reported through the chat log.
    """
    design = await service.get_design(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Circuit design not found")
    if not design.circuit_ir:
        raise HTTPException(status_code=400, detail="该设计还没有电路数据（CircuitIR），请先生成设计")
    if design.status == "processing":
        raise HTTPException(status_code=409, detail="该设计正在生成或修改中，请稍候")
    if not request.message.strip() and not request.attachments:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    try:
        attachments = CircuitService._process_chat_attachments(request.attachments)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Claim the design synchronously so a double-submit gets 409 instead of
    # queueing two concurrent revisions.
    design.status = "processing"
    design.progress = 0
    design.current_step = "理解修改要求"
    service.db.commit()

    background_tasks.add_task(
        run_revision_background, design_id, request.message, attachments
    )
    return {
        "message": "电路修改已开始",
        "design_id": design_id,
        "status": "processing",
    }


@router.post("/{design_id}/poweron", summary="Run a power-on (DC scenario) test")
async def power_on_circuit(
    design_id: int,
    service: CircuitService = Depends(get_circuit_service)
):
    """
    Power-on test: modelled DC operating points across input scenarios
    (e.g. soil wet/dry), executed by the EDA service via ngspice.
    """
    design = await service.get_design(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Circuit design not found")
    if not design.circuit_ir:
        raise HTTPException(status_code=400, detail="该设计还没有 CircuitIR，请先生成设计")

    try:
        return await service.power_on_test(design.circuit_ir)
    except Exception as e:
        logger.error(f"Power-on test failed for design {design_id}: {e}")
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/{design_id}/simulate", summary="Re-run circuit simulation")
async def simulate_circuit(
    design_id: int,
    service: CircuitService = Depends(get_circuit_service)
):
    """
    Re-run the simulation for a stored design (connectivity netlists are
    simulated from their CircuitIR with engineering models) and persist the
    result.
    """
    design = await service.get_design(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Circuit design not found")
    if not design.netlist:
        raise HTTPException(status_code=400, detail="该设计还没有网表，请先生成设计")

    try:
        return await service.rerun_simulation(design_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Simulation re-run failed for design {design_id}: {e}")
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/{design_id}/explain", summary="Generate circuit explanation")
async def explain_circuit(
    design_id: int,
    refresh: bool = False,
    service: CircuitService = Depends(get_circuit_service),
):
    """Generate a structured Chinese walkthrough (电路原理/连接关系/器件作用)
    of the completed design from its CircuitIR.

    The result is persisted on the design; subsequent calls return the cached
    explanation unless ``refresh=true``. When the AI narrative is unavailable
    the AI service returns a deterministic structural summary and marks it
    with ``source="rule"`` so the UI can disclose the downgrade.
    """
    try:
        return await service.generate_explanation(design_id, refresh=refresh)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Explanation generation failed for design {design_id}: {e}")
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{design_id}/status", response_model=DesignStatus, summary="Get generation status")
async def get_circuit_status(
    design_id: int,
    service: CircuitService = Depends(get_circuit_service)
):
    """Get circuit generation status"""
    status = await service.get_design_status(design_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status


@router.get("/{design_id}/raw-deepseek", summary="Get the raw DeepSeek response for a design")
async def get_raw_deepseek_response(
    design_id: int,
    service: CircuitService = Depends(get_circuit_service)
):
    """Return the raw upstream DeepSeek response and the system prompt used.

    This is a transparency/debug endpoint. It lets the UI show the user exactly
    what the model produced (after JSON parsing) plus the prompt that was sent.
    Returns 404 when DeepSeek was not used (rule-based fallback) so the UI can
    disable the "Show raw" button gracefully.
    """
    design = await service.get_design(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Circuit design not found")

    circuit_ir = design.circuit_ir or design.parsed_requirements or {}
    source = circuit_ir.get("source") or {}

    raw_response = source.get("raw_response")
    if not raw_response:
        raise HTTPException(
            status_code=404,
            detail="Raw DeepSeek response is not available for this design "
                   "(either DeepSeek was not used or the response was not retained).",
        )

    return {
        "design_id": design_id,
        "prompt_version": source.get("prompt_version"),
        "model": source.get("model"),
        "raw_message_text": source.get("raw_message_text"),
        "raw_response": raw_response,
        "raw_request": source.get("raw_request"),
        "validated_ir_summary": {
            "circuit_type": circuit_ir.get("circuit_type"),
            "supported": circuit_ir.get("supported"),
            "subsystem_count": len(circuit_ir.get("subsystems") or []),
            "component_count": len(circuit_ir.get("components") or []),
        },
    }


@router.get("/{design_id}/artifacts/{artifact_id}", summary="Download generated artifact")
async def download_artifact(
    design_id: int,
    artifact_id: str,
    service: CircuitService = Depends(get_circuit_service)
):
    """Download an artifact stored with a completed design."""
    design = await service.get_design(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Circuit design not found")

    artifacts = design.artifacts or {}
    artifact = artifacts.get(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    filename = artifact.get("filename", artifact_id)
    media_type = artifact.get("media_type", "application/octet-stream")
    content = artifact.get("content", "")
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)
