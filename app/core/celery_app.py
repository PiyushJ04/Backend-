"""
Celery application instance for the async pipeline (currently: sending
first-time credential emails without blocking the admin's HTTP request).

Run the worker with:
    celery -A app.core.celery_app.celery_app worker --loglevel=info
"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "app",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.email_tasks", "app.workers.evaluation_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_default_retry_delay=30,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
)
