import logging
from app.auth.providers.base import BaseOTPProvider

logger = logging.getLogger(__name__)

class SMSOTPProvider(BaseOTPProvider):
    """Stub implementation for SMS OTP delivery."""
    
    def send_otp(self, recipient: str, code: str) -> bool:
        # In a real implementation, this would use Twilio, MSG91, AWS SNS, etc.
        logger.info(f"[SMS Stub] Sending OTP {code} to {recipient}")
        return True
