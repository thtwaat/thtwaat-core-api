import logging
from app.auth.providers.base import BaseOTPProvider

logger = logging.getLogger(__name__)

class EmailOTPProvider(BaseOTPProvider):
    """Stub implementation for Email OTP delivery."""
    
    def send_otp(self, recipient: str, code: str) -> bool:
        # Never log the OTP code — it is a one-time secret.
        logger.info("[Email Stub] OTP dispatched (code redacted) recipient=%s", recipient)
        return True
