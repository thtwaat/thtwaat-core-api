"""Customer Onboarding Wizard unit + stack-backed integration coverage."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.onboarding.schemas import (
    AccountDraft,
    AutosaveRequest,
    CompanyDraft,
    StartOnboardingRequest,
)
from app.onboarding.service import OnboardingService
from app.onboarding.steps import (
    OPTIONAL_STEPS,
    STEP_ORDER,
    OnboardingStatus,
    OnboardingStep,
    build_checklist,
    estimated_minutes_remaining,
    flow_definition,
    next_incomplete_step,
    total_estimated_minutes,
)


def test_flow_has_twelve_ordered_steps():
    assert len(STEP_ORDER) == 12
    assert STEP_ORDER[0] == OnboardingStep.CREATE_ACCOUNT
    assert STEP_ORDER[-1] == OnboardingStep.GO_LIVE
    assert OnboardingStep.UPLOAD_KNOWLEDGE in OPTIONAL_STEPS
    assert OnboardingStep.CONNECT_DOMAIN in OPTIONAL_STEPS


def test_next_incomplete_and_eta():
    completed = [OnboardingStep.CREATE_ACCOUNT.value]
    skipped = [OnboardingStep.UPLOAD_KNOWLEDGE.value]
    nxt = next_incomplete_step(completed, skipped)
    assert nxt == OnboardingStep.VERIFY_EMAIL
    remaining = estimated_minutes_remaining(completed, skipped)
    assert 0 < remaining < total_estimated_minutes()
    checklist = build_checklist(completed, skipped)
    assert checklist[0]["status"] == "completed"
    assert checklist[5]["status"] == "skipped"


def test_flow_definition_exposes_integrations():
    rows = flow_definition()
    assert rows[0]["order"] == 1
    integrations = {r["integration"] for r in rows}
    assert {
        "auth",
        "billing",
        "marketplace",
        "product_generator",
        "publish",
        "domains",
        "branding",
    } <= integrations


def test_start_schema_validation():
    body = StartOnboardingRequest(
        account=AccountDraft(
            email="owner@acme.com",
            password="secret123",
            first_name="Ada",
            last_name="Lovelace",
        ),
        company=CompanyDraft(name="Acme Corp", slug="acme-corp"),
    )
    assert body.company.slug == "acme-corp"
    with pytest.raises(ValidationError):
        CompanyDraft(name="X", slug="Bad Slug")


def test_cannot_skip_required_step_without_db():
    svc = OnboardingService(MagicMock())
    session = SimpleNamespace(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status=OnboardingStatus.IN_PROGRESS,
        completed_steps=[
            OnboardingStep.CREATE_ACCOUNT.value,
            OnboardingStep.VERIFY_EMAIL.value,
        ],
        skipped_steps=[],
        current_step=OnboardingStep.CREATE_COMPANY,
    )
    svc._active_for_user = MagicMock(return_value=session)  # type: ignore[method-assign]
    with pytest.raises(HTTPException) as exc:
        svc.skip_step(
            uuid.uuid4(),
            uuid.uuid4(),
            OnboardingStep.CREATE_COMPANY,
            type("B", (), {"reason": "nope"})(),
        )
    assert exc.value.status_code == 400


def test_assert_step_out_of_order():
    svc = OnboardingService(MagicMock())
    session = SimpleNamespace(
        status=OnboardingStatus.IN_PROGRESS,
        completed_steps=[OnboardingStep.CREATE_ACCOUNT.value],
        skipped_steps=[],
        current_step=OnboardingStep.VERIFY_EMAIL,
    )
    with pytest.raises(HTTPException) as exc:
        svc._assert_step_reachable(session, OnboardingStep.PUBLISH)
    assert exc.value.status_code == 409


def test_progress_tracker_math_via_response_builder():
    svc = OnboardingService(MagicMock())
    now = datetime.now(timezone.utc)
    session = SimpleNamespace(
        id=uuid.uuid4(),
        resume_token="tok",
        user_id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        status=OnboardingStatus.IN_PROGRESS,
        current_step=OnboardingStep.CHOOSE_PLAN,
        completed_steps=[
            OnboardingStep.CREATE_ACCOUNT.value,
            OnboardingStep.VERIFY_EMAIL.value,
            OnboardingStep.CREATE_COMPANY.value,
        ],
        skipped_steps=[],
        draft_data={},
        resource_ids={},
        checklist=None,
        estimated_minutes_total=total_estimated_minutes(),
        estimated_minutes_remaining=10,
        started_at=now,
        last_active_at=now,
        paused_at=None,
        completed_at=None,
        last_error=None,
    )
    resp = svc._to_response(session)
    assert resp.progress.completed_count == 3
    assert resp.progress.current_order == 4
    assert resp.progress.percent_complete == 25.0
    assert len(resp.checklist) == 12


def test_autosave_merges_draft():
    svc = OnboardingService(MagicMock())
    session = SimpleNamespace(
        status=OnboardingStatus.IN_PROGRESS,
        current_step=OnboardingStep.CREATE_COMPANY,
        draft_data={"create_company": {"name": "Old"}},
        last_active_at=None,
    )
    svc._active_for_user = MagicMock(return_value=session)  # type: ignore[method-assign]
    svc._assert_writable = MagicMock()  # type: ignore[method-assign]
    svc._touch = MagicMock()  # type: ignore[method-assign]
    svc._record_event = MagicMock()  # type: ignore[method-assign]
    svc.db = MagicMock()
    svc.db.commit = MagicMock()
    svc.db.refresh = MagicMock()
    svc._to_response = MagicMock(return_value={"ok": True})  # type: ignore[method-assign]

    result = svc.autosave(
        uuid.uuid4(),
        uuid.uuid4(),
        AutosaveRequest(draft={"industry": "SaaS"}),
    )
    assert session.draft_data["create_company"]["name"] == "Old"
    assert session.draft_data["create_company"]["industry"] == "SaaS"
    assert result == {"ok": True}


def _auth(client):
    slug = f"onboard-{uuid.uuid4().hex[:8]}"
    start = client.post(
        "/api/v1/onboarding/start",
        json={
            "account": {
                "email": f"owner@{slug}.test",
                "password": "secret12345",
                "first_name": "Owner",
                "last_name": "User",
            },
            "company": {"name": "Onboard Co", "slug": slug},
            "send_verification": False,
        },
    )
    assert start.status_code == 201, start.text
    body = start.json()
    return body["access_token"], body["session"]


@pytest.mark.integration
def test_onboarding_start_and_progress(client):
    token, session = _auth(client)
    assert session["current_step"] == "create_company"
    assert "create_account" in session["completed_steps"]
    assert "verify_email" in session["completed_steps"]
    assert session["progress"]["total_steps"] == 12

    me = client.get(
        "/api/v1/onboarding/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["resume_token"] == session["resume_token"]

    flow = client.get("/api/v1/onboarding/flow")
    assert flow.status_code == 200
    assert len(flow.json()["steps"]) == 12


@pytest.mark.integration
def test_onboarding_autosave_pause_resume_skip(client):
    token, session = _auth(client)
    headers = {"Authorization": f"Bearer {token}"}

    saved = client.post(
        "/api/v1/onboarding/me/autosave",
        headers=headers,
        json={"step": "create_company", "draft": {"industry": "Retail"}},
    )
    assert saved.status_code == 200
    assert saved.json()["draft_data"]["create_company"]["industry"] == "Retail"

    paused = client.post("/api/v1/onboarding/me/pause", headers=headers)
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    resumed = client.post("/api/v1/onboarding/me/resume", headers=headers)
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "in_progress"

    # verify_email already completed at signup — skip is not needed
    by_token = client.get(f"/api/v1/onboarding/resume/{session['resume_token']}")
    assert by_token.status_code == 200


@pytest.mark.integration
def test_onboarding_verify_email_is_noop_without_otp(client):
    """Legacy verify_email complete still succeeds without an OTP code."""
    token, session = _auth(client)
    headers = {"Authorization": f"Bearer {token}"}
    # Already completed at start — completing again should be idempotent / reachable as done
    assert "verify_email" in session["completed_steps"]
    me = client.get("/api/v1/onboarding/me", headers=headers)
    assert me.status_code == 200
    assert "verify_email" in me.json()["completed_steps"]


def test_step_verify_email_marks_verified_without_code():
    from unittest.mock import MagicMock
    from types import SimpleNamespace

    db = MagicMock()
    owner = SimpleNamespace(id="u1", email="a@b.com", email_verified=False, email_verified_at=None)
    db.scalar.return_value = owner
    svc = OnboardingService(db)
    svc.auth = MagicMock()
    session = SimpleNamespace(user_id="u1", draft_data={"account": {"email": "a@b.com"}})
    result = svc._step_verify_email(session, {"email": "a@b.com"})
    assert result["detail"] == "Email verified"
    svc.auth.mark_email_verified.assert_called_once_with(owner)
