from celery import Celery

from app.core.config import settings

# Create Celery application instance
celery_app = Celery(
    "procurement_platform",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.ai_tasks"]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Summarisation is best-effort. When Redis is unavailable, .delay() must
    # fail fast instead of blocking RFQ/bid creation through ~20 reconnects.
    broker_connection_retry_on_startup=False,
    task_publish_retry=False,
    result_backend_transport_options={
        "retry_policy": {
            "max_retries": 1,
            "interval_start": 0,
            "interval_step": 0.2,
            "interval_max": 0.5,
        }
    },
)
