"""Unit tests for app/static_sites/preview_hostname.py — THTWAAT Deploy
Phase 6A deterministic, collision-safe preview hostnames."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.static_sites.preview_hostname import allocate_preview_subdomain, is_preview_hostname
from app.studio.domain_validation import allocate_free_subdomain


@pytest.mark.unit
def test_deterministic_per_site_and_pr():
    site_id = uuid4()
    a = allocate_preview_subdomain(site_id=site_id, site_name="Acme", pr_number=42)
    b = allocate_preview_subdomain(site_id=site_id, site_name="Acme", pr_number=42)
    assert a == b


@pytest.mark.unit
def test_distinct_per_pr_number():
    site_id = uuid4()
    a = allocate_preview_subdomain(site_id=site_id, site_name="Acme", pr_number=1)
    b = allocate_preview_subdomain(site_id=site_id, site_name="Acme", pr_number=2)
    assert a != b


@pytest.mark.unit
def test_distinct_per_site():
    a = allocate_preview_subdomain(site_id=uuid4(), site_name="Acme", pr_number=1)
    b = allocate_preview_subdomain(site_id=uuid4(), site_name="Acme", pr_number=1)
    assert a != b


@pytest.mark.unit
def test_never_collides_with_production_free_subdomain():
    """Structural guarantee (spec §4): a preview hostname must never equal a
    production free-subdomain hostname for the SAME site — proven here by
    generating both from identical inputs and asserting they differ, not
    just by convention."""
    site_id = uuid4()
    prod = allocate_free_subdomain(project_id=site_id, project_title="Acme")
    preview = allocate_preview_subdomain(site_id=site_id, site_name="Acme", pr_number=1)
    assert prod != preview
    assert is_preview_hostname(preview)
    assert not is_preview_hostname(prod)


@pytest.mark.unit
def test_hostname_is_lowercase_and_dns_safe():
    hostname = allocate_preview_subdomain(site_id=uuid4(), site_name="My Cool App!!", pr_number=7)
    assert hostname == hostname.lower()
    label = hostname.split(".")[0]
    assert all(c.isalnum() or c == "-" for c in label)
    assert not label.startswith("-")
    assert not label.endswith("-")


@pytest.mark.unit
def test_pr_number_embedded_in_hostname():
    hostname = allocate_preview_subdomain(site_id=uuid4(), site_name="Acme", pr_number=999)
    assert "-999-" in hostname


@pytest.mark.unit
def test_negative_pr_number_clamped_never_raises():
    # Defensive only — parse_pull_request_event already rejects a negative
    # PR number before this is ever called, but this function must never
    # itself raise on bad input.
    hostname = allocate_preview_subdomain(site_id=uuid4(), site_name="Acme", pr_number=-5)
    assert hostname
