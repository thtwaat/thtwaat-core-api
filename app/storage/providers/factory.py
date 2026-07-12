"""
app/storage/providers/factory.py

Factory to instantiate the correct storage provider based on configuration.
"""

from app.storage.config import storage_settings
from app.storage.model import StorageProvider
from app.storage.providers.base import StorageProviderBase
from app.storage.providers.local import LocalStorageProvider
from app.storage.providers.s3 import S3StorageProvider
from app.storage.providers.minio import MinIOStorageProvider


def get_storage_provider() -> StorageProviderBase:
    """
    Returns an instance of the configured StorageProviderBase.
    """
    provider_str = storage_settings.STORAGE_PROVIDER.lower()
    
    if provider_str == StorageProvider.S3.value:
        return S3StorageProvider()
    elif provider_str == StorageProvider.MINIO.value:
        return MinIOStorageProvider()
    
    # Default to local
    return LocalStorageProvider()
