"""
Celery tasks for background processing
"""
import logging
from datetime import datetime, timedelta
from celery import shared_task
from sqlalchemy.orm import Session

from app.worker.celery_app import celery_app
from models import CircuitDesign, SessionLocal
from app.services.circuit_service import CircuitService

logger = logging.getLogger(__name__)


@shared_task(name="app.worker.tasks.generate_circuit_task")
def generate_circuit_task(design_id: int):
    """
    Generate circuit design in background

    Args:
        design_id: Circuit design ID
    """
    logger.info(f"Starting background circuit generation for design {design_id}")

    db = SessionLocal()
    try:
        service = CircuitService(db)

        # Create progress callback for Celery
        def update_progress(design_id: int, message: str, progress: int, error: bool = False):
            """Update task progress"""
            logger.info(f"Design {design_id}: {message} ({progress}%)")

            # Update task metadata
            if error:
                generate_circuit_task.update_state(
                    state="FAILURE",
                    meta={"design_id": design_id, "error": message}
                )
            else:
                generate_circuit_task.update_state(
                    state="PROGRESS",
                    meta={
                        "design_id": design_id,
                        "message": message,
                        "progress": progress
                    }
                )

        # Run generation
        result = service.generate_circuit(design_id, progress_callback=update_progress)

        logger.info(f"✓ Background circuit generation complete for design {design_id}")
        return result

    except Exception as e:
        logger.error(f"✗ Error in background circuit generation for design {design_id}: {e}")
        raise
    finally:
        db.close()


@shared_task(name="app.worker.tasks.cleanup_old_designs")
def cleanup_old_designs():
    """
    Cleanup old completed designs (older than 30 days)
    """
    logger.info("Starting cleanup of old designs")

    db = SessionLocal()
    try:
        # Find designs older than 30 days
        cutoff_date = datetime.utcnow() - timedelta(days=30)

        old_designs = db.query(CircuitDesign).filter(
            CircuitDesign.status == "completed",
            CircuitDesign.completed_at < cutoff_date
        ).all()

        count = len(old_designs)
        for design in old_designs:
            logger.info(f"Deleting old design {design.id}")
            db.delete(design)

        db.commit()
        logger.info(f"✓ Cleaned up {count} old designs")

        return {"cleaned": count}

    except Exception as e:
        logger.error(f"✗ Error cleaning up old designs: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@shared_task(name="app.worker.tasks.update_design_progress")
def update_design_progress(design_id: int, message: str, progress: int):
    """
    Update design progress (called from frontend polling)

    Args:
        design_id: Design ID
        message: Progress message
        progress: Progress percentage (0-100)
    """
    logger.info(f"Design {design_id} progress: {message} ({progress}%)")

    db = SessionLocal()
    try:
        design = db.query(CircuitDesign).filter(CircuitDesign.id == design_id).first()
        if design:
            # Store progress in a custom field or send via WebSocket
            # For now, just log it
            pass
    finally:
        db.close()
