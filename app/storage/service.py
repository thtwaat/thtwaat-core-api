"""
app/storage/service.py

Business logic for the Storage module.
"""

import uuid
import mimetypes
from typing import Optional, List
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session

from app.storage.repository import StorageRepository
from app.storage.model import StorageFile, StorageProvider
from app.storage.providers.factory import get_storage_provider
from app.storage.config import storage_settings
from app.storage.local_paths import UnsafeLocalPathError, resolve_safe_local_path
from pathlib import Path
from fastapi.responses import FileResponse, RedirectResponse, Response



MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "image/svg+xml", "image/x-icon", "image/vnd.microsoft.icon",
    "application/pdf", "application/json", "text/plain", "text/csv",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class StorageService:
    def __init__(self, db: Session):
        self.repo = StorageRepository(db)
        self.provider = get_storage_provider()

    async def upload_file(
        self, 
        file: UploadFile, 
        company_id: Optional[uuid.UUID] = None, 
        user_id: Optional[uuid.UUID] = None
    ) -> StorageFile:
        # 1. Validation
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type: {file.content_type}"
            )
            
        # Optional: could check size here if file.size is populated, but often it's not trustworthy.
        # We'll rely on the server upload limit or read the size after saving.
        
        # 2. Secure Filename
        original_filename = file.filename or "unknown"
        ext = ""
        if "." in original_filename:
            ext = "." + original_filename.split(".")[-1].lower()
        else:
            # Try to guess from mimetype
            guessed = mimetypes.guess_extension(file.content_type)
            ext = guessed if guessed else ""
            
        storage_filename = f"{uuid.uuid4().hex}{ext}"
        
        # 3. Upload physical file
        try:
            # We must await file.read() internally in provider, so make sure cursor is 0
            await file.seek(0)
            storage_path = await self.provider.upload_file(file, storage_filename)
            
            size_bytes = file.size or 0
            if size_bytes > MAX_FILE_SIZE:
                # Clean up and reject
                await self.provider.delete_file(storage_path)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds maximum size of {MAX_FILE_SIZE // (1024*1024)}MB."
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file: {str(e)}"
            )

        # 4. Save metadata
        provider_enum_value = StorageProvider(storage_settings.STORAGE_PROVIDER.lower())
        
        db_file = self.repo.create({
            "company_id": company_id,
            "user_id": user_id,
            "original_filename": original_filename,
            "storage_filename": storage_filename,
            "mime_type": file.content_type,
            "extension": ext.lstrip("."),
            "size_bytes": size_bytes,
            "provider": provider_enum_value,
            "storage_path": storage_path
        })
        
        return db_file

    def get_file_metadata(self, file_id: uuid.UUID) -> StorageFile:
        db_file = self.repo.get_by_id(file_id)
        if not db_file:
            raise HTTPException(status_code=404, detail="File not found")
        return db_file

    def soft_delete_file(self, file_id: uuid.UUID) -> None:
        if not self.repo.soft_delete(file_id):
            raise HTTPException(status_code=404, detail="File not found")

    def get_download_url(self, file_id: uuid.UUID) -> str:
        db_file = self.get_file_metadata(file_id)
        return self.provider.get_file_url(db_file.storage_path)

    def download_file(self, file_id: uuid.UUID, company_id: uuid.UUID) -> Response:
        """
        Company-scoped download.

        Local files are streamed via FileResponse after path confinement checks.
        S3/MinIO continue to redirect to the provider URL (unchanged).
        """
        db_file = self.repo.get_by_id(file_id)
        if not db_file or db_file.company_id != company_id:
            # Identical 404 for missing and cross-tenant (no existence leak).
            raise HTTPException(status_code=404, detail="File not found")

        if db_file.provider == StorageProvider.LOCAL:
            try:
                path = resolve_safe_local_path(
                    base_dir=Path(storage_settings.LOCAL_STORAGE_DIR),
                    storage_filename=db_file.storage_filename,
                )
            except (UnsafeLocalPathError, FileNotFoundError, OSError):
                raise HTTPException(status_code=404, detail="File not found") from None

            return FileResponse(
                path=path,
                media_type=db_file.mime_type or "application/octet-stream",
                filename=db_file.original_filename,
            )

        url = self.provider.get_file_url(db_file.storage_path)
        return RedirectResponse(url=url)
