"""Package starter seeds + Product Generator assemble dependency."""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.marketplace.models import MarketplaceTemplate, TemplateKind
from app.marketplace.seed import REQUIRED_PACKAGE_SLUGS, seed_marketplace_catalog
from app.marketplace.seed_loader import (
    load_package_seed_docs,
    package_doc_to_create,
    seed_package_templates,
)
from app.product_generator.analyzer import analyze_prompt
from app.product_generator.service import PACKAGE_TEMPLATE_MISSING, ProductGeneratorService

ROOT = Path(__file__).resolve().parents[3]
SQL_DIR = ROOT / "data" / "marketplace" / "sql"
PACKAGES_DIR = ROOT / "data" / "marketplace" / "seeds" / "packages"


def test_required_package_slugs_present_in_json_catalog():
    docs = load_package_seed_docs()
    slugs = {d["slug"] for d in docs}
    assert REQUIRED_PACKAGE_SLUGS.issubset(slugs)
    assert len(docs) >= len(REQUIRED_PACKAGE_SLUGS)
    for doc in docs:
        payload = package_doc_to_create(doc)
        assert payload.kind == "package"
        assert payload.package_path
        assert payload.publish is True


def test_package_sql_seed_artifacts_exist():
    seed_sql = SQL_DIR / "010_seed_package_templates.sql"
    upgrade_sql = SQL_DIR / "011_upgrade_package_templates.sql"
    rollback_sql = SQL_DIR / "910_rollback_package_seeds.sql"
    assert seed_sql.exists()
    assert upgrade_sql.exists()
    assert rollback_sql.exists()
    text = seed_sql.read_text(encoding="utf-8")
    assert "ON CONFLICT (slug) DO UPDATE" in text
    assert "ai-website-starter" in text
    assert "hotel-website-starter" in text
    assert "landing-page-starter" in text
    rollback = rollback_sql.read_text(encoding="utf-8")
    assert "DELETE FROM marketplace_templates" in rollback
    assert "ecommerce-starter" in rollback


def test_seed_package_templates_idempotent(db_session):
    first = seed_package_templates(db_session, refresh_same_version=False)
    assert first.created >= len(REQUIRED_PACKAGE_SLUGS)
    assert first.created == len(load_package_seed_docs())

    second = seed_package_templates(db_session, refresh_same_version=False)
    assert second.created == 0
    assert second.skipped == first.created

    hotel = db_session.query(MarketplaceTemplate).filter_by(slug="hotel-website-starter").one()
    assert hotel.kind == TemplateKind.PACKAGE
    assert hotel.industry == "hotel"
    assert hotel.package_path == "apps/templates/website"
    assert hotel.id == UUID("c7d0f642-b3e9-5be5-9f1d-d760a03017f1")


def test_seed_marketplace_catalog_packages_only(db_session):
    docs = load_package_seed_docs()
    stats = seed_marketplace_catalog(
        db_session,
        include_packages=True,
        include_prompts=False,
        refresh_same_version=False,
    )
    assert stats.created == len(docs)
    again = seed_marketplace_catalog(
        db_session,
        include_packages=True,
        include_prompts=False,
        refresh_same_version=False,
    )
    assert again.created == 0
    assert again.skipped == len(docs)


def test_product_generator_discovers_hotel_package(db_session):
    seed_package_templates(db_session)
    analysis = analyze_prompt("Hotel website with AI concierge and room booking")
    assert analysis.industry == "hotel"
    svc = ProductGeneratorService(db_session)
    picked = svc._pick_template(analysis.category, None, industry=analysis.industry)
    assert picked is not None
    assert picked.slug == "hotel-website-starter"


def test_product_generator_discovers_restaurant_package(db_session):
    seed_package_templates(db_session)
    analysis = analyze_prompt("Restaurant website with AI ordering and table booking")
    svc = ProductGeneratorService(db_session)
    picked = svc._pick_template(analysis.category, None, industry=analysis.industry)
    assert picked is not None
    assert picked.slug == "restaurant-starter"


def test_generate_missing_package_returns_structured_error(client, db_session):
    import uuid

    company_slug = f"pkg-miss-{uuid.uuid4().hex[:8]}"
    company_resp = client.post(
        "/api/v1/companies/",
        json={"name": "Missing Packages Co", "slug": company_slug},
    )
    assert company_resp.status_code in (200, 201), company_resp.text
    company_id = company_resp.json()["id"]

    email = f"owner-{uuid.uuid4().hex[:8]}@example.com"
    user_resp = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": "securepassword",
            "company_id": company_id,
            "first_name": "Owner",
            "last_name": "User",
            "role": "admin",
        },
    )
    assert user_resp.status_code in (200, 201), user_resp.text
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword"})
    assert login_resp.status_code == 200, login_resp.text
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    from app.usage.service import UsageService

    UsageService(db_session).apply_plan_limits(uuid.UUID(company_id), "starter", emit_upgraded=False)

    # Intentionally do NOT seed marketplace packages.
    resp = client.post(
        "/api/v1/product-generator/generate",
        json={"prompt": "Hotel website with AI concierge", "auto_publish": False},
        headers=headers,
    )
    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["error"] == PACKAGE_TEMPLATE_MISSING["error"]
    assert body["code"] == PACKAGE_TEMPLATE_MISSING["code"]


def test_packages_index_matches_files():
    index = (PACKAGES_DIR / "index.json").read_text(encoding="utf-8")
    assert "ai-website-starter" in index
    for slug in REQUIRED_PACKAGE_SLUGS:
        assert (PACKAGES_DIR / f"{slug}.json").exists(), slug
