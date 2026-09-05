"""Unit tests for scripts/break_glass_reset_password.py.

Focus areas per the break-glass CLI's safety contract:
  1. wrong/missing break-glass token aborts
  2. wrong UUID identity/email/company/role aborts before any write
  3. correct target allows the reset to proceed
  4. only the target user's refresh tokens are revoked
  5. the password never appears in stdout/stderr
  6. the password hash is produced through AuthService's existing bcrypt method
  7. the confirmation phrase is required before any DB mutation
"""
from __future__ import annotations

import hashlib
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.database.orm_bootstrap import register_orm_models

register_orm_models()

from app.rbac.enums import EnterpriseRole

import scripts.break_glass_reset_password as mod
from scripts.break_glass_reset_password import (
    CONFIRMATION_PHRASE,
    ENV_BREAK_GLASS_TOKEN,
    ENV_BREAK_GLASS_TOKEN_SHA256,
    EXPECTED_COMPANY_SLUG,
    EXPECTED_EMAIL,
    EXPECTED_ROLE,
    EXPECTED_USER_ID,
    BreakGlassError,
    confirm_execution,
    load_and_verify_target,
    main,
    perform_break_glass_reset,
    read_new_password,
    verify_break_glass_token,
)

OLD_HASH = "old-bcrypt-hash-marker"


def _fail(message: str):
    def _raise(*_args, **_kwargs):
        raise AssertionError(message)

    return _raise


def _valid_user_and_company():
    company_id = uuid.uuid4()
    company = SimpleNamespace(id=company_id, slug=EXPECTED_COMPANY_SLUG)
    user = SimpleNamespace(
        id=EXPECTED_USER_ID,
        email=EXPECTED_EMAIL,
        company_id=company_id,
        role=EXPECTED_ROLE,
        hashed_password=OLD_HASH,
    )
    return user, company


def _make_db(user=None, company=None):
    from app.companies.model import Company
    from app.users.model import User

    def _get(model, id_):
        if model is User:
            return user if (user is not None and id_ == user.id) else None
        if model is Company:
            return company if (company is not None and id_ == company.id) else None
        return None

    db = MagicMock()
    db.get.side_effect = _get
    return db


def _set_valid_token_env(monkeypatch, token: str = "correct-break-glass-token"):
    monkeypatch.setenv(ENV_BREAK_GLASS_TOKEN, token)
    monkeypatch.setenv(ENV_BREAK_GLASS_TOKEN_SHA256, hashlib.sha256(token.encode("utf-8")).hexdigest())


def _stub_session(monkeypatch, db):
    monkeypatch.setattr("app.database.database.SessionLocal", lambda: db)


# ── 1. wrong/missing break-glass token aborts ────────────────────────────────


def test_verify_break_glass_token_missing_supplied():
    expected = hashlib.sha256(b"whatever").hexdigest()
    assert verify_break_glass_token(None, expected) is False
    assert verify_break_glass_token("", expected) is False


def test_verify_break_glass_token_missing_expected_hash():
    assert verify_break_glass_token("some-token", None) is False
    assert verify_break_glass_token("some-token", "") is False


def test_verify_break_glass_token_wrong_value():
    expected = hashlib.sha256(b"correct-token").hexdigest()
    assert verify_break_glass_token("wrong-token", expected) is False


def test_verify_break_glass_token_correct_value():
    expected = hashlib.sha256(b"correct-token").hexdigest()
    assert verify_break_glass_token("correct-token", expected) is True


def test_main_aborts_when_token_env_vars_missing(monkeypatch, capsys):
    monkeypatch.delenv(ENV_BREAK_GLASS_TOKEN, raising=False)
    monkeypatch.delenv(ENV_BREAK_GLASS_TOKEN_SHA256, raising=False)

    rc = main()

    assert rc == 1
    assert "BREAK_GLASS_TOKEN" in capsys.readouterr().out


def test_main_aborts_when_token_present_but_expected_hash_missing(monkeypatch, capsys):
    monkeypatch.setenv(ENV_BREAK_GLASS_TOKEN, "some-token")
    monkeypatch.delenv(ENV_BREAK_GLASS_TOKEN_SHA256, raising=False)

    rc = main()

    assert rc == 1


