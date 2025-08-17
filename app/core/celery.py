from celery import Celery
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Create Celery instance
celery_app = Celery(
    "clinic_crm",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.services.notification_service",
        "app.services.email_service", 
        "app.services.sms_service"
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    task_routes={
        "app.services.notification_service.*": {"queue": "notifications"},
        "app.services.email_service.*": {"queue": "emails"},
        "app.services.sms_service.*": {"queue": "sms"},
    },
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
)

@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    logger.info(f"Request: {self.request!r}")
    return f"Hello from Celery! Request: {self.request!r}"