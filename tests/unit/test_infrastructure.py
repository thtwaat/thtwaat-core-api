"""Unit smoke — infrastructure must run with zero Docker services."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_sqlite_session_lifecycle(unit_db_session):
    row = unit_db_session.execute(__import__("sqlalchemy").text("SELECT 1")).scalar()
    assert row == 1


def test_fake_redis_roundtrip(fake_redis):
    fake_redis.set("thtwaat:unit:ping", "pong")
    assert fake_redis.get("thtwaat:unit:ping") == "pong"


def test_tmp_storage_isolated(tmp_storage):
    target = tmp_storage / "note.txt"
    target.write_text("ok", encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "ok"


def test_payment_mock_succeeds(mock_payments):
    result = mock_payments.process_payment(amount=1.0, currency="USD", method="card", metadata={})
    assert result.success is True
    assert result.transaction_id


def test_rbac_permission_enum_nonempty():
    from app.rbac.enums import Permission

    assert len(list(Permission)) > 5
