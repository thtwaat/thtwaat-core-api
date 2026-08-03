"""Unit: Phase 7 sort key resolution + FTS generated expression (no DB)."""
from __future__ import annotations

from app.marketplace.search import resolve_sort_key


def test_resolve_sort_key_defaults():
    assert resolve_sort_key(sort=None, newest=False, q=None) == "featured"
    assert resolve_sort_key(sort=None, newest=True, q=None) == "newest"
    assert resolve_sort_key(sort=None, newest=False, q="blog") == "relevance"
    assert resolve_sort_key(sort="name", newest=False, q="blog") == "name"
    assert resolve_sort_key(sort="RELEVANCE", newest=False, q="x") == "relevance"


def test_generated_fts_expr_uses_immutable_regconfig():
    # Import from the migration module path used by Alembic
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "e1f2a3b4c5d6_marketplace_phase7_fts.py"
    )
    spec = importlib.util.spec_from_file_location("phase7_fts_migration", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    expr = mod.GENERATED_EXPR
    # Postgres rejects GENERATED columns unless to_tsvector config is regconfig
    assert "english'::regconfig" in expr
    assert "to_tsvector('english', coalesce" not in expr
