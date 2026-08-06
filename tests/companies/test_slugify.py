"""Unit tests for company / workspace slug generation."""
from __future__ import annotations

from app.companies.slugify import allocate_unique_slug, slugify_company_name


def test_slugify_asma_garments():
    assert slugify_company_name("Asma Garments") == "asma-garments"


def test_slugify_strips_and_collapses():
    assert slugify_company_name("  ACME!!! AI  ") == "acme-ai"
    assert slugify_company_name("---") == "workspace"
    assert slugify_company_name("") == "workspace"


def test_allocate_unique_slug_base_free():
    assert allocate_unique_slug("Asma Garments", slug_exists=lambda s: False) == "asma-garments"


def test_allocate_unique_slug_numeric_then_hex():
    taken = {"asma-garments"}
    assert (
        allocate_unique_slug("Asma Garments", slug_exists=lambda s: s in taken)
        == "asma-garments-2"
    )
    taken.add("asma-garments-2")
    for n in range(3, 50):
        taken.add(f"asma-garments-{n}")
    result = allocate_unique_slug("Asma Garments", slug_exists=lambda s: s in taken)
    assert result.startswith("asma-garments-")
    suffix = result.rsplit("-", 1)[-1]
    assert len(suffix) == 4
    assert all(c in "0123456789abcdef" for c in suffix)
