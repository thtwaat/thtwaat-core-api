"""Marketplace catalog auto-load (fixes empty Browse when seeds were never applied)."""
from __future__ import annotations

from pathlib import Path

from app.config.settings import settings
from app.marketplace.seed import REQUIRED_PACKAGE_SLUGS, get_seed_templates
from app.marketplace.seed_loader import load_package_seed_docs, load_prompt_seed_docs


ROOT = Path(__file__).resolve().parents[3]


def test_auto_seed_setting_defaults_on():
    assert settings.MARKETPLACE_AUTO_SEED_ON_STARTUP is True
    assert settings.MARKETPLACE_AUTO_SEED_REFRESH_SAME_VERSION is False


def test_on_disk_catalog_matches_browse_expectations():
    """Seeds exist and are public/published — production emptiness is a load gap, not missing files."""
    prompts = load_prompt_seed_docs()
    packages = load_package_seed_docs()
    assert len(prompts) == 100
    assert len(packages) >= len(REQUIRED_PACKAGE_SLUGS)
    assert all((p.get("visibility") or "public") == "public" for p in prompts)
    assert all(bool(p.get("publish", True)) for p in packages)
    assert all(p.get("kind") == "package" for p in packages)
    assert {p["slug"] for p in packages} >= set(REQUIRED_PACKAGE_SLUGS)
    assert len(get_seed_templates()) == len(packages)


def test_dockerfile_and_compose_run_seed_after_alembic():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    assert "scripts.seed_marketplace" in dockerfile
    assert "alembic upgrade head" in dockerfile
    assert "scripts.seed_marketplace" in compose
    assert "alembic upgrade head" in compose


def test_dockerignore_keeps_marketplace_seed_catalog():
    """Production Browse empty when `data/` is blanket-ignored from the image."""
    text = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    ignored = {
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#") and not line.strip().startswith("!")
    }
    assert "data/" not in ignored
    assert "data/uploads/" in ignored or "data/uploads" in ignored
    assert (ROOT / "data" / "marketplace" / "seeds" / "packages" / "index.json").exists()
    assert (ROOT / "data" / "marketplace" / "seeds" / "index.json").exists()


def test_ensure_marketplace_catalog_seeded_exportable():
    from app.marketplace.seed import ensure_marketplace_catalog_seeded

    assert callable(ensure_marketplace_catalog_seeded)


def test_main_lifespan_wires_auto_seed():
    main_src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "MARKETPLACE_AUTO_SEED_ON_STARTUP" in main_src
    assert "ensure_marketplace_catalog_seeded" in main_src


def test_seed_marketplace_cli_registers_orm_before_session():
    src = (ROOT / "scripts" / "seed_marketplace.py").read_text(encoding="utf-8")
    assert "register_orm_models" in src
    # Must register before SessionLocal / marketplace seed import.
    assert src.index("register_orm_models") < src.index("SessionLocal")
    assert src.index("register_orm_models") < src.index("seed_marketplace_catalog")
