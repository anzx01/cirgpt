"""
Celery application setup for background tasks
"""
from celery import Celery
from app.config import settings

# Create Celery app
celery_app = Celery(
    "circuit_design_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3000,  # 50 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50
)

# Celery beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "cleanup-old-designs": {
        "task": "app.worker.tasks.cleanup_old_designs",
        "schedule": 3600.0,  # Run every hour
    },
}
