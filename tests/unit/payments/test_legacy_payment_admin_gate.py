"""Regression tests for the CRITICAL/HIGH audit finding on the legacy
generic-payments CRUD surface: PATCH /payments/{id}/status accepted a
client-controlled status (including "success") and gateway_transaction_id
with no gateway verification, and POST /payments/{id}/refund had no admin
gate while calling the real gateway provider's refund API.

Fix: both routes now depend on the existing
``app.payments.admin_router.require_platform_admin`` dependency (reused,
not reinvented) instead of the plain ``get_current_user`` dependency, so
only a PLATFORM_ADMIN-permissioned caller can reach them. These tests
exercise that dependency directly — no DB/HTTP stack required — mirroring
the ordinary company user vs. platform admin boundary that is the actual
security fix.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.payments.admin_router import require_platform_admin
from app.payments.router import refund_payment, update_payment_status


@pytest.mark.unit
def test_ordinary_company_admin_cannot_pass_the_gate():
    """The tenant-scoped 'admin' role (EnterpriseRole.ADMIN) must NOT carry
    PLATFORM_ADMIN — this is exactly the role used to fabricate a fake
    'success' payment in the pre-fix vulnerable flow."""
    with pytest.raises(HTTPException) as exc:
        require_platform_admin(user=SimpleNamespace(role="admin"))
    assert exc.value.status_code == 403


@pytest.mark.unit
def test_ordinary_employee_cannot_pass_the_gate():
    with pytest.raises(HTTPException) as exc:
        require_platform_admin(user=SimpleNamespace(role="employee"))
    assert exc.value.status_code == 403


@pytest.mark.unit
def test_unrecognized_role_cannot_pass_the_gate():
    with pytest.raises(HTTPException) as exc:
        require_platform_admin(user=SimpleNamespace(role="not_a_real_role"))
    assert exc.value.status_code == 403


@pytest.mark.unit
def test_super_admin_passes_the_gate():
    user = SimpleNamespace(role="super_admin")
    result = require_platform_admin(user=user)
    assert result is user


@pytest.mark.unit
def test_update_payment_status_route_depends_on_platform_admin_gate():
    """The route's own dependency wiring must be require_platform_admin,
    not the plain get_current_user used by every other route in this
    router — this is what actually closes the finding at the FastAPI
    dependency-injection level."""
    import inspect

    sig = inspect.signature(update_payment_status)
    dep = sig.parameters["current_user"].default
    assert dep.dependency is require_platform_admin


@pytest.mark.unit
def test_refund_payment_route_depends_on_platform_admin_gate():
    import inspect

    sig = inspect.signature(refund_payment)
    dep = sig.parameters["current_user"].default
    assert dep.dependency is require_platform_admin
