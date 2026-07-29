"""White-label branding — unit + API integration tests."""
from __future__ import annotations

import io
import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.branding.assets import validate_brand_upload
from app.branding.defaults import css_variables_from, default_branding_kwargs, snapshot_from_row
from app.branding.email import render_branded_email
from app.branding.models import BrandingAssetType
from app.branding.schemas import BrandingUpdate


def _auth(client, role: str = "admin"):
    company_slug = f"brand-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": "Brand Co", "slug": company_slug, "display_name": "Brand Co"},
    )
    assert company_resp.status_code in (200, 201), company_resp.text
    company_id = company_resp.json()["id"]

    email = f"brand-{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword"
    user_resp = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": password,
            "company_id": company_id,
            "first_name": "Brand",
            "last_name": "Owner",
            "role": role,
        },
    )
    assert user_resp.status_code in (200, 201), user_resp.text

    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, company_id, company_slug


def test_default_branding_kwargs_and_css():
    raw = default_branding_kwargs("Acme")
    assert raw["company_name"] == "Acme"
    assert "welcome" in raw["email"]["templates"]
    css = css_variables_from(raw)
    assert css["--brand-primary"].startswith("#")
    assert "Inter" in css["--brand-font"]


def test_snapshot_from_row_shape():
    row = SimpleNamespace(
        company_name="X",
        copyright_text="c",
        footer_text="f",
        primary_color="#111111",
        secondary_color="#222222",
        accent_color="#333333",
        font_family="Serif",
        heading_font=None,
        dashboard_theme="dark",
        login_background_url=None,
        logo_url="https://cdn/logo.png",
        dark_logo_url=None,
        favicon_url=None,
        email={"sender_name": "X"},
        mobile={"app_name": "X App"},
        widget={"bubble_color": "#111111"},
        domain_roles={"app": "app.x.com"},
    )
    snap = snapshot_from_row(row)
    assert snap["logo_url"].endswith("logo.png")
    assert snap["domain_roles"]["app"] == "app.x.com"
    assert "draft_version" not in snap


def test_branding_update_schema_rejects_bad_theme():
    with pytest.raises(ValidationError):
        BrandingUpdate(dashboard_theme="neon")


def test_branding_update_normalizes_color():
    body = BrandingUpdate(primary_color="0ea5e9")
    assert body.primary_color == "#0EA5E9"


@pytest.mark.asyncio
async def test_validate_brand_upload_rejects_bad_mime():
    class FakeUpload:
        content_type = "application/pdf"

        async def read(self):
            return b"%PDF"

        async def seek(self, *_args, **_kwargs):
            return None

    with pytest.raises(Exception) as exc:
        await validate_brand_upload(FakeUpload(), BrandingAssetType.LOGO)
    assert getattr(exc.value, "status_code", None) in (415, None) or "Unsupported" in str(exc.value)


def test_render_branded_email_uses_service(monkeypatch):
    class FakeSvc:
        def __init__(self, db):
            pass

        def resolve_email_context(self, company_id):
            return {
                "company_name": "Acme",
                "sender_name": "Acme",
                "sender_email": "hi@acme.test",
                "logo_url": None,
                "primary_color": "#0F766E",
                "templates": {"welcome": "Hello {{company_name}}"},
                "footer": "Acme",
                "copyright": "© Acme",
            }

    monkeypatch.setattr("app.branding.service.BrandingService", FakeSvc)
    out = render_branded_email(db=None, company_id=uuid.uuid4(), template_key="welcome")
    assert out["body"] == "Hello Acme"
    assert out["sender_email"] == "hi@acme.test"


@pytest.mark.integration
def test_get_patch_preview_publish_reset(client):
    headers, company_id, slug = _auth(client)

    got = client.get("/api/v1/branding", headers=headers)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["company_id"] == company_id
    assert body["primary_color"]
    assert body["is_published"] is False

    patched = client.patch(
        "/api/v1/branding",
        headers=headers,
        json={
            "company_name": "Acme AI",
            "primary_color": "#0EA5E9",
            "secondary_color": "#0369A1",
            "accent_color": "#F97316",
            "dashboard_theme": "dark",
            "copyright_text": "© Acme AI",
            "footer_text": "Powered by Acme",
            "email": {
                "sender_name": "Acme Support",
                "sender_email": "hello@acme.test",
                "templates": {"welcome": "Hi from {{company_name}}"},
            },
            "mobile": {
                "app_name": "Acme Mobile",
                "android_package": "com.acme.app",
                "ios_bundle_id": "com.acme.app",
            },
            "widget": {
                "chat_theme": "dark",
                "bubble_color": "#0EA5E9",
                "suggested_prompts": ["Hello", "Pricing"],
            },
            "domain_roles": {
                "app": "app.acme.test",
                "api": "api.acme.test",
                "chat": "chat.acme.test",
            },
        },
    )
    assert patched.status_code == 200, patched.text
    data = patched.json()
    assert data["company_name"] == "Acme AI"
    assert data["primary_color"] == "#0EA5E9"
    assert data["email"]["sender_email"] == "hello@acme.test"
    assert data["mobile"]["android_package"] == "com.acme.app"
    assert data["widget"]["suggested_prompts"] == ["Hello", "Pricing"]
    assert data["domain_roles"]["chat"] == "chat.acme.test"
    assert data["draft_version"] >= 2

    preview = client.get("/api/v1/branding/preview", headers=headers)
    assert preview.status_code == 200, preview.text
    prev = preview.json()
    assert prev["css_variables"]["--brand-primary"] == "#0EA5E9"
    assert "Hello" in prev["widget_preview"]["suggested_prompts"]
    assert any(d.get("hostname") == "app.acme.test" for d in prev["domains"])

    published = client.post("/api/v1/branding/publish", headers=headers)
    assert published.status_code == 200, published.text
    pub = published.json()
    assert pub["published_version"] >= 1
    assert pub["branding"]["is_published"] is True

    public = client.get(f"/public/v1/branding?slug={slug}")
    assert public.status_code == 200, public.text
    pub_body = public.json()
    assert pub_body["branding"]["company_name"] == "Acme AI"
    assert pub_body["css_variables"]["--brand-primary"] == "#0EA5E9"

    reset = client.post("/api/v1/branding/reset", headers=headers)
    assert reset.status_code == 200, reset.text
    still = client.get(f"/public/v1/branding?slug={slug}")
    assert still.status_code == 200
    assert still.json()["branding"]["company_name"] == "Acme AI"


@pytest.mark.integration
def test_upload_logo_asset(client):
    headers, company_id, _ = _auth(client)
    assert client.get("/api/v1/branding", headers=headers).status_code == 200

    png_header = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    files = {"file": ("logo.png", io.BytesIO(png_header), "image/png")}
    data = {"asset_type": BrandingAssetType.LOGO.value}
    resp = client.post(
        "/api/v1/branding/assets",
        headers=headers,
        data=data,
        files=files,
    )
    assert resp.status_code == 201, resp.text
    asset = resp.json()
    assert asset["asset_type"] == "logo"
    assert asset["version"] == 1
    assert asset["url"]

    branding = client.get("/api/v1/branding", headers=headers).json()
    assert branding["logo_url"] == asset["url"]


@pytest.mark.integration
def test_public_branding_requires_selector(client):
    resp = client.get("/public/v1/branding")
    assert resp.status_code == 400
