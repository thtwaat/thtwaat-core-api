"""Marketplace Phase 7: Postgres full-text search on templates.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-08-03
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "marketplace_templates"
COLUMN = "search_vector"
INDEX = "ix_marketplace_templates_search_vector"

# Weighted document: name/slug (A), industry/description (B), tags (C)
GENERATED_EXPR = """(
  setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
  setweight(to_tsvector('english', coalesce(slug, '')), 'A') ||
  setweight(to_tsvector('english', coalesce(industry, '')), 'B') ||
  setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
  setweight(to_tsvector('english', coalesce(array_to_string(tags, ' '), '')), 'C')
)"""


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def _has_index(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return index_name in {i["name"] for i in inspector.get_indexes(table)}


def upgrade() -> None:
    if not _has_table(TABLE):
        return
    bind = op.get_bind()
    if not _has_column(TABLE, COLUMN):
        bind.execute(
            sa.text(
                f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} tsvector "
                f"GENERATED ALWAYS AS {GENERATED_EXPR} STORED"
            )
        )
    if not _has_index(TABLE, INDEX):
        op.create_index(INDEX, TABLE, [COLUMN], postgresql_using="gin")


def downgrade() -> None:
    if not _has_table(TABLE):
        return
    if _has_index(TABLE, INDEX):
        op.drop_index(INDEX, table_name=TABLE)
    if _has_column(TABLE, COLUMN):
        op.drop_column(TABLE, COLUMN)
