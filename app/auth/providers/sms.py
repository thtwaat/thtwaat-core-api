import logging
from app.auth.providers.base import BaseOTPProvider

logger = logging.getLogger(__name__)

class SMSOTPProvider(BaseOTPProvider):
    """Stub implementation for SMS OTP delivery."""
    
    def send_otp(self, recipient: str, code: str) -> bool:
        # Never log the OTP code — it is a one-time secret.
        logger.info("[SMS Stub] OTP dispatched (code redacted) recipient=%s", recipient)
        return True
