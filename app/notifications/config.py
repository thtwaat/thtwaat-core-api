"""
app/notifications/config.py

Configuration for Notifications module.
"""
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NotificationsSettings(BaseSettings):
    # smtp | stub | sendgrid | ses | resend
    EMAIL_PROVIDER: str = "stub"
    SMS_PROVIDER: str = "stub"
    WHATSAPP_PROVIDER: str = "stub"
    PUSH_PROVIDER: str = "stub"

    # SMTP (default production email transport)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = Field(default=None, validation_alias="SMTP_USERNAME")
    # Backward-compatible alias used in older .env.prod.example files
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    SMTP_FROM_NAME: Optional[str] = "THTWAAT"
    SMTP_USE_TLS: bool = True
    SMTP_TIMEOUT_SECONDS: float = 30.0

    # Future providers
    SENDGRID_API_KEY: Optional[str] = None
    AWS_SES_REGION: Optional[str] = None
    RESEND_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def smtp_username(self) -> Optional[str]:
        return (self.SMTP_USERNAME or self.SMTP_USER or None)


notifications_settings = NotificationsSettings()
