"""Ops persistence: alerts, deployment history, admin activity."""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base, TimestampMixin


class AlertSeverity(str, enum.Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class DeploymentAction(str, enum.Enum):
    BACKUP = "backup"
    NGINX_RELOAD = "nginx_reload"
    CONTAINER_RESTART = "container_restart"
    SSL_RENEW = "ssl_renew"
    JOB_ENQUEUE = "job_enqueue"
    JOB_RETRY = "job_retry"
    JOB_CANCEL = "job_cancel"
    PUBLISH = "publish"
    OTHER = "other"


class OpsAlert(Base, TimestampMixin):
    __tablename__ = "ops_alerts"
    __table_args__ = (
        Index("ix_ops_alerts_status_severity", "status", "severity"),
        Index("ix_ops_alerts_source", "source"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    severity = Column(
        SAEnum(
            AlertSeverity,
            name="ops_alert_severity_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AlertSeverity.WARNING,
    )
    status = Column(
        SAEnum(
            AlertStatus,
            name="ops_alert_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AlertStatus.OPEN,
    )
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    source = Column(String(100), nullable=False, default="system")
    metric = Column(String(100), nullable=True)
    fingerprint = Column(String(64), nullable=False, index=True)
    details = Column(JSONB, nullable=False, default=dict)
    notified_channels = Column(JSONB, nullable=False, default=list)

    acknowledged_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )


class OpsDeploymentEvent(Base, TimestampMixin):
    """Persisted operational / deployment history (not a second Prometheus series)."""

    __tablename__ = "ops_deployment_events"
    __table_args__ = (Index("ix_ops_deployment_events_action", "action"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action = Column(
        SAEnum(
            DeploymentAction,
            name="ops_deployment_action_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    status = Column(String(50), nullable=False, default="success")
    actor_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    target = Column(String(255), nullable=True)
    message = Column(Text, nullable=True)
    details = Column(JSONB, nullable=False, default=dict)


class OpsAdminActivity(Base, TimestampMixin):
    """Platform-admin activity timeline (complements enterprise audit logs)."""

    __tablename__ = "ops_admin_activities"
    __table_args__ = (Index("ix_ops_admin_activities_category", "category"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    category = Column(String(50), nullable=False)  # admin | operations | security | monitoring
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(100), nullable=True)
    ip_address = Column(String(64), nullable=True)
    details = Column(JSONB, nullable=False, default=dict)
