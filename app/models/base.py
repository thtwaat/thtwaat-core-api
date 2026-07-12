from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, DateTime, func

class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.
    All models in the project must inherit from this class.
    Uses SQLAlchemy 2.0 style DeclarativeBase.
    """
    pass


class TimestampMixin:
    """
    Mixin to add created_at and updated_at timestamps
    to any model that needs auditing.
    """
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
