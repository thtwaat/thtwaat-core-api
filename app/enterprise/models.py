"""Tenant-isolated enterprise administration ORM models."""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID

from app.models.base import Base, TimestampMixin


class UnitType(str, enum.Enum):
    ORGANIZATION = "organization"
    BUSINESS_UNIT = "business_unit"
    DEPARTMENT = "department"
    TEAM = "team"


class InvitationStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class SSOProvider(str, enum.Enum):
    OIDC = "oidc"
    SAML = "saml"
    GOOGLE_WORKSPACE = "google_workspace"
    MICROSOFT_ENTRA = "microsoft_entra"


class AuditSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ExportStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class EnterpriseUnit(Base, TimestampMixin):
    __tablename__ = "enterprise_units"
    __table_args__ = (
        UniqueConstraint("company_id", "parent_id", "slug", name="uq_enterprise_unit_path"),
        Index("ix_enterprise_units_company_type", "company_id", "unit_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id = Column(
        UUID(as_uuid=True), ForeignKey("enterprise_units.id", ondelete="CASCADE"), nullable=True
    )
    unit_type = Column(
        SAEnum(UnitType, name="enterprise_unit_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    manager_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    cost_center = Column(String(100), nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)


class EnterpriseUnitMembership(Base, TimestampMixin):
    __tablename__ = "enterprise_unit_memberships"
    __table_args__ = (
        UniqueConstraint("unit_id", "user_id", name="uq_enterprise_unit_member"),
        Index("ix_enterprise_membership_company_user", "company_id", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_id = Column(
        UUID(as_uuid=True), ForeignKey("enterprise_units.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False)


class EnterpriseInvitation(Base, TimestampMixin):
    __tablename__ = "enterprise_invitations"
    __table_args__ = (
        Index("ix_enterprise_invites_company_email", "company_id", "email"),
        Index("ix_enterprise_invites_token_hash", "token_hash", unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    builtin_role = Column(String(64), nullable=False, default="employee")
    custom_role_id = Column(
        UUID(as_uuid=True), ForeignKey("enterprise_custom_roles.id", ondelete="SET NULL"), nullable=True
    )
    unit_ids = Column(JSONB, nullable=False, default=list)
    token_hash = Column(String(64), nullable=False)
    status = Column(
        SAEnum(
            InvitationStatus,
            name="enterprise_invitation_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=InvitationStatus.PENDING,
    )
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)


class EnterprisePermissionGroup(Base, TimestampMixin):
    __tablename__ = "enterprise_permission_groups"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_enterprise_permission_group_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    permissions = Column(JSONB, nullable=False, default=list)
    is_system = Column(Boolean, nullable=False, default=False)


class EnterpriseCustomRole(Base, TimestampMixin):
    __tablename__ = "enterprise_custom_roles"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_enterprise_custom_role_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    template_key = Column(String(64), nullable=True)
    permissions = Column(JSONB, nullable=False, default=list)
    permission_group_ids = Column(JSONB, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)


class EnterpriseRoleAssignment(Base, TimestampMixin):
    __tablename__ = "enterprise_role_assignments"
    __table_args__ = (
        UniqueConstraint("company_id", "user_id", "role_id", "unit_id", name="uq_enterprise_role_scope"),
        Index("ix_enterprise_role_assignment_user", "company_id", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(
        UUID(as_uuid=True), ForeignKey("enterprise_custom_roles.id", ondelete="CASCADE"), nullable=False
    )
    unit_id = Column(
        UUID(as_uuid=True), ForeignKey("enterprise_units.id", ondelete="CASCADE"), nullable=True
    )
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class EnterpriseSSOConnection(Base, TimestampMixin):
    __tablename__ = "enterprise_sso_connections"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_enterprise_sso_name"),
        Index("ix_enterprise_sso_domain", "company_id", "domain"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(100), nullable=False)
    provider = Column(
        SAEnum(SSOProvider, name="enterprise_sso_provider_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    domain = Column(String(253), nullable=False)
    issuer = Column(String(1024), nullable=True)
    client_id = Column(String(512), nullable=True)
    encrypted_client_secret = Column(Text, nullable=True)
    authorization_endpoint = Column(String(1024), nullable=True)
    token_endpoint = Column(String(1024), nullable=True)
    jwks_uri = Column(String(1024), nullable=True)
    metadata_url = Column(String(1024), nullable=True)
    entity_id = Column(String(1024), nullable=True)
    sso_url = Column(String(1024), nullable=True)
    certificate = Column(Text, nullable=True)
    scopes = Column(JSONB, nullable=False, default=lambda: ["openid", "profile", "email"])
    allowed_redirect_uris = Column(JSONB, nullable=False, default=list)
    attribute_mapping = Column(JSONB, nullable=False, default=dict)
    enforce_sso = Column(Boolean, nullable=False, default=False)
    jit_provisioning = Column(Boolean, nullable=False, default=True)
    default_role = Column(String(64), nullable=False, default="employee")
    is_active = Column(Boolean, nullable=False, default=True)


class EnterpriseSecurityPolicy(Base, TimestampMixin):
    __tablename__ = "enterprise_security_policies"
    __table_args__ = (UniqueConstraint("company_id", name="uq_enterprise_security_policy_company"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    require_mfa = Column(Boolean, nullable=False, default=False)
    session_ttl_minutes = Column(Integer, nullable=False, default=480)
    idle_timeout_minutes = Column(Integer, nullable=False, default=60)
    max_sessions_per_user = Column(Integer, nullable=False, default=10)
    ip_allow_list = Column(JSONB, nullable=False, default=list)
    trusted_device_days = Column(Integer, nullable=False, default=30)
    api_policies = Column(JSONB, nullable=False, default=dict)
    password_policy = Column(JSONB, nullable=False, default=dict)


class EnterpriseTrustedDevice(Base, TimestampMixin):
    __tablename__ = "enterprise_trusted_devices"
    __table_args__ = (
        UniqueConstraint("user_id", "fingerprint_hash", name="uq_enterprise_trusted_device"),
        Index("ix_enterprise_trusted_devices_company_user", "company_id", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=True)
    fingerprint_hash = Column(String(64), nullable=False)
    last_ip = Column(INET, nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class EnterpriseAuditLog(Base):
    __tablename__ = "enterprise_audit_logs"
    __table_args__ = (
        Index("ix_enterprise_audit_company_created", "company_id", "created_at"),
        Index("ix_enterprise_audit_actor", "company_id", "actor_user_id"),
        Index("ix_enterprise_audit_action", "company_id", "action"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(128), nullable=False)
    resource_type = Column(String(128), nullable=False)
    resource_id = Column(String(255), nullable=True)
    severity = Column(
        SAEnum(AuditSeverity, name="enterprise_audit_severity_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AuditSeverity.INFO,
    )
    ip_address = Column(INET, nullable=True)
    user_agent = Column(String(1024), nullable=True)
    request_id = Column(String(128), nullable=True)
    before = Column(JSONB, nullable=True)
    after = Column(JSONB, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)


class EnterpriseRetentionPolicy(Base, TimestampMixin):
    __tablename__ = "enterprise_retention_policies"
    __table_args__ = (
        UniqueConstraint("company_id", "data_type", name="uq_enterprise_retention_data_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_type = Column(String(100), nullable=False)
    retention_days = Column(Integer, nullable=False)
    legal_hold = Column(Boolean, nullable=False, default=False)
    auto_delete = Column(Boolean, nullable=False, default=False)
    anonymize = Column(Boolean, nullable=False, default=False)


class EnterpriseConsentLog(Base):
    __tablename__ = "enterprise_consent_logs"
    __table_args__ = (
        Index("ix_enterprise_consent_company_subject", "company_id", "subject_id"),
        Index("ix_enterprise_consent_company_created", "company_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id = Column(String(255), nullable=False)
    purpose = Column(String(255), nullable=False)
    granted = Column(Boolean, nullable=False)
    policy_version = Column(String(64), nullable=False)
    source = Column(String(100), nullable=True)
    ip_address = Column(INET, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False)


class EnterpriseExportJob(Base, TimestampMixin):
    __tablename__ = "enterprise_export_jobs"
    __table_args__ = (Index("ix_enterprise_exports_company_created", "company_id", "created_at"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    export_type = Column(String(64), nullable=False)
    format = Column(String(16), nullable=False, default="csv")
    filters = Column(JSONB, nullable=False, default=dict)
    status = Column(
        SAEnum(ExportStatus, name="enterprise_export_status_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ExportStatus.PENDING,
    )
    storage_file_id = Column(
        UUID(as_uuid=True), ForeignKey("storage_files.id", ondelete="SET NULL"), nullable=True
    )
    download_url = Column(String(1024), nullable=True)
    row_count = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
