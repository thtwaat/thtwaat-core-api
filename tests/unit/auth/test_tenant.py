"""Unit tests for tenant isolation helpers and API key masking."""

import uuid

import pytest
from fastapi import HTTPException

from app.apps.service import mask_api_key
from app.auth.schema import UserProfileResponse
from app.auth.tenant import (
    assert_same_company,
    can_manage_company_users,
    is_platform_admin,
    require_platform_admin,
)


def _user(role: str, company_id: uuid.UUID | None = None) -> UserProfileResponse:
    return UserProfileResponse(
        id=uuid.uuid4(),
        company_id=company_id or uuid.uuid4(),
        email=f"{role}-{uuid.uuid4().hex[:6]}@example.com",
        first_name="T",
        last_name="U",
        role=role,
    )


@pytest.mark.unit
def test_is_platform_admin_true_for_super_admin():
    assert is_platform_admin(_user("super_admin")) is True


@pytest.mark.unit
def test_is_platform_admin_false_for_company_owner():
    assert is_platform_admin(_user("company_owner")) is False


@pytest.mark.unit
def test_assert_same_company_allows_own():
    cid = uuid.uuid4()
    assert_same_company(_user("employee", cid), cid)


@pytest.mark.unit
def test_assert_same_company_404_for_foreign():
    with pytest.raises(HTTPException) as exc:
        assert_same_company(_user("employee"), uuid.uuid4())
    assert exc.value.status_code == 404


@pytest.mark.unit
def test_assert_same_company_platform_admin_bypass():
    assert_same_company(_user("super_admin"), uuid.uuid4())


@pytest.mark.unit
def test_can_manage_company_users():
    assert can_manage_company_users(_user("company_owner")) is True
    assert can_manage_company_users(_user("admin")) is True
    assert can_manage_company_users(_user("employee")) is False
    assert can_manage_company_users(_user("super_admin")) is True


@pytest.mark.unit
def test_require_platform_admin():
    require_platform_admin(_user("super_admin"))
    with pytest.raises(HTTPException) as exc:
        require_platform_admin(_user("company_owner"))
    assert exc.value.status_code == 403


@pytest.mark.unit
def test_mask_api_key():
    raw = "thtwaat_live_abcdefghijklmnopqrstuvwxyz012345"
    masked = mask_api_key(raw)
    assert masked.startswith("thtwaat_")
    assert masked.endswith(raw[-4:])
    assert raw not in masked
    assert "…" in masked
