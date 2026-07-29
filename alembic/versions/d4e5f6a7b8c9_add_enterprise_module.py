"""add enterprise administration module

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None

unit_type = sa.Enum(
    "organization", "business_unit", "department", "team",
    name="enterprise_unit_type_enum", create_type=False,
)
invitation_status = sa.Enum(
    "pending", "accepted", "expired", "revoked",
    name="enterprise_invitation_status_enum", create_type=False,
)
sso_provider = sa.Enum(
    "oidc", "saml", "google_workspace", "microsoft_entra",
    name="enterprise_sso_provider_enum", create_type=False,
)
audit_severity = sa.Enum(
    "info", "warning", "critical",
    name="enterprise_audit_severity_enum", create_type=False,
)
export_status = sa.Enum(
    "pending", "processing", "completed", "failed",
    name="enterprise_export_status_enum", create_type=False,
)


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (unit_type, invitation_status, sso_provider, audit_severity, export_status):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "enterprise_units",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enterprise_units.id", ondelete="CASCADE")),
        sa.Column("unit_type", unit_type, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("manager_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("cost_center", sa.String(100)),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.UniqueConstraint("company_id", "parent_id", "slug", name="uq_enterprise_unit_path"),
    )
    op.create_index("ix_enterprise_units_company_id", "enterprise_units", ["company_id"])
    op.create_index("ix_enterprise_units_company_type", "enterprise_units", ["company_id", "unit_type"])

    op.create_table(
        "enterprise_permission_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("permissions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_timestamps(),
        sa.UniqueConstraint("company_id", "name", name="uq_enterprise_permission_group_name"),
    )
    op.create_index("ix_enterprise_permission_groups_company_id", "enterprise_permission_groups", ["company_id"])

    op.create_table(
        "enterprise_custom_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("template_key", sa.String(64)),
        sa.Column("permissions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("permission_group_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.UniqueConstraint("company_id", "name", name="uq_enterprise_custom_role_name"),
    )
    op.create_index("ix_enterprise_custom_roles_company_id", "enterprise_custom_roles", ["company_id"])

    op.create_table(
        "enterprise_unit_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enterprise_units.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255)),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_timestamps(),
        sa.UniqueConstraint("unit_id", "user_id", name="uq_enterprise_unit_member"),
    )
    op.create_index("ix_enterprise_membership_company_user", "enterprise_unit_memberships", ["company_id", "user_id"])

    op.create_table(
        "enterprise_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("builtin_role", sa.String(64), nullable=False, server_default="employee"),
        sa.Column("custom_role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enterprise_custom_roles.id", ondelete="SET NULL")),
        sa.Column("unit_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("status", invitation_status, nullable=False, server_default="pending"),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_enterprise_invites_company_email", "enterprise_invitations", ["company_id", "email"])
    op.create_index("ix_enterprise_invites_token_hash", "enterprise_invitations", ["token_hash"], unique=True)

    op.create_table(
        "enterprise_role_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enterprise_custom_roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("enterprise_units.id", ondelete="CASCADE")),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_timestamps(),
        sa.UniqueConstraint("company_id", "user_id", "role_id", "unit_id", name="uq_enterprise_role_scope"),
    )
    op.create_index("ix_enterprise_role_assignment_user", "enterprise_role_assignments", ["company_id", "user_id"])

    op.create_table(
        "enterprise_sso_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("provider", sso_provider, nullable=False),
        sa.Column("domain", sa.String(253), nullable=False),
        sa.Column("issuer", sa.String(1024)),
        sa.Column("client_id", sa.String(512)),
        sa.Column("encrypted_client_secret", sa.Text()),
        sa.Column("authorization_endpoint", sa.String(1024)),
        sa.Column("token_endpoint", sa.String(1024)),
        sa.Column("jwks_uri", sa.String(1024)),
        sa.Column("metadata_url", sa.String(1024)),
        sa.Column("entity_id", sa.String(1024)),
        sa.Column("sso_url", sa.String(1024)),
        sa.Column("certificate", sa.Text()),
        sa.Column("scopes", postgresql.JSONB(), nullable=False, server_default=sa.text("'[\"openid\",\"profile\",\"email\"]'::jsonb")),
        sa.Column("allowed_redirect_uris", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("attribute_mapping", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("enforce_sso", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("jit_provisioning", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("default_role", sa.String(64), nullable=False, server_default="employee"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.UniqueConstraint("company_id", "name", name="uq_enterprise_sso_name"),
    )
    op.create_index("ix_enterprise_sso_domain", "enterprise_sso_connections", ["company_id", "domain"])

    op.create_table(
        "enterprise_security_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("require_mfa", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("session_ttl_minutes", sa.Integer(), nullable=False, server_default="480"),
        sa.Column("idle_timeout_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("max_sessions_per_user", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("ip_allow_list", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("trusted_device_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("api_policies", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("password_policy", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
        sa.UniqueConstraint("company_id", name="uq_enterprise_security_policy_company"),
    )
    op.create_index("ix_enterprise_security_policies_company_id", "enterprise_security_policies", ["company_id"])

    op.create_table(
        "enterprise_trusted_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255)),
        sa.Column("fingerprint_hash", sa.String(64), nullable=False),
        sa.Column("last_ip", postgresql.INET()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "fingerprint_hash", name="uq_enterprise_trusted_device"),
    )
    op.create_index("ix_enterprise_trusted_devices_company_user", "enterprise_trusted_devices", ["company_id", "user_id"])

    op.create_table(
        "enterprise_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(128), nullable=False),
        sa.Column("resource_id", sa.String(255)),
        sa.Column("severity", audit_severity, nullable=False, server_default="info"),
        sa.Column("ip_address", postgresql.INET()),
        sa.Column("user_agent", sa.String(1024)),
        sa.Column("request_id", sa.String(128)),
        sa.Column("before", postgresql.JSONB()),
        sa.Column("after", postgresql.JSONB()),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_enterprise_audit_company_created", "enterprise_audit_logs", ["company_id", "created_at"])
    op.create_index("ix_enterprise_audit_actor", "enterprise_audit_logs", ["company_id", "actor_user_id"])
    op.create_index("ix_enterprise_audit_action", "enterprise_audit_logs", ["company_id", "action"])

    op.create_table(
        "enterprise_retention_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("data_type", sa.String(100), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("auto_delete", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("anonymize", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_timestamps(),
        sa.UniqueConstraint("company_id", "data_type", name="uq_enterprise_retention_data_type"),
    )
    op.create_index("ix_enterprise_retention_policies_company_id", "enterprise_retention_policies", ["company_id"])

    op.create_table(
        "enterprise_consent_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", sa.String(255), nullable=False),
        sa.Column("purpose", sa.String(255), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("source", sa.String(100)),
        sa.Column("ip_address", postgresql.INET()),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_enterprise_consent_company_subject", "enterprise_consent_logs", ["company_id", "subject_id"])
    op.create_index("ix_enterprise_consent_company_created", "enterprise_consent_logs", ["company_id", "created_at"])

    op.create_table(
        "enterprise_export_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("export_type", sa.String(64), nullable=False),
        sa.Column("format", sa.String(16), nullable=False, server_default="csv"),
        sa.Column("filters", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", export_status, nullable=False, server_default="pending"),
        sa.Column("storage_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("storage_files.id", ondelete="SET NULL")),
        sa.Column("download_url", sa.String(1024)),
        sa.Column("row_count", sa.Integer()),
        sa.Column("error", sa.Text()),
        *_timestamps(),
    )
    op.create_index("ix_enterprise_exports_company_created", "enterprise_export_jobs", ["company_id", "created_at"])


def downgrade() -> None:
    for table in (
        "enterprise_export_jobs",
        "enterprise_consent_logs",
        "enterprise_retention_policies",
        "enterprise_audit_logs",
        "enterprise_trusted_devices",
        "enterprise_security_policies",
        "enterprise_sso_connections",
        "enterprise_role_assignments",
        "enterprise_invitations",
        "enterprise_unit_memberships",
        "enterprise_custom_roles",
        "enterprise_permission_groups",
        "enterprise_units",
    ):
        op.drop_table(table)
    bind = op.get_bind()
    for enum in (export_status, audit_severity, sso_provider, invitation_status, unit_type):
        enum.drop(bind, checkfirst=True)
