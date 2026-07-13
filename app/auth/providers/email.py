import logging
from app.auth.providers.base import BaseOTPProvider

logger = logging.getLogger(__name__)

class EmailOTPProvider(BaseOTPProvider):
    """Stub implementation for Email OTP delivery."""
    
    def send_otp(self, recipient: str, code: str) -> bool:
        # In a real implementation, this would use SMTP, AWS SES, SendGrid, etc.
        logger.info(f"[Email Stub] Sending OTP {code} to {recipient}")
        return True
