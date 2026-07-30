"""add product generator table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

generation_status_enum = postgresql.ENUM(
    "draft",
    "analyzing",
    "template_selected",
    "provisioning",
    "configuring",
    "binding",
    "preview_ready",
    "publishing",
    "published",
    "failed",
    name="product_generation_status_enum",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    generation_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "product_generations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("status", generation_status_enum, nullable=False, server_default="draft"),
        sa.Column("analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("template_slug", sa.String(length=120), nullable=True),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("api_key_prefix", sa.String(length=32), nullable=True),
        sa.Column("widget_id", sa.String(length=64), nullable=True),
        sa.Column("domain_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("preview_url", sa.String(length=500), nullable=True),
        sa.Column("widget_snippet", sa.Text(), nullable=True),
        sa.Column("publish_status", sa.String(length=32), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("deployment_checklist", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("ephemeral_api_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_product_generations_id", "product_generations", ["id"])
    op.create_index("ix_product_generations_company_id", "product_generations", ["company_id"])
    op.create_index("ix_product_generations_agent_id", "product_generations", ["agent_id"])
    op.create_index("ix_product_generations_status", "product_generations", ["status"])
    op.create_index(
        "ix_product_generations_company_status",
        "product_generations",
        ["company_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_product_generations_company_status", table_name="product_generations")
    op.drop_index("ix_product_generations_status", table_name="product_generations")
    op.drop_index("ix_product_generations_agent_id", table_name="product_generations")
    op.drop_index("ix_product_generations_company_id", table_name="product_generations")
    op.drop_index("ix_product_generations_id", table_name="product_generations")
    op.drop_table("product_generations")

    bind = op.get_bind()
    generation_status_enum.drop(bind, checkfirst=True)
