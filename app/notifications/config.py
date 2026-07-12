"""
app/notifications/config.py

Configuration for Notifications module.
"""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class NotificationsSettings(BaseSettings):
    EMAIL_PROVIDER: str = "stub"
    SMS_PROVIDER: str = "stub"
    WHATSAPP_PROVIDER: str = "stub"
    PUSH_PROVIDER: str = "stub"
    
    # Provider API keys would go here, e.g. SENDGRID_API_KEY
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

notifications_settings = NotificationsSettings()
