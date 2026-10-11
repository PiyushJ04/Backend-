"""
Celery tasks - the async half of the "admin creates a user -> user gets
an email" pipeline. Kept as thin wrappers around app.services.email_service
so retry/backoff policy lives here, not in the service.
"""
import logging

from app.core.celery_app import celery_app
from app.services.email_service import send_first_time_credentials_email

logger = logging.getLogger("app.workers.email")


@celery_app.task(
    name="app.workers.email_tasks.send_credentials_email_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def send_credentials_email_task(self, to_email: str, username: str, temp_password: str, role: str) -> None:
    try:
        send_first_time_credentials_email(to_email, username, temp_password, role)
    except Exception as exc: 
        logger.warning("Credential email to %s failed (attempt %s): %s", to_email, self.request.retries + 1, exc)
        raise self.retry(exc=exc)
