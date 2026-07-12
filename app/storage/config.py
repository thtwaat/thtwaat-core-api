"""
app/storage/config.py

Configuration for the Storage module loaded from .env.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageSettings(BaseSettings):
    """
    Storage-specific settings. 
    Reads from .env so no credentials are hardcoded.
    """
    STORAGE_PROVIDER: str = "local"
    LOCAL_STORAGE_DIR: str = "data/uploads"
    
    # AWS S3 Settings
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: Optional[str] = None
    AWS_BUCKET_NAME: Optional[str] = None
    
    # MinIO Settings
    MINIO_ENDPOINT_URL: Optional[str] = None
    MINIO_ACCESS_KEY: Optional[str] = None
    MINIO_SECRET_KEY: Optional[str] = None
    MINIO_BUCKET_NAME: Optional[str] = None
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

storage_settings = StorageSettings()
