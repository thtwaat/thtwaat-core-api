"""Domain Manager tests — CRUD, verification, permissions, CORS."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.domains.service import (
    DomainService,
    build_dns_records,
    get_cached_cors_origins,
    invalidate_cors_cache,
    widget_urls_for,
)
from app.domains.models import DomainStatus
from app.domains.cors import DynamicCORSMiddleware
from app.usage.service import UsageService


def _auth(client, role: str = "admin"):
    company_slug = f"dom-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": "Domain Co", "slug": company_slug},
    )
    assert company_resp.status_code in (200, 201), company_resp.text
    company_id = company_resp.json()["id"]

    email = f"owner-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword"
    user_resp = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": password,
            "company_id": company_id,
            "first_name": "Owner",
            "last_name": "User",
            "role": role,
        },
    )
    assert user_resp.status_code in (200, 201), user_resp.text

    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, company_id


def _enable_domains(db_session, company_id: str):
    """Free plan max_domains=0 — bump to starter for tests."""
    UsageService(db_session).apply_plan_limits(uuid.UUID(company_id), "starter", emit_upgraded=False)


# ── Unit helpers ──────────────────────────────────────────────────────────────

def test_build_dns_records_includes_txt_and_cname():
    records = build_dns_records("chat.acme.com", "tht_dom_token", "TXT")
    types = {r["type"] for r in records}
    assert "TXT" in types
    assert "CNAME" in types
    txt = next(r for r in records if r["type"] == "TXT")
    assert txt["host"] == "_thtwaat-verify.chat.acme.com"
    assert "tht_dom_token" in txt["value"]


def test_widget_urls_for_chat_host():
    urls = widget_urls_for("chat.acme.com")
    assert urls["chat_host"] == "https://chat.acme.com"
    assert urls["chat_path"] == "https://chat.acme.com/chat"


def test_widget_urls_for_apex():
    urls = widget_urls_for("acme.com")
    assert urls["chat_path"] == "https://acme.com/chat"
    assert "chat.acme.com" in urls["chat_host"]


# ── CRUD ──────────────────────────────────────────────────────────────────────

def test_domain_crud_flow(client, db_session):
    headers, company_id = _auth(client)
    _enable_domains(db_session, company_id)

    create = client.post(
        "/api/v1/domains/",
        json={"hostname": f"chat.{uuid.uuid4().hex[:6]}.example.com", "verification_method": "TXT"},
        headers=headers,
    )
    assert create.status_code == 201, create.text
    data = create.json()
    assert data["status"] == "PENDING"
    assert data["verification_token"].startswith("tht_dom_")
    assert any(r["type"] == "TXT" for r in data["dns_records"])
    assert "chat_path" in data["widget_urls"]
    domain_id = data["id"]

    listed = client.get("/api/v1/domains/", headers=headers)
    assert listed.status_code == 200
    assert any(d["id"] == domain_id for d in listed.json())

    got = client.get(f"/api/v1/domains/{domain_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["id"] == domain_id

    updated = client.patch(
        f"/api/v1/domains/{domain_id}",
        json={"is_primary": True, "widget_id": "wgt_test123"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["is_primary"] is True
    assert updated.json()["widget_id"] == "wgt_test123"

    dns = client.get(f"/api/v1/domains/{domain_id}/dns", headers=headers)
    assert dns.status_code == 200
    assert len(dns.json()["records"]) >= 2

    deleted = client.delete(f"/api/v1/domains/{domain_id}", headers=headers)
    assert deleted.status_code == 204

    missing = client.get(f"/api/v1/domains/{domain_id}", headers=headers)
    assert missing.status_code == 404


# ── Verification ──────────────────────────────────────────────────────────────

def test_domain_verify_success_with_dns_override(client, db_session):
    headers, company_id = _auth(client)
    _enable_domains(db_session, company_id)

    hostname = f"ai.{uuid.uuid4().hex[:6]}.example.com"
    create = client.post(
        "/api/v1/domains/",
        json={"hostname": hostname},
        headers=headers,
    )
    assert create.status_code == 201, create.text
    domain_id = create.json()["id"]

    def _ok(domain):
        return True, "mocked TXT ok"

    # Patch service method used by the request-scoped instance
    with patch.object(DomainService, "_verify_dns", lambda self, domain: _ok(domain)):
        resp = client.post(f"/api/v1/domains/{domain_id}/verify", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified"] is True
    assert body["status"] in ("SSL_PENDING", "VERIFIED", "LIVE")

    # Promote to LIVE via ssl issued
    live = client.post(f"/api/v1/domains/{domain_id}/ssl/issued", headers=headers)
    assert live.status_code == 200, live.text
    assert live.json()["status"] == "LIVE"
    assert live.json()["ssl_status"] in ("ACTIVE", "ISSUED", "issued")


def test_domain_verify_failure(client, db_session):
    headers, company_id = _auth(client)
    _enable_domains(db_session, company_id)

    create = client.post(
        "/api/v1/domains/",
        json={"hostname": f"app.{uuid.uuid4().hex[:6]}.example.com"},
        headers=headers,
    )
    domain_id = create.json()["id"]

    with patch.object(
        DomainService,
        "_verify_dns",
        lambda self, domain: (False, "TXT missing"),
    ):
        resp = client.post(f"/api/v1/domains/{domain_id}/verify", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["verified"] is False
    assert resp.json()["status"] == "FAILED"

    with patch.object(
        DomainService,
        "_verify_dns",
        lambda self, domain: (True, "ok"),
    ):
        retry = client.post(f"/api/v1/domains/{domain_id}/retry", headers=headers)
    assert retry.status_code == 200
    assert retry.json()["verified"] is True


# ── Permissions / isolation ───────────────────────────────────────────────────

def test_viewer_cannot_create_domain(client, db_session):
    headers, company_id = _auth(client, role="viewer")
    _enable_domains(db_session, company_id)
    resp = client.post(
        "/api/v1/domains/",
        json={"hostname": f"www.{uuid.uuid4().hex[:6]}.example.com"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_domain_company_isolation(client, db_session):
    headers_a, company_a = _auth(client)
    headers_b, company_b = _auth(client)
    _enable_domains(db_session, company_a)
    _enable_domains(db_session, company_b)

    create = client.post(
        "/api/v1/domains/",
        json={"hostname": f"chat.{uuid.uuid4().hex[:6]}.iso-a.com"},
        headers=headers_a,
    )
    assert create.status_code == 201
    domain_id = create.json()["id"]

    other = client.get(f"/api/v1/domains/{domain_id}", headers=headers_b)
    assert other.status_code == 404


# ── CORS ──────────────────────────────────────────────────────────────────────

def test_cors_cache_includes_verified_origin(db_session):
    invalidate_cors_cache()
    company_slug = f"cors-{uuid.uuid4().hex[:6]}"
    # Minimal insert via service after creating company through ORM if needed —
    # use UsageService plan + DomainService with mock company exists
    from app.companies.model import Company, CompanyPlan, CompanyStatus
    from app.domains.models import CompanyDomain, DomainVerificationMethod, SslStatus
    from app.domains.service import generate_verification_token, build_dns_records

    company = Company(
        name="CORS Co",
        slug=company_slug,
        plan=CompanyPlan.STARTER,
        status=CompanyStatus.ACTIVE,
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)

    UsageService(db_session).apply_plan_limits(company.id, "starter", emit_upgraded=False)
    token = generate_verification_token()
    hostname = f"live.{uuid.uuid4().hex[:6]}.cors.test"
    domain = CompanyDomain(
        company_id=company.id,
        hostname=hostname,
        status=DomainStatus.LIVE,
        verification_method=DomainVerificationMethod.TXT,
        verification_token=token,
        dns_records=build_dns_records(hostname, token, "TXT"),
        ssl_status=SslStatus.ISSUED.value,
        cors_origin=f"https://{hostname}",
    )
    db_session.add(domain)
    db_session.commit()

    invalidate_cors_cache()
    origins = get_cached_cors_origins(db_session)
    assert f"https://{hostname}" in origins


def test_dynamic_cors_middleware_allows_static_origin():
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    async def homepage(request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", homepage)])
    app.add_middleware(DynamicCORSMiddleware)

    with patch("app.config.settings.settings") as s:
        s.CORS_ORIGINS = ["https://app.example.com"]
        # Re-import path uses settings module — patch get_cached to empty
        with patch("app.domains.cors.settings") as cs:
            cs.CORS_ORIGINS = ["https://app.example.com"]
            with patch("app.domains.service.get_cached_cors_origins", return_value=["https://app.example.com"]):
                client = TestClient(app)
                resp = client.options(
                    "/",
                    headers={
                        "Origin": "https://app.example.com",
                        "Access-Control-Request-Method": "GET",
                    },
                )
                assert resp.status_code == 200
                assert resp.headers.get("access-control-allow-origin") == "https://app.example.com"


def test_dashboard_endpoint(client, db_session):
    headers, company_id = _auth(client)
    _enable_domains(db_session, company_id)
    client.post(
        "/api/v1/domains/",
        json={"hostname": f"www.{uuid.uuid4().hex[:6]}.dash.com"},
        headers=headers,
    )
    resp = client.get("/api/v1/domains/dashboard", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["domains_used"] >= 1
    assert "add_domain" in body["instructions"]
