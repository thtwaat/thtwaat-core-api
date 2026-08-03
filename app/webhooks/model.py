from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timezone
from app.models.base import Base, TimestampMixin

class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    url = Column(String(2048), nullable=False)
    event_types = Column(JSONB, default=list, nullable=False)
    secret = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    company = relationship("Company", backref="webhooks")

    def __repr__(self):
        return f"<Webhook {self.url} ({self.id})>"


# Status machine (Day 1 writes pending → queued; Day 2+ delivered/dead)
WEBHOOK_DELIVERY_PENDING = "pending"
WEBHOOK_DELIVERY_QUEUED = "queued"
WEBHOOK_DELIVERY_DELIVERED = "delivered"
WEBHOOK_DELIVERY_FAILED = "failed"
WEBHOOK_DELIVERY_DEAD = "dead"


class WebhookDelivery(Base, TimestampMixin):
    """Durable outbox row for webhook.dispatch (Week 4 Day 1).

    Redis remains the hot path; this table survives Redis loss and enables redrive.
    Secrets are intentionally not stored — reload from ``webhooks`` on redrive.
    """

    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    delivery_id = Column(String(64), nullable=False, unique=True, index=True)
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    webhook_id = Column(
        UUID(as_uuid=True),
        ForeignKey("webhooks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event = Column(String(128), nullable=False, index=True)
    url = Column(String(2048), nullable=False)
    payload = Column(JSONB, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default=WEBHOOK_DELIVERY_PENDING, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<WebhookDelivery {self.delivery_id} status={self.status}>"
