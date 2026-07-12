"""
app/storage/providers/local.py

Local disk implementation of the StorageProviderBase.
"""

import os
from pathlib import Path
import aiofiles
from fastapi import UploadFile

from app.storage.providers.base import StorageProviderBase
from app.storage.config import storage_settings


class LocalStorageProvider(StorageProviderBase):
    """
    Fully functional local storage provider.
    Saves files to the local disk directory defined in LOCAL_STORAGE_DIR.
    """

    def __init__(self):
        self.base_dir = Path(storage_settings.LOCAL_STORAGE_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def upload_file(self, file: UploadFile, storage_filename: str) -> str:
        file_path = self.base_dir / storage_filename
        
        # Read/write in async chunks
        async with aiofiles.open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024): # 1MB chunks
                await buffer.write(chunk)
            
        return str(file_path.as_posix())

    async def delete_file(self, storage_path: str) -> bool:
        path = Path(storage_path)
        if path.exists() and path.is_file():
            path.unlink()
            return True
        return False

    def get_file_url(self, storage_path: str) -> str:
        # In a real app, this would be a URL pointing to a static file server route.
        # Here we return a relative URL path to be served by the FastAPI download endpoint.
        return f"/api/v1/storage/download?path={storage_path}"
