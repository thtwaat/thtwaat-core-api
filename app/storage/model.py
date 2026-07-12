"""
app/storage/model.py

SQLAlchemy ORM model for Storage items.
"""

import uuid
import enum
from sqlalchemy import Column, String, Integer, Enum as SAEnum, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin


class StorageProvider(str, enum.Enum):
    LOCAL = "local"
    S3 = "s3"
    MINIO = "minio"


class StorageFile(Base, TimestampMixin):
    """
    Represents a file uploaded to the system.
    """

    __tablename__ = "storage_files"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        nullable=False,
    )
    
    # Nullable ownership to allow system-level files vs company-level files
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    original_filename = Column(String(255), nullable=False)
    storage_filename = Column(String(255), unique=True, index=True, nullable=False)
    mime_type = Column(String(100), nullable=False)
    extension = Column(String(20), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    
    provider = Column(
        SAEnum(StorageProvider, name="storage_provider_enum"),
        default=StorageProvider.LOCAL,
        nullable=False,
    )
    storage_path = Column(String(1024), nullable=False)
    
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<StorageFile id={self.id} filename={self.original_filename!r}>"
