"""Phase 5: idempotent seed loader + SQL artifacts."""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.marketplace.models import MarketplaceTemplate, TemplateVersion
from app.marketplace.seed import seed_marketplace_catalog
from app.marketplace.seed_loader import (
    load_prompt_seed_docs,
    prompt_doc_to_create,
    seed_prompt_templates,
    upsert_prompt_doc,
)
from app.marketplace.service import MarketplaceService

ROOT = Path(__file__).resolve().parents[3]
SQL_DIR = ROOT / "data" / "marketplace" / "sql"


def test_prompt_docs_map_to_template_create():
    docs = load_prompt_seed_docs()
    assert len(docs) == 100
    payload = prompt_doc_to_create(docs[0])
    assert payload.kind in {"prompt", "agent"}
    assert payload.default_config["prompt"]
    assert payload.default_config["variables"]
    assert "temperature" in payload.default_config


def test_sql_seed_artifacts_exist_and_mention_conflict():
    seed_sql = SQL_DIR / "001_seed_prompt_templates.sql"
    upgrade_sql = SQL_DIR / "002_upgrade_prompt_templates.sql"
    rollback_sql = SQL_DIR / "900_rollback_prompt_seeds.sql"
    assert seed_sql.exists(), "run: python scripts/generate_marketplace_seed_sql.py"
    assert upgrade_sql.exists()
    assert rollback_sql.exists()
    text = seed_sql.read_text(encoding="utf-8")
    assert "ON CONFLICT (slug) DO UPDATE" in text
    assert "BEGIN;" in text and "COMMIT;" in text
    rollback = rollback_sql.read_text(encoding="utf-8")
    assert "DELETE FROM marketplace_templates" in rollback
    assert "writing-blog-outline" in rollback


def test_seed_prompt_templates_idempotent(db_session):
    first = seed_prompt_templates(db_session, refresh_same_version=False)
    assert first.created == 100
    assert first.upgraded == 0

    second = seed_prompt_templates(db_session, refresh_same_version=False)
    assert second.created == 0
    assert second.skipped == 100

    sample = db_session.query(MarketplaceTemplate).filter_by(slug="writing-blog-outline").one()
    assert sample.kind.value == "prompt"
    assert sample.default_config.get("prompt")
    versions = (
        db_session.query(TemplateVersion)
        .filter(TemplateVersion.template_id == sample.id)
        .all()
    )
    assert len(versions) == 1
    assert versions[0].is_latest is True


def test_seed_prompt_upgrade_adds_version(db_session, tmp_path):
    docs = load_prompt_seed_docs()
    doc = dict(docs[0])
    service = MarketplaceService(db_session)
    assert upsert_prompt_doc(service, doc) == "created"

    upgraded = dict(doc)
    upgraded["version"] = "1.1.0"
    upgraded["description"] = "Upgraded description"
    upgraded["prompt"] = doc["prompt"] + "\n# v1.1"
    assert upsert_prompt_doc(service, upgraded, upgrade=True) == "upgraded"

    row = db_session.query(MarketplaceTemplate).filter_by(slug=doc["slug"]).one()
    assert row.version == "1.1.0"
    assert "v1.1" in row.default_config["prompt"]
    vers = (
        db_session.query(TemplateVersion)
        .filter(TemplateVersion.template_id == row.id)
        .order_by(TemplateVersion.version)
        .all()
    )
    assert {v.version for v in vers} == {"1.0.0", "1.1.0"}
    assert sum(1 for v in vers if v.is_latest) == 1


def test_seed_marketplace_catalog_packages_only(db_session):
    from app.marketplace.seed_loader import load_package_seed_docs

    expected = len(load_package_seed_docs())
    stats = seed_marketplace_catalog(
        db_session,
        include_packages=True,
        include_prompts=False,
        refresh_same_version=False,
    )
    assert stats.created == expected
    again = seed_marketplace_catalog(
        db_session,
        include_packages=True,
        include_prompts=False,
        refresh_same_version=False,
    )
    assert again.created == 0
    assert again.skipped == expected


def test_stable_seed_uuid_used(db_session):
    docs = load_prompt_seed_docs()
    doc = next(d for d in docs if d["slug"] == "finance-expense-summary")
    service = MarketplaceService(db_session)
    upsert_prompt_doc(service, doc)
    row = db_session.query(MarketplaceTemplate).filter_by(slug=doc["slug"]).one()
    assert row.id == UUID(doc["id"])
