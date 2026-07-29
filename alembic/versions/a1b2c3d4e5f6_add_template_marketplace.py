"""add template marketplace

Revision ID: a1b2c3d4e5f6
Revises: f3c4d5e6f7a8
Create Date: 2026-07-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

template_category_enum = sa.Enum(
    "website",
    "landing",
    "saas",
    "crm",
    "helpdesk",
    "ecommerce",
    "education",
    "healthcare",
    "real_estate",
    "restaurant",
    "finance",
    "legal",
    name="template_category_enum",
    create_type=False,
)
template_status_enum = sa.Enum(
    "draft",
    "published",
    "archived",
    name="template_status_enum",
    create_type=False,
)
install_status_enum = sa.Enum(
    "pending",
    "connecting",
    "ready",
    "published",
    "update_available",
    "failed",
    "uninstalled",
    name="template_install_status_enum",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    template_category_enum.create(bind, checkfirst=True)
    template_status_enum.create(bind, checkfirst=True)
    install_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "marketplace_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", template_category_enum, nullable=False),
        sa.Column("industry", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="1.0.0"),
        sa.Column("thumbnail", sa.String(length=500), nullable=True),
        sa.Column("icon", sa.String(length=120), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("author", sa.String(length=160), nullable=False, server_default="THTWAAT"),
        sa.Column("status", template_status_enum, nullable=False, server_default="draft"),
        sa.Column("price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("supports_agents", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("supports_domains", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("supports_billing", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("supports_mobile", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("package_path", sa.String(length=255), nullable=True),
        sa.Column("install_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("default_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("slug", name="uq_marketplace_templates_slug"),
    )
    op.create_index("ix_marketplace_templates_id", "marketplace_templates", ["id"])
    op.create_index("ix_marketplace_templates_slug", "marketplace_templates", ["slug"])
    op.create_index("ix_marketplace_templates_category", "marketplace_templates", ["category"])
    op.create_index("ix_marketplace_templates_status", "marketplace_templates", ["status"])
    op.create_index(
        "ix_marketplace_templates_category_status",
        "marketplace_templates",
        ["category", "status"],
    )
    op.create_index(
        "ix_marketplace_templates_featured",
        "marketplace_templates",
        ["is_featured", "status"],
    )

    op.create_table(
        "marketplace_template_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketplace_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("template_id", "version", name="uq_template_version"),
    )
    op.create_index("ix_marketplace_template_versions_id", "marketplace_template_versions", ["id"])
    op.create_index("ix_template_versions_template", "marketplace_template_versions", ["template_id"])

    op.create_table(
        "marketplace_template_installations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketplace_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketplace_template_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("installed_version", sa.String(length=32), nullable=False),
        sa.Column("previous_version", sa.String(length=32), nullable=True),
        sa.Column("previous_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", install_status_enum, nullable=False, server_default="pending"),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("api_key_prefix", sa.String(length=32), nullable=True),
        sa.Column("domain_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("update_available", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("latest_available_version", sa.String(length=32), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("installed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("company_id", "template_id", name="uq_company_template_install"),
    )
    op.create_index("ix_marketplace_template_installations_id", "marketplace_template_installations", ["id"])
    op.create_index("ix_marketplace_template_installations_company_id", "marketplace_template_installations", ["company_id"])
    op.create_index("ix_marketplace_template_installations_template_id", "marketplace_template_installations", ["template_id"])
    op.create_index("ix_marketplace_template_installations_agent_id", "marketplace_template_installations", ["agent_id"])
    op.create_index("ix_marketplace_template_installations_status", "marketplace_template_installations", ["status"])
    op.create_index(
        "ix_template_installs_company_status",
        "marketplace_template_installations",
        ["company_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_template_installs_company_status", table_name="marketplace_template_installations")
    op.drop_index("ix_marketplace_template_installations_status", table_name="marketplace_template_installations")
    op.drop_index("ix_marketplace_template_installations_agent_id", table_name="marketplace_template_installations")
    op.drop_index("ix_marketplace_template_installations_template_id", table_name="marketplace_template_installations")
    op.drop_index("ix_marketplace_template_installations_company_id", table_name="marketplace_template_installations")
    op.drop_index("ix_marketplace_template_installations_id", table_name="marketplace_template_installations")
    op.drop_table("marketplace_template_installations")

    op.drop_index("ix_template_versions_template", table_name="marketplace_template_versions")
    op.drop_index("ix_marketplace_template_versions_id", table_name="marketplace_template_versions")
    op.drop_table("marketplace_template_versions")

    op.drop_index("ix_marketplace_templates_featured", table_name="marketplace_templates")
    op.drop_index("ix_marketplace_templates_category_status", table_name="marketplace_templates")
    op.drop_index("ix_marketplace_templates_status", table_name="marketplace_templates")
    op.drop_index("ix_marketplace_templates_category", table_name="marketplace_templates")
    op.drop_index("ix_marketplace_templates_slug", table_name="marketplace_templates")
    op.drop_index("ix_marketplace_templates_id", table_name="marketplace_templates")
    op.drop_table("marketplace_templates")

    bind = op.get_bind()
    install_status_enum.drop(bind, checkfirst=True)
    template_status_enum.drop(bind, checkfirst=True)
    template_category_enum.drop(bind, checkfirst=True)
