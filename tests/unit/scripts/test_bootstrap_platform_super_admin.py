"""Unit tests for scripts/bootstrap_platform_super_admin.py.

Focus areas per the bootstrap CLI's safety contract:
  1. wrong/missing bootstrap token aborts (fails closed)
  2. exact company slug/name targeting; mismatch aborts before any write
  3. exact user email/company targeting; wrong role aborts before any write
  4. a newly created user is always role=SUPER_ADMIN / ACTIVE / is_active=True
  5. the password never appears in stdout/stderr
  6. an existing, correct company/user is reused, not recreated
  7. an existing user's password is left untouched without the explicit
     --reset-existing-password flag AND a second confirmation phrase
  8. password reset only happens with both gates satisfied
  9. the primary confirmation phrase is required before any mutation
  10. no DB mutation occurs on any preflight failure
  11. password hashing goes through AuthService.get_password_hash()
  12. refresh-token deletion is scoped to the target user only
  13. the audit event is emitted with the expected event name
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

import scripts.bootstrap_platform_super_admin as mod
from scripts.bootstrap_platform_super_admin import (
    AUDIT_EVENT,
    CONFIRMATION_PHRASE,
    ENV_BOOTSTRAP_TOKEN,
    ENV_BOOTSTRAP_TOKEN_SHA256,
    RESET_CONFIRMATION_PHRASE,
    TARGET_COMPANY_NAME,
    TARGET_COMPANY_SLUG,
    TARGET_EMAIL,
    TARGET_ROLE,
    BootstrapError,
    BootstrapPlan,
    apply_plan,
    build_company_lookup_stmt,
    build_plan,
    build_user_lookup_stmt,
    confirm_execution,
    confirm_reset_execution,
    main,
    read_new_password,
    verify_bootstrap_token,
)

OLD_HASH = "old-bcrypt-hash-marker"


def _fail(message: str):
    def _raise(*_args, **_kwargs):
        raise AssertionError(message)

    return _raise


def _make_company(name=TARGET_COMPANY_NAME, slug=TARGET_COMPANY_SLUG):
    return SimpleNamespace(id=uuid.uuid4(), name=name, slug=slug)


def _make_user(company_id, role=TARGET_ROLE, email=TARGET_EMAIL, hashed_password=OLD_HASH):
    return SimpleNamespace(
        id=uuid.uuid4(),
        company_id=company_id,
        email=email,
        role=role,
        hashed_password=hashed_password,
    )


def _make_db(company=None, user=None):
    """A db whose .execute(stmt).scalar_one_or_none() resolves based on which
    lookup statement was built, keyed off the target table name in the
    compiled SQL -- mirrors how find_company_by_slug/find_user_by_email
    dispatch in the real module."""

    def _execute(stmt):
        compiled = str(stmt)
        result = MagicMock()
        if "companies" in compiled:
            result.scalar_one_or_none.return_value = company
        elif "users" in compiled:
            result.scalar_one_or_none.return_value = user
        else:
            result.scalar_one_or_none.return_value = None
        return result

    db = MagicMock()
    db.execute.side_effect = _execute
    return db


def _set_valid_token_env(monkeypatch, token: str = "correct-bootstrap-token"):
    monkeypatch.setenv(ENV_BOOTSTRAP_TOKEN, token)
    monkeypatch.setenv(ENV_BOOTSTRAP_TOKEN_SHA256, hashlib.sha256(token.encode("utf-8")).hexdigest())


def _stub_session(monkeypatch, db):
    monkeypatch.setattr("app.database.database.SessionLocal", lambda: db)


# ── 1. wrong/missing bootstrap token aborts ──────────────────────────────────


def test_verify_bootstrap_token_missing_supplied():
    expected = hashlib.sha256(b"whatever").hexdigest()
    assert verify_bootstrap_token(None, expected) is False
    assert verify_bootstrap_token("", expected) is False


def test_verify_bootstrap_token_missing_expected_hash():
    assert verify_bootstrap_token("some-token", None) is False
    assert verify_bootstrap_token("some-token", "") is False


def test_verify_bootstrap_token_wrong_value():
    expected = hashlib.sha256(b"correct-token").hexdigest()
    assert verify_bootstrap_token("wrong-token", expected) is False


def test_verify_bootstrap_token_correct_value():
    expected = hashlib.sha256(b"correct-token").hexdigest()
    assert verify_bootstrap_token("correct-token", expected) is True


def test_main_aborts_when_token_env_vars_missing(monkeypatch, capsys):
    monkeypatch.delenv(ENV_BOOTSTRAP_TOKEN, raising=False)
    monkeypatch.delenv(ENV_BOOTSTRAP_TOKEN_SHA256, raising=False)

    rc = main([])

    assert rc == 1
    assert ENV_BOOTSTRAP_TOKEN in capsys.readouterr().out


def test_main_aborts_when_token_wrong_never_touches_session(monkeypatch):
    monkeypatch.setenv(ENV_BOOTSTRAP_TOKEN, "wrong-token")
    monkeypatch.setenv(ENV_BOOTSTRAP_TOKEN_SHA256, hashlib.sha256(b"correct-token").hexdigest())
    monkeypatch.setattr("app.database.database.SessionLocal", _fail("must not open a DB session"))

    rc = main([])

    assert rc == 1


# ── 2/3. exact company/user targeting; mismatches abort before any write ────


def test_build_company_lookup_stmt_targets_exact_slug():
    stmt = build_company_lookup_stmt(TARGET_COMPANY_SLUG)
    compiled = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "companies" in compiled
    assert TARGET_COMPANY_SLUG in compiled


def test_build_user_lookup_stmt_targets_exact_company_and_email():
    company_id = uuid.uuid4()
    stmt = build_user_lookup_stmt(company_id, TARGET_EMAIL)
    compiled = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "users" in compiled
    assert TARGET_EMAIL in compiled
    assert str(company_id) in compiled


def test_build_plan_no_existing_rows_plans_full_create():
    db = _make_db(company=None, user=None)
    plan = build_plan(db)
    assert plan.create_company is True
    assert plan.create_user is True
    assert plan.existing_password_set is False


def test_build_plan_company_name_mismatch_aborts():
    company = _make_company(name="Someone Else's Company")
    db = _make_db(company=company, user=None)
    with pytest.raises(BootstrapError):
        build_plan(db)


def test_build_plan_existing_user_wrong_role_aborts():
    company = _make_company()
    user = _make_user(company.id, role=EnterpriseRole.ADMIN)
    db = _make_db(company=company, user=user)
    with pytest.raises(BootstrapError):
        build_plan(db)


def test_build_plan_correct_existing_company_and_user_reused():
    company = _make_company()
    user = _make_user(company.id, role=TARGET_ROLE)
    db = _make_db(company=company, user=user)

    plan = build_plan(db)

    assert plan.company is company
    assert plan.user is user
    assert plan.create_company is False
    assert plan.create_user is False
    assert plan.existing_password_set is True


def test_main_aborts_before_write_on_company_name_mismatch(monkeypatch, capsys):
    _set_valid_token_env(monkeypatch)
    company = _make_company(name="Wrong Name")
    db = _make_db(company=company, user=None)
    _stub_session(monkeypatch, db)
    monkeypatch.setattr(mod, "confirm_execution", _fail("confirmation must not be reached"))
    monkeypatch.setattr(mod, "read_new_password", _fail("password read must not be reached"))

    rc = main([])

    assert rc == 1
    assert db.commit.call_count == 0
    assert "Aborting before any write" in capsys.readouterr().out


def test_main_aborts_before_write_on_existing_user_wrong_role(monkeypatch, capsys):
    _set_valid_token_env(monkeypatch)
    company = _make_company()
    user = _make_user(company.id, role=EnterpriseRole.VIEWER)
    db = _make_db(company=company, user=user)
    _stub_session(monkeypatch, db)
    monkeypatch.setattr(mod, "confirm_execution", _fail("confirmation must not be reached"))
    monkeypatch.setattr(mod, "read_new_password", _fail("password read must not be reached"))

    rc = main([])

    assert rc == 1
    assert db.commit.call_count == 0
    assert "Aborting before any write" in capsys.readouterr().out


# ── 4. a newly created user is always SUPER_ADMIN / ACTIVE / is_active=True ─


def test_apply_plan_creates_user_with_super_admin_role_and_active_status():
    from app.users.model import UserStatus

    plan = BootstrapPlan(company=None, user=None, create_company=True, create_user=True, existing_password_set=False)
    db = MagicMock()

    company, user = apply_plan(db, plan, "NewOperatorPassw0rd!", reset_existing_password=False)

    assert user.role == TARGET_ROLE
    assert user.role == EnterpriseRole.SUPER_ADMIN
    assert user.status == UserStatus.ACTIVE
    assert user.is_active is True
    assert user.email == TARGET_EMAIL
    assert company.name == TARGET_COMPANY_NAME
    assert company.slug == TARGET_COMPANY_SLUG
    db.commit.assert_called_once()


def test_apply_plan_creates_user_under_existing_company_without_recreating_it():
    company = _make_company()
    plan = BootstrapPlan(company=company, user=None, create_company=False, create_user=True, existing_password_set=False)
    db = MagicMock()

    returned_company, user = apply_plan(db, plan, "NewOperatorPassw0rd!", reset_existing_password=False)

    assert returned_company is company
    assert user.company_id == company.id
    # Only the new user is added -- the existing company object is not re-added.
    added = [call.args[0] for call in db.add.call_args_list]
    assert company not in added


# ── 5. the password never appears in stdout/stderr ──────────────────────────


def test_main_success_path_never_prints_password_or_hashes(monkeypatch, capsys):
    _set_valid_token_env(monkeypatch)
    db = _make_db(company=None, user=None)
    _stub_session(monkeypatch, db)
    monkeypatch.setattr(mod, "confirm_execution", lambda: True)
    secret_password = "SuperSecretOperatorPassw0rd!"
    monkeypatch.setattr(mod, "read_new_password", lambda: secret_password)
    monkeypatch.setattr(mod, "emit_audit_event", lambda *a, **k: None)

    rc = main([])

    assert rc == 0
    combined = "".join(capsys.readouterr())
    assert secret_password not in combined


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


# ── 6. an existing, correct company/user is reused, not recreated ───────────


def test_main_nothing_to_do_when_all_correct_and_no_reset_requested(monkeypatch, capsys):
    _set_valid_token_env(monkeypatch)
    company = _make_company()
    user = _make_user(company.id)
    db = _make_db(company=company, user=user)
    _stub_session(monkeypatch, db)
    monkeypatch.setattr(mod, "confirm_execution", lambda: True)
    monkeypatch.setattr(mod, "read_new_password", _fail("password must not be read when there is nothing to do"))

    rc = main([])

    assert rc == 0
    assert db.commit.call_count == 0
    assert "Nothing to do" in capsys.readouterr().out


# ── 7/8. existing password untouched without both explicit gates ────────────


def test_main_existing_user_password_untouched_without_reset_flag(monkeypatch, capsys):
    _set_valid_token_env(monkeypatch)
    company = _make_company()
    user = _make_user(company.id, hashed_password=OLD_HASH)
    db = _make_db(company=company, user=user)
    _stub_session(monkeypatch, db)
    monkeypatch.setattr(mod, "confirm_execution", lambda: True)
    monkeypatch.setattr(mod, "confirm_reset_execution", _fail("reset confirmation must not be reached"))
    monkeypatch.setattr(mod, "read_new_password", _fail("password must not be read without --reset-existing-password"))

    rc = main([])  # no --reset-existing-password

    assert rc == 0
    assert user.hashed_password == OLD_HASH
    assert db.commit.call_count == 0
    assert "untouched" in capsys.readouterr().out


def test_main_reset_flag_without_second_phrase_match_aborts_without_write(monkeypatch, capsys):
    _set_valid_token_env(monkeypatch)
    company = _make_company()
    user = _make_user(company.id, hashed_password=OLD_HASH)
    db = _make_db(company=company, user=user)
    _stub_session(monkeypatch, db)
    monkeypatch.setattr(mod, "confirm_execution", lambda: True)
    monkeypatch.setattr(mod, "confirm_reset_execution", lambda: False)
    monkeypatch.setattr(mod, "read_new_password", _fail("password must not be read when reset confirmation fails"))

    rc = main(["--reset-existing-password"])

    assert rc == 1
    assert user.hashed_password == OLD_HASH
    assert db.commit.call_count == 0


def test_main_reset_flag_with_second_phrase_matched_resets_password(monkeypatch):
    _set_valid_token_env(monkeypatch)
    company = _make_company()
    user = _make_user(company.id, hashed_password=OLD_HASH)
    db = _make_db(company=company, user=user)
    _stub_session(monkeypatch, db)
    monkeypatch.setattr(mod, "confirm_execution", lambda: True)
    monkeypatch.setattr(mod, "confirm_reset_execution", lambda: True)
    monkeypatch.setattr(mod, "read_new_password", lambda: "BrandNewOperatorPassw0rd!")
    monkeypatch.setattr(mod, "emit_audit_event", lambda *a, **k: None)

    rc = main(["--reset-existing-password"])

    assert rc == 0
    assert user.hashed_password != OLD_HASH
    db.commit.assert_called()


def test_confirm_reset_execution_true_on_exact_match():
    assert confirm_reset_execution(reader=lambda _prompt: RESET_CONFIRMATION_PHRASE) is True


@pytest.mark.parametrize(
    "typed",
    ["", "overwrite existing super admin password", "yes", RESET_CONFIRMATION_PHRASE + " "],
)
def test_confirm_reset_execution_false_on_any_mismatch(typed):
    assert confirm_reset_execution(reader=lambda _prompt: typed) is False


# ── 9/10. primary confirmation required before any mutation ─────────────────


def test_confirm_execution_true_on_exact_match():
    assert confirm_execution(reader=lambda _prompt: CONFIRMATION_PHRASE) is True


@pytest.mark.parametrize(
    "typed",
    ["", "bootstrap thtwaat platform super admin", "yes", CONFIRMATION_PHRASE + " "],
)
def test_confirm_execution_false_on_any_mismatch(typed):
    assert confirm_execution(reader=lambda _prompt: typed) is False


def test_main_aborts_when_confirmation_phrase_wrong(monkeypatch, capsys):
    _set_valid_token_env(monkeypatch)
    db = _make_db(company=None, user=None)
    _stub_session(monkeypatch, db)
    monkeypatch.setattr(mod, "confirm_execution", lambda: False)
    monkeypatch.setattr(mod, "read_new_password", _fail("password read must not be reached"))

    rc = main([])

    assert rc == 1
    assert db.commit.call_count == 0
    assert "Aborting before any write" in capsys.readouterr().out


def test_main_confirmation_runs_only_after_successful_preflight(monkeypatch):
    """Regression guard: confirmation must come after preflight, not before —
    a preflight failure must never even prompt for confirmation."""
    _set_valid_token_env(monkeypatch)
    company = _make_company(name="Wrong Name")
    db = _make_db(company=company, user=None)
    _stub_session(monkeypatch, db)
    called = {"confirm": False}

    def _record_confirm():
        called["confirm"] = True
        return True

    monkeypatch.setattr(mod, "confirm_execution", _record_confirm)
    monkeypatch.setattr(mod, "read_new_password", _fail("password read must not be reached"))

    rc = main([])

    assert rc == 1
    assert called["confirm"] is False


def test_main_full_create_success_path(monkeypatch):
    _set_valid_token_env(monkeypatch)
    db = _make_db(company=None, user=None)
    _stub_session(monkeypatch, db)
    monkeypatch.setattr(mod, "confirm_execution", lambda: True)
    monkeypatch.setattr(mod, "read_new_password", lambda: "OperatorChosenPassw0rd!")
    monkeypatch.setattr(mod, "emit_audit_event", lambda *a, **k: None)

    rc = main([])

    assert rc == 0
    db.commit.assert_called_once()


# ── 11. password hashing goes through AuthService.get_password_hash() ───────


def test_apply_plan_new_user_hash_is_real_verifiable_bcrypt_hash():
    from app.auth.service import AuthService

    plan = BootstrapPlan(company=None, user=None, create_company=True, create_user=True, existing_password_set=False)
    db = MagicMock()
    new_password = "RoundTripPassw0rd!"

    _company, user = apply_plan(db, plan, new_password, reset_existing_password=False)

    assert AuthService.verify_password(new_password, user.hashed_password) is True
    assert AuthService.verify_password("WrongPassword!", user.hashed_password) is False


def test_apply_plan_calls_authservice_get_password_hash(monkeypatch):
    from app.auth.service import AuthService

    calls = []

    def _fake_hash(password: str) -> str:
        calls.append(password)
        return "MARKER-HASH-FROM-AUTHSERVICE"

    monkeypatch.setattr(AuthService, "get_password_hash", staticmethod(_fake_hash))

    plan = BootstrapPlan(company=None, user=None, create_company=True, create_user=True, existing_password_set=False)
    db = MagicMock()

    _company, user = apply_plan(db, plan, "WhateverPassw0rd!", reset_existing_password=False)

    assert calls == ["WhateverPassw0rd!"]
    assert user.hashed_password == "MARKER-HASH-FROM-AUTHSERVICE"


def test_apply_plan_reset_produces_real_verifiable_bcrypt_hash():
    from app.auth.service import AuthService

    company = _make_company()
    user = _make_user(company.id, hashed_password=OLD_HASH)
    plan = BootstrapPlan(company=company, user=user, create_company=False, create_user=False, existing_password_set=True)
    db = MagicMock()
    new_password = "ResetRoundTripPassw0rd!"

    apply_plan(db, plan, new_password, reset_existing_password=True)

    assert user.hashed_password != OLD_HASH
    assert AuthService.verify_password(new_password, user.hashed_password) is True


# ── 12. refresh-token deletion is scoped to the target user only ────────────


def test_apply_plan_reset_scopes_refresh_token_delete_to_target_user():
    company = _make_company()
    user = _make_user(company.id, hashed_password=OLD_HASH)
    plan = BootstrapPlan(company=company, user=user, create_company=False, create_user=False, existing_password_set=True)
    db = MagicMock()

    apply_plan(db, plan, "AnotherValidPassw0rd!", reset_existing_password=True)

    delete_calls = [
        call.args[0]
        for call in db.execute.call_args_list
        if "refresh_tokens" in str(
            call.args[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )
    ]
    assert len(delete_calls) == 1
    compiled = str(delete_calls[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert str(user.id) in compiled


def test_apply_plan_new_user_never_touches_refresh_tokens():
    plan = BootstrapPlan(company=None, user=None, create_company=True, create_user=True, existing_password_set=False)
    db = MagicMock()

    apply_plan(db, plan, "NewOperatorPassw0rd!", reset_existing_password=False)

    db.execute.assert_not_called()


def test_apply_plan_reuse_without_reset_never_touches_refresh_tokens_or_password():
    """If create_user/create_company are both False and reset is False, apply_plan
    is not the code path main() takes (main short-circuits to "nothing to do"),
    but apply_plan itself must still never mutate the password/tokens in that
    configuration, as a defense-in-depth guard."""
    company = _make_company()
    user = _make_user(company.id, hashed_password=OLD_HASH)
    plan = BootstrapPlan(company=company, user=user, create_company=False, create_user=False, existing_password_set=True)
    db = MagicMock()

    apply_plan(db, plan, "ShouldNotBeUsedPassw0rd!", reset_existing_password=False)

    assert user.hashed_password == OLD_HASH
    db.execute.assert_not_called()


# ── 13. audit event is emitted with the expected event name ─────────────────


def test_main_emits_audit_event_with_expected_name(monkeypatch):
    _set_valid_token_env(monkeypatch)
    db = _make_db(company=None, user=None)
    _stub_session(monkeypatch, db)
    monkeypatch.setattr(mod, "confirm_execution", lambda: True)
    monkeypatch.setattr(mod, "read_new_password", lambda: "OperatorChosenPassw0rd!")

    recorded = {}

    def _fake_log_otp_event(event, **kwargs):
        recorded["event"] = event
        recorded.update(kwargs)

    monkeypatch.setattr("app.auth.audit.log_otp_event", _fake_log_otp_event)

    rc = main([])

    assert rc == 0
    assert recorded["event"] == AUDIT_EVENT == "PLATFORM_SUPER_ADMIN_BOOTSTRAP_CLI"
    assert recorded["email"] == TARGET_EMAIL


def test_main_no_reset_no_audit_event_emitted_when_nothing_to_do(monkeypatch):
    _set_valid_token_env(monkeypatch)
    company = _make_company()
    user = _make_user(company.id)
    db = _make_db(company=company, user=user)
    _stub_session(monkeypatch, db)
    monkeypatch.setattr(mod, "confirm_execution", lambda: True)

    recorded = {"called": False}

    def _fake_log_otp_event(*_args, **_kwargs):
        recorded["called"] = True

    monkeypatch.setattr("app.auth.audit.log_otp_event", _fake_log_otp_event)

    rc = main([])

    assert rc == 0
    assert recorded["called"] is False
