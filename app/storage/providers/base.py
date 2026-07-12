"""
app/storage/providers/base.py

Abstract base class for storage providers.
"""

from abc import ABC, abstractmethod
from fastapi import UploadFile


class StorageProviderBase(ABC):
    """
    Abstract interface for all storage providers (Local, S3, MinIO).
    """

    @abstractmethod
    async def upload_file(self, file: UploadFile, storage_filename: str) -> str:
        """
        Uploads a file and returns the storage path/key.
        """
        pass

    @abstractmethod
    async def delete_file(self, storage_path: str) -> bool:
        """
        Deletes a file from storage. Returns True if successful.
        """
        pass

    @abstractmethod
    def get_file_url(self, storage_path: str) -> str:
        """
        Returns a public URL or local path for the file.
        """
        pass
