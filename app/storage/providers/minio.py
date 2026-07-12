"""
app/storage/providers/minio.py

MinIO implementation of the StorageProviderBase.
"""

from fastapi import UploadFile
from app.storage.providers.base import StorageProviderBase
from app.storage.config import storage_settings


class MinIOStorageProvider(StorageProviderBase):
    """
    Stub for MinIO storage provider.
    """

    def __init__(self):
        self.endpoint = storage_settings.MINIO_ENDPOINT_URL
        self.bucket = storage_settings.MINIO_BUCKET_NAME
        self.access_key = storage_settings.MINIO_ACCESS_KEY
        self.secret_key = storage_settings.MINIO_SECRET_KEY

    async def upload_file(self, file: UploadFile, storage_filename: str) -> str:
        # Placeholder logic
        return f"minio://{self.bucket}/{storage_filename}"

    async def delete_file(self, storage_path: str) -> bool:
        # Placeholder logic
        return True

    def get_file_url(self, storage_path: str) -> str:
        filename = storage_path.split("/")[-1]
        return f"{self.endpoint}/{self.bucket}/{filename}"
