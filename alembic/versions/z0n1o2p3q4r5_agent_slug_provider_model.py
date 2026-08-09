"""Agent slug + first-class provider/model columns.

Revision ID: z0n1o2p3q4r5
Revises: y9m0n1o2p3q4
Create Date: 2026-08-09
"""
from __future__ import annotations

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "z0n1o2p3q4r5"
down_revision: Union[str, Sequence[str], None] = "y9m0n1o2p3q4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
    return column in cols


def _slugify(name: str, fallback: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return base or fallback


def upgrade() -> None:
    if not _has_column("agent_configs", "slug"):
        op.add_column("agent_configs", sa.Column("slug", sa.String(160), nullable=True))
    if not _has_column("agent_configs", "provider"):
        op.add_column("agent_configs", sa.Column("provider", sa.String(50), nullable=True))
    if not _has_column("agent_configs", "model"):
        op.add_column("agent_configs", sa.Column("model", sa.String(120), nullable=True))

    bind = op.get_bind()
    indexes = {ix["name"] for ix in sa.inspect(bind).get_indexes("agent_configs")}
    if "ix_agent_configs_slug" not in indexes:
        op.create_index("ix_agent_configs_slug", "agent_configs", ["slug"], unique=False)

    # Backfill: slug from name (unique per company), provider/model lifted out of web_config.
    rows = bind.execute(
        sa.text(
            "SELECT id, company_id, name, web_config FROM agent_configs "
            "WHERE slug IS NULL OR provider IS NULL OR model IS NULL"
        )
    ).fetchall()

    used_per_company: dict = {}
    for row in rows:
        agent_id, company_id, name, web_config = row
        web_config = web_config or {}

        existing = used_per_company.setdefault(company_id, set())
        base_slug = _slugify(name, str(agent_id)[:8])
        slug = base_slug
        suffix = 1
        while slug in existing:
            suffix += 1
            slug = f"{base_slug}-{suffix}"
        existing.add(slug)

        provider = web_config.get("provider") or "openai"
        model = web_config.get("model") or "gpt-4o-mini"

        bind.execute(
            sa.text(
                "UPDATE agent_configs SET slug = :slug, provider = :provider, model = :model "
                "WHERE id = :id"
            ),
            {"slug": slug, "provider": provider, "model": model, "id": agent_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    indexes = {ix["name"] for ix in sa.inspect(bind).get_indexes("agent_configs")}
    if "ix_agent_configs_slug" in indexes:
        op.drop_index("ix_agent_configs_slug", table_name="agent_configs")
    for col in ("model", "provider", "slug"):
        if _has_column("agent_configs", col):
            op.drop_column("agent_configs", col)
