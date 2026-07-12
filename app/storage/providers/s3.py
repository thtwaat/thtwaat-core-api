"""
app/storage/providers/s3.py

AWS S3 implementation of the StorageProviderBase.
"""

from fastapi import UploadFile
from app.storage.providers.base import StorageProviderBase
from app.storage.config import storage_settings


class S3StorageProvider(StorageProviderBase):
    """
    Stub for AWS S3 storage provider.
    To be fully implemented in the future using boto3 and aiobotocore.
    """

    def __init__(self):
        # Configuration read from .env via storage_settings
        self.bucket_name = storage_settings.AWS_BUCKET_NAME
        self.region = storage_settings.AWS_REGION
        self.access_key = storage_settings.AWS_ACCESS_KEY_ID
        self.secret_key = storage_settings.AWS_SECRET_ACCESS_KEY

    async def upload_file(self, file: UploadFile, storage_filename: str) -> str:
        # Placeholder logic
        return f"s3://{self.bucket_name}/{storage_filename}"

    async def delete_file(self, storage_path: str) -> bool:
        # Placeholder logic
        return True

    def get_file_url(self, storage_path: str) -> str:
        # Extract filename from s3://bucket/filename
        filename = storage_path.split("/")[-1]
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{filename}"
