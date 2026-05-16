"""Celery app singleton."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "mureka_studio",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.poll_task",
        "app.workers.cleanup_task",
    ],
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
    task_default_queue="generation:normal",
    task_routes={
        "app.workers.poll_task.run_generation": {"queue": "generation:normal"},
        "app.workers.cleanup_task.cleanup_expired_files": {"queue": "cleanup:cron"},
    },
    beat_schedule={
        "cleanup-expired-files": {
            "task": "app.workers.cleanup_task.cleanup_expired_files",
            "schedule": crontab(hour="*/6", minute="0"),
        },
    },
)
