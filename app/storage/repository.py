"""
app/storage/repository.py

Repository for Storage models.
"""

import uuid
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.storage.model import StorageFile


class StorageRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, file_data: dict) -> StorageFile:
        db_file = StorageFile(**file_data)
        self.db.add(db_file)
        self.db.commit()
        self.db.refresh(db_file)
        return db_file

    def get_by_id(self, file_id: uuid.UUID, include_deleted: bool = False) -> Optional[StorageFile]:
        stmt = select(StorageFile).where(StorageFile.id == file_id)
        if not include_deleted:
            stmt = stmt.where(StorageFile.deleted_at.is_(None))
        
        return self.db.execute(stmt).scalar_one_or_none()
    
    def get_by_company(self, company_id: uuid.UUID) -> List[StorageFile]:
        stmt = select(StorageFile).where(
            StorageFile.company_id == company_id,
            StorageFile.deleted_at.is_(None)
        )
        return list(self.db.execute(stmt).scalars().all())

    def soft_delete(self, file_id: uuid.UUID) -> bool:
        db_file = self.get_by_id(file_id)
        if db_file:
            db_file.deleted_at = datetime.now(timezone.utc)
            self.db.commit()
            return True
        return False
