"""Unit: Phase 7 sort key resolution + FTS migration helpers (no DB)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from app.marketplace.search import resolve_sort_key


def test_resolve_sort_key_defaults():
    assert resolve_sort_key(sort=None, newest=False, q=None) == "featured"
    assert resolve_sort_key(sort=None, newest=True, q=None) == "newest"
    assert resolve_sort_key(sort=None, newest=False, q="blog") == "relevance"
    assert resolve_sort_key(sort="name", newest=False, q="blog") == "name"
    assert resolve_sort_key(sort="RELEVANCE", newest=False, q="x") == "relevance"


def test_phase7_migration_uses_trigger_not_generated_column():
    path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "e1f2a3b4c5d6_marketplace_phase7_fts.py"
    )
    source = path.read_text(encoding="utf-8")
    assert "ADD COLUMN {COLUMN} tsvector GENERATED" not in source
    assert "GENERATED ALWAYS AS {GENERATED_EXPR}" not in source
    assert "CREATE TRIGGER" in source
    assert "tht_marketplace_tsvector_doc" in source
    assert "english'::regconfig" in source

    spec = importlib.util.spec_from_file_location("phase7_fts_migration", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    assert "tht_marketplace_tsvector_doc" in mod.GENERATED_EXPR