def test_main_aborts_when_token_wrong_never_touches_session(monkeypatch, capsys):
    monkeypatch.setenv(ENV_BREAK_GLASS_TOKEN, "wrong-token")
    monkeypatch.setenv(ENV_BREAK_GLASS_TOKEN_SHA256, hashlib.sha256(b"correct-token").hexdigest())
    # If the token check is bypassed, this would blow up instead of a clean 1.
    monkeypatch.setattr("app.database.database.SessionLocal", _fail("must not open a DB session"))

    rc = main()

    assert rc == 1


# ── 2. wrong UUID identity/email/company/role aborts before any write ───────


def test_load_and_verify_target_user_not_found():
    db = _make_db(user=None, company=None)
    with pytest.raises(BreakGlassError):
        load_and_verify_target(db)


def test_load_and_verify_target_email_mismatch():
    user, company = _valid_user_and_company()
    user.email = "someone-else@example.com"
    db = _make_db(user=user, company=company)
    with pytest.raises(BreakGlassError):
        load_and_verify_target(db)


def test_load_and_verify_target_company_slug_mismatch():
    user, company = _valid_user_and_company()
    company.slug = "not-tts"
    db = _make_db(user=user, company=company)
    with pytest.raises(BreakGlassError):
        load_and_verify_target(db)


def test_load_and_verify_target_missing_company_row():
    user, _company = _valid_user_and_company()
    db = _make_db(user=user, company=None)
    with pytest.raises(BreakGlassError):
        load_and_verify_target(db)


def test_load_and_verify_target_role_mismatch():
    user, company = _valid_user_and_company()
    user.role = EnterpriseRole.ADMIN
    db = _make_db(user=user, company=company)
    with pytest.raises(BreakGlassError):
        load_and_verify_target(db)


def test_load_and_verify_target_success_returns_user():
    user, company = _valid_user_and_company()
    db = _make_db(user=user, company=company)
    result = load_and_verify_target(db)
    assert result is user


def test_main_aborts_before_write_when_identity_does_not_match(monkeypatch, capsys):
    _set_valid_token_env(monkeypatch)
    db = _make_db(user=None, company=None)  # no matching row
    _stub_session(monkeypatch, db)
    monkeypatch.setattr(mod, "confirm_execution", _fail("confirmation must not be reached"))
    monkeypatch.setattr(mod, "read_new_password", _fail("password read must not be reached"))

    rc = main()

    assert rc == 1
    assert db.commit.call_count == 0
    assert "Aborting before any write" in capsys.readouterr().out


# ── 3. correct target allows the reset to proceed ────────────────────────────


def test_main_full_success_path(monkeypatch):
    _set_valid_token_env(monkeypatch)
    user, company = _valid_user_and_company()
    db = _make_db(user=user, company=company)
    _stub_session(monkeypatch, db)
    monkeypatch.setattr(mod, "confirm_execution", lambda: True)
    monkeypatch.setattr(mod, "read_new_password", lambda: "OperatorChosenPassw0rd!")

    rc = main()

    assert rc == 0
    assert user.hashed_password != OLD_HASH
    db.commit.assert_called()


# ── 4. only the target user's refresh tokens are revoked ────────────────────


def test_perform_break_glass_reset_scopes_delete_to_target_user_id():
    user, _company = _valid_user_and_company()
    db = MagicMock()

    perform_break_glass_reset(db, user, "AnotherValidPassw0rd!")

    assert db.execute.call_count == 1
    stmt = db.execute.call_args[0][0]
    compiled = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "refresh_tokens" in compiled
    assert str(user.id) in compiled


