import logging

from fastapi import HTTPException, status

from app.auth.providers.base import BaseOTPProvider
from app.notifications.email.errors import EmailConfigurationError, EmailDeliveryError
from app.notifications.email.factory import get_email_backend
from app.notifications.email.templates import render_security_code_email

logger = logging.getLogger(__name__)


class EmailOTPProvider(BaseOTPProvider):
    """Delivers auth OTPs via the configured email backend (SMTP in production)."""

    def send_otp(self, recipient: str, code: str) -> bool:
        subject, html, text = render_security_code_email(code, purpose="otp")
        try:
            backend = get_email_backend()
            result = backend.send(
                recipient=recipient,
                subject=subject,
                body=text,
                html=html,
                text=text,
            )
        except EmailConfigurationError:
            logger.error("Email configuration error while sending OTP (details redacted)")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email delivery is not configured",
            ) from None
        except EmailDeliveryError:
            logger.error("Email delivery error while sending OTP (details redacted)")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email delivery failed",
            ) from None

        if not result.success:
            logger.error(
                "Email provider reported failure recipient=%s error=%s",
                recipient,
                result.error_message or "unknown",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=result.error_message or "Email delivery failed",
            )

        # Never log the OTP code.
        logger.info(
            "Auth email dispatched provider=%s recipient=%s",
            backend.provider_name,
            recipient,
        )
        return True
