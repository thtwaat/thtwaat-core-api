"""Enterprise module unit and stack-backed integration coverage."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.enterprise.middleware import EnterpriseSecurityMiddleware
from app.enterprise.models import SSOProvider, UnitType
from app.enterprise.schemas import (
    BulkInviteRequest,
    InviteMember,
    SecurityPolicyUpdate,
    SSOConnectionCreate,
    UnitCreate,
)
from app.enterprise.service import EnterpriseService
from app.rbac.enums import Permission


@pytest.mark.unit
def test_role_templates_only_contain_registered_permissions():
    valid = {permission.value for permission in Permission}
    templates = EnterpriseService.role_templates()
    assert {"organization_admin", "security_admin", "compliance_manager"} <= set(templates)
    assert all(set(permissions) <= valid for permissions in templates.values())


@pytest.mark.unit
def test_permission_validation_rejects_unknown_values():
    with pytest.raises(HTTPException) as exc:
        EnterpriseService._validate_permissions(["enterprise:read", "unknown:power"])
    assert exc.value.status_code == 422
    assert exc.value.detail["unknown_permissions"] == ["unknown:power"]


@pytest.mark.unit
def test_permission_validation_deduplicates():
    result = EnterpriseService._validate_permissions(
        [Permission.ENTERPRISE_READ.value, Permission.ENTERPRISE_READ.value]
    )
    assert result == [Permission.ENTERPRISE_READ.value]


@pytest.mark.unit
def test_unit_schema_and_security_policy_bounds():
    unit = UnitCreate(
        name="Platform",
        slug="platform",
        unit_type=UnitType.DEPARTMENT,
        parent_id=uuid.uuid4(),
    )
    assert unit.unit_type == UnitType.DEPARTMENT
    with pytest.raises(ValidationError):
        SecurityPolicyUpdate(session_ttl_minutes=1)


@pytest.mark.unit
def test_bulk_invite_is_bounded():
    member = InviteMember(
        email="person@example.com",
        first_name="A",
        last_name="Person",
    )
    assert len(BulkInviteRequest(members=[member]).members) == 1
    with pytest.raises(ValidationError):
        BulkInviteRequest(members=[])


@pytest.mark.unit
def test_oidc_requires_secure_configuration_shape():
    body = SSOConnectionCreate(
        name="Workspace",
        provider=SSOProvider.GOOGLE_WORKSPACE,
        domain="example.com",
        client_id="client-id",
        client_secret="long-secret",
        allowed_redirect_uris=["https://app.example.com/auth/callback"],
    )
    assert body.provider == SSOProvider.GOOGLE_WORKSPACE
    assert body.allowed_redirect_uris[0].startswith("https://")


@pytest.mark.unit
def test_ip_allow_list_supports_hosts_and_cidr():
    assert EnterpriseSecurityMiddleware._ip_allowed("10.0.0.5", ["10.0.0.0/24"])
    assert EnterpriseSecurityMiddleware._ip_allowed("203.0.113.10", ["203.0.113.10"])
    assert not EnterpriseSecurityMiddleware._ip_allowed("10.0.1.5", ["10.0.0.0/24"])
    assert not EnterpriseSecurityMiddleware._ip_allowed(None, ["10.0.0.0/24"])


@pytest.mark.unit
def test_export_encoders():
    rows = [{"id": "1", "action": "login"}]
    csv_data = EnterpriseService._encode_export(rows, "csv").decode()
    assert "id,action" in csv_data
    assert "login" in csv_data
    json_data = EnterpriseService._encode_export(rows, "json").decode()
    assert '"action": "login"' in json_data


def _auth(client):
    slug = f"enterprise-{uuid.uuid4().hex[:8]}"
    company = client.post(
        "/api/v1/companies/",
        json={"name": "Enterprise Co", "slug": slug},
    )
    assert company.status_code in (200, 201), company.text
    company_id = company.json()["id"]
    email = f"owner-{uuid.uuid4().hex[:8]}@example.com"
    user = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": "securepassword",
            "company_id": company_id,
            "first_name": "Enterprise",
            "last_name": "Owner",
            "role": "company_owner",
        },
    )
    assert user.status_code in (200, 201), user.text
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, company_id


@pytest.mark.integration
def test_enterprise_hierarchy_rbac_and_compliance_flow(client):
    headers, company_id = _auth(client)
    organization = client.post(
        "/api/v1/enterprise/units",
        headers=headers,
        json={
            "name": "Enterprise Co",
            "slug": "enterprise-co",
            "unit_type": "organization",
        },
    )
    assert organization.status_code == 201, organization.text
    org_id = organization.json()["id"]

    department = client.post(
        "/api/v1/enterprise/units",
        headers=headers,
        json={
            "name": "Engineering",
            "slug": "engineering",
            "unit_type": "department",
            "parent_id": org_id,
        },
    )
    assert department.status_code == 201, department.text

    role = client.post(
        "/api/v1/enterprise/rbac/roles",
        headers=headers,
        json={"name": "Security Reader", "template_key": "security_admin"},
    )
    assert role.status_code == 201, role.text
    assert "enterprise:security" in role.json()["permissions"]

    policy = client.patch(
        "/api/v1/enterprise/security/policy",
        headers=headers,
        json={
            "session_ttl_minutes": 1440,
            "api_policies": {"max_request_bytes": 5_000_000},
        },
    )
    assert policy.status_code == 200, policy.text
    assert policy.json()["session_ttl_minutes"] == 1440

    retention = client.put(
        "/api/v1/enterprise/compliance/retention",
        headers=headers,
        json={
            "data_type": "audit",
            "retention_days": 2555,
            "legal_hold": False,
            "auto_delete": True,
        },
    )
    assert retention.status_code == 200, retention.text

    audit = client.get("/api/v1/enterprise/audit/logs", headers=headers)
    assert audit.status_code == 200, audit.text
    assert len(audit.json()) >= 3

    dashboard = client.get("/api/v1/enterprise/dashboard", headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["organization"]["id"] == company_id
