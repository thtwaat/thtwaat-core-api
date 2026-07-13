from abc import ABC, abstractmethod

class BaseOTPProvider(ABC):
    """Abstract base class for OTP providers."""
    
    @abstractmethod
    def send_otp(self, recipient: str, code: str) -> bool:
        """
        Send the OTP to the recipient.
        
        Args:
            recipient: Email or phone number.
            code: The 6-digit OTP code.
            
        Returns:
            bool: True if sent successfully, False otherwise.
        """
        pass
