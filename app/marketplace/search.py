"""Postgres full-text search helpers for marketplace templates."""
from __future__ import annotations

from typing import Any, Optional, Tuple

from sqlalchemy import func, literal_column, or_
from sqlalchemy.orm import Query
from sqlalchemy.sql.elements import ColumnElement

from app.marketplace.models import MarketplaceTemplate

# DB-owned search_vector column (migration e1f2a3b4c5d6, trigger-maintained)
# — not mapped on the ORM model
_SEARCH_VECTOR = literal_column("marketplace_templates.search_vector")


def resolve_sort_key(*, sort: Optional[str], newest: bool, q: Optional[str]) -> str:
    if sort:
        return sort.lower()
    if newest:
        return "newest"
    if q and q.strip():
        return "relevance"
    return "featured"


def apply_template_text_search(
    query: Query,
    q: Optional[str],
    *,
    dialect_name: str,
) -> Tuple[Query, Optional[ColumnElement[Any]]]:
    """Filter by `q`. On Postgres uses FTS (+ ILIKE safety net); else ILIKE.

    Returns (query, rank_expr) — rank_expr is set when FTS ranking is available.
    """
    term = (q or "").strip()
    if not term:
        return query, None

    like = f"%{term}%"
    if dialect_name == "postgresql":
        tsquery = func.websearch_to_tsquery("english", term)
        rank = func.ts_rank_cd(_SEARCH_VECTOR, tsquery)
        query = query.filter(
            or_(
                _SEARCH_VECTOR.op("@@")(tsquery),
                MarketplaceTemplate.name.ilike(like),
                MarketplaceTemplate.slug.ilike(like),
                MarketplaceTemplate.description.ilike(like),
                MarketplaceTemplate.industry.ilike(like),
            )
        )
        return query, rank

    # Non-Postgres fallback (unit / sqlite): substring match
    query = query.filter(
        or_(
            MarketplaceTemplate.name.ilike(like),
            MarketplaceTemplate.description.ilike(like),
            MarketplaceTemplate.slug.ilike(like),
            MarketplaceTemplate.industry.ilike(like),
        )
    )
    return query, None
