from app.auth.providers.base import BaseOTPProvider
from app.auth.providers.email import EmailOTPProvider
from app.auth.providers.sms import SMSOTPProvider

class OTPProviderFactory:
    """Factory to return the appropriate OTP provider."""
    
    @staticmethod
    def get_provider(channel: str) -> BaseOTPProvider:
        """
        Returns the provider for the specified channel ('email' or 'phone').
        """
        if channel == "email":
            return EmailOTPProvider()
        elif channel == "phone":
            return SMSOTPProvider()
        else:
            raise ValueError(f"Unknown OTP channel: {channel}")