def test_perform_break_glass_reset_delete_is_specific_to_each_user():
    user_a, _ = _valid_user_and_company()
    user_b = SimpleNamespace(
        id=uuid.uuid4(),
        email="unrelated@example.com",
        company_id=uuid.uuid4(),
        hashed_password="unrelated-hash",
    )
    db_a, db_b = MagicMock(), MagicMock()

    perform_break_glass_reset(db_a, user_a, "SomeValidPassw0rd!")
    perform_break_glass_reset(db_b, user_b, "SomeValidPassw0rd!")

    compiled_a = str(
        db_a.execute.call_args[0][0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    compiled_b = str(
        db_b.execute.call_args[0][0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    assert str(user_a.id) in compiled_a
    assert str(user_b.id) in compiled_b
    assert str(user_a.id) not in compiled_b
    assert str(user_b.id) not in compiled_a


# ── 5. the password never appears in stdout/stderr ───────────────────────────


def test_main_success_path_never_prints_password_or_hashes(monkeypatch, capsys):
    _set_valid_token_env(monkeypatch)
    user, company = _valid_user_and_company()
    db = _make_db(user=user, company=company)
    _stub_session(monkeypatch, db)
    monkeypatch.setattr(mod, "confirm_execution", lambda: True)
    secret_password = "SuperSecretOperatorPassw0rd!"
    monkeypatch.setattr(mod, "read_new_password", lambda: secret_password)

    rc = main()

    assert rc == 0
    combined = "".join(capsys.readouterr())
    assert secret_password not in combined
    assert OLD_HASH not in combined
    assert user.hashed_password not in combined


def test_read_new_password_returns_value_without_printing(capsys):
    values = iter(["Sup3rSecret!", "Sup3rSecret!"])
    password = read_new_password(reader=lambda _prompt: next(values))
    assert password == "Sup3rSecret!"
    captured = capsys.readouterr()
    assert "Sup3rSecret!" not in captured.out
    assert "Sup3rSecret!" not in captured.err


def test_read_new_password_rejects_mismatch_without_leaking_attempts(capsys):
    values = iter(["first-try-1", "does-not-match", "Sup3rSecret!", "Sup3rSecret!"])
    password = read_new_password(reader=lambda _prompt: next(values))
    assert password == "Sup3rSecret!"
    captured = capsys.readouterr()
    assert "do not match" in captured.out
    assert "first-try-1" not in captured.out
    assert "does-not-match" not in captured.out


# ── 6. the hash is produced through AuthService's existing bcrypt method ────


def test_perform_break_glass_reset_produces_a_real_verifiable_bcrypt_hash():
    from app.auth.service import AuthService

    user, _company = _valid_user_and_company()
    db = MagicMock()
    new_password = "RoundTripPassw0rd!"

    perform_break_glass_reset(db, user, new_password)

    assert user.hashed_password != OLD_HASH
    assert AuthService.verify_password(new_password, user.hashed_password) is True
    assert AuthService.verify_password("WrongPassword!", user.hashed_password) is False


def test_perform_break_glass_reset_calls_authservice_get_password_hash(monkeypatch):
    from app.auth.service import AuthService

    calls = []

    def _fake_hash(password: str) -> str:
        calls.append(password)
        return "MARKER-HASH-FROM-AUTHSERVICE"

    monkeypatch.setattr(AuthService, "get_password_hash", staticmethod(_fake_hash))

    user, _company = _valid_user_and_company()
    db = MagicMock()

    perform_break_glass_reset(db, user, "WhateverPassw0rd!")

    assert calls == ["WhateverPassw0rd!"]
    assert user.hashed_password == "MARKER-HASH-FROM-AUTHSERVICE"


# ── 7. confirmation is required before any DB mutation ──────────────────────


def test_confirm_execution_true_on_exact_match():
    assert confirm_execution(reader=lambda _prompt: CONFIRMATION_PHRASE) is True


@pytest.mark.parametrize(
    "typed",
    ["", "break glass reset thtwaat platform admin", "yes", CONFIRMATION_PHRASE + " "],
)
def test_confirm_execution_false_on_any_mismatch(typed):
    assert confirm_execution(reader=lambda _prompt: typed) is False


def test_main_aborts_when_confirmation_phrase_wrong(monkeypatch, capsys):
    _set_valid_token_env(monkeypatch)
    user, company = _valid_user_and_company()
    db = _make_db(user=user, company=company)
    _stub_session(monkeypatch, db)
    monkeypatch.setattr(mod, "confirm_execution", lambda: False)
    monkeypatch.setattr(mod, "read_new_password", _fail("password read must not be reached"))

    rc = main()

    assert rc == 1
    assert db.commit.call_count == 0
    assert user.hashed_password == OLD_HASH
    assert "Aborting before any write" in capsys.readouterr().out


def test_main_confirmation_runs_only_after_successful_identity_check(monkeypatch):
    """Regression guard: confirmation must come after identity verification,
    not before — an identity failure must never even prompt for confirmation."""
    _set_valid_token_env(monkeypatch)
    db = _make_db(user=None, company=None)
    _stub_session(monkeypatch, db)
    called = {"confirm": False}

    def _record_confirm():
        called["confirm"] = True
        return True

    monkeypatch.setattr(mod, "confirm_execution", _record_confirm)
    monkeypatch.setattr(mod, "read_new_password", _fail("password read must not be reached"))

    rc = main()

    assert rc == 1
    assert called["confirm"] is False
