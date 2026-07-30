"""add white label company branding

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

branding_asset_type_enum = postgresql.ENUM(
    "logo",
    "dark_logo",
    "favicon",
    "splash",
    "launcher_icon",
    "email_logo",
    "login_background",
    "widget_launcher",
    "widget_header",
    name="branding_asset_type_enum",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    branding_asset_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "company_branding",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("copyright_text", sa.String(500), nullable=True),
        sa.Column("footer_text", sa.Text(), nullable=True),
        sa.Column("primary_color", sa.String(32), nullable=False, server_default="#0F766E"),
        sa.Column("secondary_color", sa.String(32), nullable=False, server_default="#134E4A"),
        sa.Column("accent_color", sa.String(32), nullable=False, server_default="#F59E0B"),
        sa.Column(
            "font_family",
            sa.String(255),
            nullable=False,
            server_default="Inter, system-ui, sans-serif",
        ),
        sa.Column("heading_font", sa.String(255), nullable=True),
        sa.Column("dashboard_theme", sa.String(32), nullable=False, server_default="system"),
        sa.Column("login_background_url", sa.String(1024), nullable=True),
        sa.Column("logo_url", sa.String(1024), nullable=True),
        sa.Column("dark_logo_url", sa.String(1024), nullable=True),
        sa.Column("favicon_url", sa.String(1024), nullable=True),
        sa.Column("email", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("mobile", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("widget", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "domain_roles",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("draft_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("published_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("company_id", name="uq_company_branding_company_id"),
    )
    op.create_index("ix_company_branding_company_id", "company_branding", ["company_id"])

    op.create_table(
        "branding_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "branding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("company_branding.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_type",
            branding_asset_type_enum,
            nullable=False,
        ),
        sa.Column(
            "storage_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("storage_files.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_branding_assets_company_type",
        "branding_assets",
        ["company_id", "asset_type"],
    )
    op.create_index("ix_branding_assets_company_id", "branding_assets", ["company_id"])
    op.create_index("ix_branding_assets_branding_id", "branding_assets", ["branding_id"])


def downgrade() -> None:
    op.drop_index("ix_branding_assets_branding_id", table_name="branding_assets")
    op.drop_index("ix_branding_assets_company_id", table_name="branding_assets")
    op.drop_index("ix_branding_assets_company_type", table_name="branding_assets")
    op.drop_table("branding_assets")
    op.drop_index("ix_company_branding_company_id", table_name="company_branding")
    op.drop_table("company_branding")
    branding_asset_type_enum.drop(op.get_bind(), checkfirst=True)
