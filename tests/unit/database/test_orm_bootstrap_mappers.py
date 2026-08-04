"""Regression: Company.relationship('User') must resolve after ORM bootstrap."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_register_orm_models_configures_company_user_mappers():
    from sqlalchemy.orm import configure_mappers

    from app.database.orm_bootstrap import register_orm_models

    register_orm_models()
    configure_mappers()  # must not raise InvalidRequestError for User

    from app.companies.model import Company
    from app.users.model import User

    assert Company.__mapper__.relationships["users"].mapper.class_ is User
    assert User.__mapper__.relationships["company"].mapper.class_ is Company


def test_seed_loader_import_does_not_eager_load_company(monkeypatch):
    """Marketplace seed_loader must not import MarketplaceService at module level.

    Eager import pulls UsageService → CompanyRepository → Company without User,
    which is the production InvalidRequestError on seed CLI / boot.
    """
    src = (ROOT / "app" / "marketplace" / "seed_loader.py").read_text(encoding="utf-8")
    assert "from app.marketplace.service import MarketplaceService" in src
    # Only inside a function (lazy), not as a top-level binding used at import time.
    assert "def _marketplace_service" in src
    # Top-level should not instantiate service via bare MarketplaceService(db)
    assert "service = MarketplaceService(db)" not in src


def test_orm_bootstrap_imports_user_before_company():
    src = (ROOT / "app" / "database" / "orm_bootstrap.py").read_text(encoding="utf-8")
    assert src.index("import app.users.model") < src.index("import app.companies.model")
    assert "configure_mappers()" in src


def test_seed_cli_registers_orm_before_marketplace_seed_import():
    src = (ROOT / "scripts" / "seed_marketplace.py").read_text(encoding="utf-8")
    assert src.index("register_orm_models") < src.index("seed_marketplace_catalog")


def test_subprocess_seed_bootstrap_configures_mappers():
    """Fresh interpreter: register_orm_models then import seed + configure_mappers."""
    code = r"""
from app.database.orm_bootstrap import register_orm_models
register_orm_models()
from app.marketplace.seed import seed_marketplace_catalog  # noqa: F401
from sqlalchemy.orm import configure_mappers
configure_mappers()
from app.companies.model import Company
from app.users.model import User
assert Company.__mapper__.relationships["users"].mapper.class_ is User
print("OK")
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": str(ROOT)},
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout


def test_alembic_env_imports_user_before_company():
    src = (ROOT / "alembic" / "env.py").read_text(encoding="utf-8")
    assert src.index("import app.users.model") < src.index("import app.companies.model")
