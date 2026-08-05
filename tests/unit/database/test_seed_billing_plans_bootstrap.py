"""Regression: seed_billing_plans CLI must bootstrap ORM before Session queries."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.unit
def test_seed_billing_plans_registers_orm_before_sessionlocal():
    src = (ROOT / "scripts" / "seed_billing_plans.py").read_text(encoding="utf-8")
    assert "register_orm_models" in src
    assert src.index("register_orm_models") < src.index("SessionLocal")
    # Avoid eager Plan import at module top (mirrors seed_marketplace pattern).
    assert "def seed_billing_plans" in src
    top = src.split("def seed_billing_plans", 1)[0]
    assert "from app.payments.plans.model import Plan" not in top


@pytest.mark.unit
def test_seed_billing_plans_function_after_bootstrap():
    from app.database.orm_bootstrap import register_orm_models

    register_orm_models()

    from scripts.seed_billing_plans import seed_billing_plans

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    result = seed_billing_plans(db)
    assert "created" in result
    assert "updated" in result
    db.commit.assert_called_once()


@pytest.mark.unit
def test_subprocess_seed_billing_plans_no_mapper_error():
    """Execute ``python -m scripts.seed_billing_plans`` in a fresh interpreter.

    Mapper bootstrap must succeed. DB connectivity failures are allowed; the
    InvalidRequestError for missing ``User`` mapper must not appear.
    """
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    # Non-routable URL so the test does not depend on Postgres being up.
    env["DATABASE_URL"] = "postgresql://invalid:invalid@127.0.0.1:1/invalid"

    proc = subprocess.run(
        [sys.executable, "-m", "scripts.seed_billing_plans"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert "Mapper[Company(companies)]" not in combined
    assert "failed to locate a name ('User')" not in combined
    assert "expression 'User'" not in combined


@pytest.mark.unit
def test_subprocess_seed_billing_plans_main_with_bootstrapped_seed():
    """Fresh process: register_orm_models then seed_billing_plans with mock Session."""
    code = r"""
from unittest.mock import MagicMock

from app.database.orm_bootstrap import register_orm_models
register_orm_models()

mock_session = MagicMock()
mock_session.query.return_value.filter.return_value.first.return_value = None

from scripts.seed_billing_plans import seed_billing_plans
result = seed_billing_plans(mock_session)
assert isinstance(result, dict)
assert result["created"] + result["updated"] >= 1
print("OK")
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout
    assert "InvalidRequestError" not in proc.stderr
    assert "failed to locate a name" not in proc.stderr
