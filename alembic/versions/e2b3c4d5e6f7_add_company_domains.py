"""Add company_domains table for Domain Manager.

Revision ID: e2b3c4d5e6f7
Revises: d1a2b3c4e5f6
Create Date: 2026-07-29 11:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "d1a2b3c4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    domain_status = postgresql.ENUM(
        "PENDING",
        "DNS_PENDING",
        "VERIFIED",
        "SSL_PENDING",
        "LIVE",
        "FAILED",
        name="domain_status_enum",
        create_type=False,
    )
    verify_method = postgresql.ENUM(
        "TXT",
        "CNAME",
        name="domain_verification_method_enum",
        create_type=False,
    )

    bind = op.get_bind()
    domain_status.create(bind, checkfirst=True)
    verify_method.create(bind, checkfirst=True)

    op.create_table(
        "company_domains",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("hostname", sa.String(length=253), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "DNS_PENDING",
                "VERIFIED",
                "SSL_PENDING",
                "LIVE",
                "FAILED",
                name="domain_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "verification_method",
            postgresql.ENUM(
                "TXT",
                "CNAME",
                name="domain_verification_method_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="TXT",
        ),
        sa.Column("verification_token", sa.String(length=128), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("widget_id", sa.String(length=64), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "dns_records",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("ssl_status", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("ssl_issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ssl_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ssl_renewal_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ssl_provider", sa.String(length=64), nullable=True, server_default="letsencrypt"),
        sa.Column("cors_origin", sa.String(length=300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("hostname", name="uq_company_domains_hostname"),
    )
    op.create_index("ix_company_domains_id", "company_domains", ["id"])
    op.create_index("ix_company_domains_company_id", "company_domains", ["company_id"])
    op.create_index("ix_company_domains_status", "company_domains", ["status"])
    op.create_index("ix_company_domains_agent_id", "company_domains", ["agent_id"])
    op.create_index("ix_company_domains_widget_id", "company_domains", ["widget_id"])
    op.create_index(
        "ix_company_domains_company_status",
        "company_domains",
        ["company_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_company_domains_company_status", table_name="company_domains")
    op.drop_index("ix_company_domains_widget_id", table_name="company_domains")
    op.drop_index("ix_company_domains_agent_id", table_name="company_domains")
    op.drop_index("ix_company_domains_status", table_name="company_domains")
    op.drop_index("ix_company_domains_company_id", table_name="company_domains")
    op.drop_index("ix_company_domains_id", table_name="company_domains")
    op.drop_table("company_domains")

    bind = op.get_bind()
    postgresql.ENUM(name="domain_status_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="domain_verification_method_enum").drop(bind, checkfirst=True)
