"""Marketplace Phase 7: Postgres full-text search on templates.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-08-03

NOTE: A GENERATED ALWAYS AS (to_tsvector...) STORED column is rejected by
Postgres when the expression is not fully IMMUTABLE (even with ::regconfig,
array_to_string on varchar[] can fail the check). We maintain search_vector
with an IMMUTABLE SQL helper + BEFORE INSERT/UPDATE trigger instead.
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
FN_DOC = "tht_marketplace_tsvector_doc"
FN_TAGS = "tht_marketplace_tags_text"
FN_TRIGGER = "tht_marketplace_templates_search_vector_tg"
TRIGGER = "trg_marketplace_templates_search_vector"

# Kept for unit tests / docs — expression body used by the SQL helper.
GENERATED_EXPR = f"{FN_DOC}(name, slug, industry, description, tags)"


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

    # Immutable helpers — safe for expression indexes / future generated columns
    bind.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {FN_TAGS}(tags character varying[])
            RETURNS text
            LANGUAGE sql
            IMMUTABLE
            PARALLEL SAFE
            AS $fn$
              SELECT coalesce(array_to_string(tags, ' '), '')
            $fn$
            """
        )
    )
    bind.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {FN_DOC}(
              name text,
              slug text,
              industry text,
              description text,
              tags character varying[]
            )
            RETURNS tsvector
            LANGUAGE sql
            IMMUTABLE
            PARALLEL SAFE
            AS $fn$
              SELECT
                setweight(to_tsvector('english'::regconfig, coalesce(name, '')), 'A') ||
                setweight(to_tsvector('english'::regconfig, coalesce(slug, '')), 'A') ||
                setweight(to_tsvector('english'::regconfig, coalesce(industry, '')), 'B') ||
                setweight(to_tsvector('english'::regconfig, coalesce(description, '')), 'B') ||
                setweight(to_tsvector('english'::regconfig, {FN_TAGS}(tags)), 'C')
            $fn$
            """
        )
    )

    if not _has_column(TABLE, COLUMN):
        # Plain column (not GENERATED) — populated by trigger + backfill
        bind.execute(sa.text(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} tsvector"))

    bind.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {FN_TRIGGER}()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $fn$
            BEGIN
              NEW.{COLUMN} := {FN_DOC}(
                NEW.name, NEW.slug, NEW.industry, NEW.description, NEW.tags
              );
              RETURN NEW;
            END
            $fn$
            """
        )
    )
    bind.execute(sa.text(f"DROP TRIGGER IF EXISTS {TRIGGER} ON {TABLE}"))
    bind.execute(
        sa.text(
            f"""
            CREATE TRIGGER {TRIGGER}
            BEFORE INSERT OR UPDATE OF name, slug, industry, description, tags
            ON {TABLE}
            FOR EACH ROW
            EXECUTE FUNCTION {FN_TRIGGER}()
            """
        )
    )

    # Backfill existing rows
    bind.execute(
        sa.text(
            f"""
            UPDATE {TABLE}
            SET {COLUMN} = {FN_DOC}(name, slug, industry, description, tags)
            WHERE {COLUMN} IS NULL
            """
        )
    )

    if not _has_index(TABLE, INDEX):
        op.create_index(INDEX, TABLE, [COLUMN], postgresql_using="gin")


def downgrade() -> None:
    if not _has_table(TABLE):
        return
    bind = op.get_bind()
    bind.execute(sa.text(f"DROP TRIGGER IF EXISTS {TRIGGER} ON {TABLE}"))
    bind.execute(sa.text(f"DROP FUNCTION IF EXISTS {FN_TRIGGER}()"))
    if _has_index(TABLE, INDEX):
        op.drop_index(INDEX, table_name=TABLE)
    if _has_column(TABLE, COLUMN):
        op.drop_column(TABLE, COLUMN)
    bind.execute(sa.text(f"DROP FUNCTION IF EXISTS {FN_DOC}(text, text, text, text, character varying[])"))
    bind.execute(sa.text(f"DROP FUNCTION IF EXISTS {FN_TAGS}(character varying[])"))
