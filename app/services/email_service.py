"""
Actual SMTP send. Kept synchronous and dependency-free (stdlib smtplib)
so it can run inside a Celery worker process without pulling in an async
mail library. Called only from app.workers.email_tasks, never from a
request handler directly (that would block the HTTP response).
"""
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger("app.email")


def _send(message: EmailMessage) -> None:
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)


def send_first_time_credentials_email(to_email: str, username: str, temp_password: str, role: str) -> None:
    login_url = f"{settings.frontend_base_url}/login"
    role_label = role.replace("_", " ").title()

    message = EmailMessage()
    message["Subject"] = "Your account has been created"
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = to_email

    message.set_content(
        f"Hello,\n\n"
        f"An administrator has created a {role_label} account for you.\n\n"
        f"Username: {username}\n"
        f"Temporary password: {temp_password}\n\n"
        f"Please sign in at {login_url} and you will be asked to set a new "
        f"password before you can continue.\n\n"
        f"If you were not expecting this account, please contact the admin.\n"
    )
    message.add_alternative(
        f"""\
<html>
  <body style="font-family: sans-serif; line-height: 1.5;">
    <p>Hello,</p>
    <p>An administrator has created a <strong>{role_label}</strong> account for you.</p>
    <table cellpadding="6" style="border-collapse: collapse;">
      <tr><td><strong>Username</strong></td><td>{username}</td></tr>
      <tr><td><strong>Temporary password</strong></td><td><code>{temp_password}</code></td></tr>
    </table>
    <p>
      Please <a href="{login_url}">sign in here</a>. You will be required to
      set a new password before you can do anything else.
    </p>
    <p>If you were not expecting this account, please contact the admin.</p>
  </body>
</html>
""",
        subtype="html",
    )

    if settings.environment == "development" and not settings.smtp_username:
        # No real SMTP configured locally - log instead of failing the pipeline.
        logger.info(
            "[DEV EMAIL - not actually sent] to=%s username=%s temp_password=%s role=%s",
            to_email, username, temp_password, role,
        )
        return

    _send(message)
