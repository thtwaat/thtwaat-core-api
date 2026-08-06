"""Unit tests for CompanyService.create_company slug / name rules."""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.companies.model import CompanyPlan, CompanyStatus
from app.companies.schema import CompanyCreate
from app.companies.service import CompanyService


def _svc(*, existing_names=None, existing_slugs=None):
    existing_names = {n.lower() for n in (existing_names or set())}
    existing_slugs = set(existing_slugs or set())
    repo = MagicMock()
    repo.name_exists_ci = MagicMock(side_effect=lambda n: n.strip().lower() in existing_names)
    repo.slug_exists = MagicMock(side_effect=lambda s: s in existing_slugs)
    created = SimpleNamespace(
        id=uuid.uuid4(),
        name="Asma Garments",
        slug="asma-garments",
        display_name="Asma Garments",
        description=None,
        website=None,
        logo_url=None,
        industry=None,
        country=None,
        timezone="UTC",
        plan=CompanyPlan.FREE,
        status=CompanyStatus.TRIAL,
        is_verified=False,
        is_active=True,
        max_users=5,
        max_apps=3,
        settings={},
        created_at=None,
        updated_at=None,
    )

    def create_from_dict(data):
        created.name = data["name"]
        created.slug = data["slug"]
        created.display_name = data.get("display_name") or data["name"]
        return created

    repo.create_from_dict = MagicMock(side_effect=create_from_dict)
    repo.db = MagicMock()
    svc = CompanyService(MagicMock())
    svc.repo = repo
    return svc, repo, created


def test_create_company_auto_slug():
    svc, repo, _ = _svc()
    result = svc.create_company(CompanyCreate(name="Asma Garments"))
    assert result.slug == "asma-garments"
    assert repo.create_from_dict.call_args[0][0]["slug"] == "asma-garments"


def test_create_company_collision_suffix():
    svc, repo, _ = _svc(existing_slugs={"asma-garments"})
    result = svc.create_company(CompanyCreate(name="Asma Garments"))
    assert result.slug == "asma-garments-2"


def test_create_company_duplicate_name():
    svc, _, _ = _svc(existing_names={"Asma Garments"})
    with pytest.raises(HTTPException) as exc:
        svc.create_company(CompanyCreate(name="asma garments"))
    assert exc.value.status_code == 409
    assert exc.value.detail == "Company name already exists."


def test_create_company_repo_failure_message():
    svc, repo, _ = _svc()
    repo.create_from_dict.side_effect = RuntimeError("db down")
    with pytest.raises(HTTPException) as exc:
        svc.create_company(CompanyCreate(name="Fresh Co"))
    assert exc.value.status_code == 500
    assert exc.value.detail == "Unable to create workspace."
