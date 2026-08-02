"""SMTP email backend (default production provider)."""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional

from app.notifications.config import notifications_settings
from app.notifications.email.base import EmailBackend
from app.notifications.email.errors import EmailConfigurationError
from app.notifications.providers.base import NotificationResult

logger = logging.getLogger(__name__)


def smtp_is_configured() -> bool:
    host = (notifications_settings.SMTP_HOST or "").strip()
    from_addr = (notifications_settings.SMTP_FROM or "").strip()
    return bool(host and from_addr)


class SMTPEmailProvider(EmailBackend):
    @property
    def provider_name(self) -> str:
        return "smtp"

    def send(
        self,
        recipient: str,
        subject: Optional[str],
        body: str,
        *,
        html: Optional[str] = None,
        text: Optional[str] = None,
    ) -> NotificationResult:
        if not smtp_is_configured():
            raise EmailConfigurationError(
                "SMTP is not configured (SMTP_HOST and SMTP_FROM are required)"
            )

        text_body = text if text is not None else body
        html_body = html

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject or "Notification"
        msg["From"] = formataddr(
            (
                notifications_settings.SMTP_FROM_NAME or "THTWAAT",
                notifications_settings.SMTP_FROM.strip(),
            )
        )
        msg["To"] = recipient
        msg.attach(MIMEText(text_body or "", "plain", "utf-8"))
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))

        host = notifications_settings.SMTP_HOST.strip()
        port = int(notifications_settings.SMTP_PORT or 587)
        username = notifications_settings.smtp_username
        password = notifications_settings.SMTP_PASSWORD or None
        use_tls = bool(notifications_settings.SMTP_USE_TLS)
        timeout = float(notifications_settings.SMTP_TIMEOUT_SECONDS or 30)

        try:
            if use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(host, port, timeout=timeout) as server:
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                    if username:
                        server.login(username, password or "")
                    server.sendmail(notifications_settings.SMTP_FROM.strip(), [recipient], msg.as_string())
            else:
                with smtplib.SMTP(host, port, timeout=timeout) as server:
                    if username:
                        server.login(username, password or "")
                    server.sendmail(notifications_settings.SMTP_FROM.strip(), [recipient], msg.as_string())
        except smtplib.SMTPAuthenticationError as exc:
            logger.error("SMTP authentication failed (credentials redacted)")
            return NotificationResult(success=False, error_message="SMTP authentication failed")
        except (TimeoutError, smtplib.SMTPServerDisconnected, OSError) as exc:
            logger.error("SMTP connection/timeout error type=%s", type(exc).__name__)
            return NotificationResult(success=False, error_message="SMTP connection timed out or was reset")
        except smtplib.SMTPException as exc:
            logger.error("SMTP send failed type=%s", type(exc).__name__)
            return NotificationResult(success=False, error_message="SMTP send failed")

        logger.info("SMTP email accepted by server recipient=%s", recipient)
        return NotificationResult(success=True)
