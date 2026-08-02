"""Unit: Phase 7 sort key resolution (no DB)."""
from __future__ import annotations

from app.marketplace.search import resolve_sort_key


def test_resolve_sort_key_defaults():
    assert resolve_sort_key(sort=None, newest=False, q=None) == "featured"
    assert resolve_sort_key(sort=None, newest=True, q=None) == "newest"
    assert resolve_sort_key(sort=None, newest=False, q="blog") == "relevance"
    assert resolve_sort_key(sort="name", newest=False, q="blog") == "name"
    assert resolve_sort_key(sort="RELEVANCE", newest=False, q="x") == "relevance"
