"""
tests/unit/coding_agent/test_tasks_proxy.py — Phase 6C-2: Core's
task-creation/status/cancel proxy (app/coding_agent/router.py's
/api/v1/coding-agent/tasks* routes).

Builds a minimal FastAPI app with ONLY app.coding_agent.router — the
same "no lifespan, no live Postgres/Redis" pattern
tests/unit/auth/test_route_auth_openapi.py already established — and
mocks app.coding_agent.client's outbound calls (unittest.mock.patch), so
these tests never touch a real AI_Project process or network. AI_Project
's own test suite (tests/test_service_tasks.py in that repository)
covers the real end-to-end behavior against the actual TaskStore/
AgentRuntime; these tests cover Core's own RBAC gate, request/response
translation, and error sanitization at ITS boundary.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.coding_agent.client import CodingAgentError
from app.coding_agent.router import router as coding_agent_router


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(coding_agent_router, prefix="/api/v1")
    return app


def _fake_user(role: str = "employee") -> UserProfileResponse:
    return UserProfileResponse(
        id=uuid.uuid4(), company_id=uuid.uuid4(), email="dev@example.com",
        first_name="Dev", last_name="User", role=role,
    )


@pytest.fixture
def app():
    """Authenticated by default (role=employee, which holds
    CODING_AGENT_ACCESS) — the common case for these tests. Tests that
    specifically exercise "no credentials at all" use the separate
    unauthenticated_client fixture below instead of clearing this
    override, so there is never an ordering-dependent risk of a
    forgotten override leaking into another test."""
    fastapi_app = _app()
    fastapi_app.dependency_overrides[get_current_user] = lambda: _fake_user(role="employee")
    return fastapi_app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def unauthenticated_client():
    return TestClient(_app())


class TestCreateCodingTask:
    def test_valid_task_creation(self, client):
        upstream = {
            "task_id": "task-abc123", "status": "QUEUED", "phase": None,
            "termination_code": None, "created_at": 1.0, "updated_at": 1.0,
            "started_at": None, "ended_at": None, "result": None, "error": None,
        }
        with patch("app.coding_agent.router.coding_agent_client.create_task", return_value=upstream) as mocked:
            resp = client.post("/api/v1/coding-agent/tasks", json={"goal": "Add a health check endpoint."})
        assert resp.status_code == 201
        body = resp.json()
        assert body["task_id"] == "task-abc123"
        assert body["status"] == "QUEUED"
        assert mocked.call_count == 1

    def test_rbac_denies_viewer_role(self, app, client):
        app.dependency_overrides[get_current_user] = lambda: _fake_user(role="viewer")
        resp = client.post("/api/v1/coding-agent/tasks", json={"goal": "x"})
        assert resp.status_code == 403

    def test_authentication_failure_missing_bearer(self, unauthenticated_client):
        resp = unauthenticated_client.post("/api/v1/coding-agent/tasks", json={"goal": "x"})
        assert resp.status_code == 401

    def test_invalid_input_blank_goal_rejected(self, client):
        resp = client.post("/api/v1/coding-agent/tasks", json={"goal": "   "})
        assert resp.status_code == 422

    def test_invalid_input_oversized_goal_rejected(self, client):
        resp = client.post("/api/v1/coding-agent/tasks", json={"goal": "x" * 20_001})
        assert resp.status_code == 422

    def test_invalid_idempotency_key_rejected(self, client):
        resp = client.post(
            "/api/v1/coding-agent/tasks", json={"goal": "x"},
            headers={"Idempotency-Key": "has spaces and $ymbols!!"},
        )
        assert resp.status_code == 400

    def test_valid_idempotency_key_forwarded(self, client):
        upstream = {
            "task_id": "task-abc123", "status": "QUEUED", "phase": None,
            "termination_code": None, "created_at": 1.0, "updated_at": 1.0,
            "started_at": None, "ended_at": None, "result": None, "error": None,
        }
        with patch("app.coding_agent.router.coding_agent_client.create_task", return_value=upstream) as mocked:
            resp = client.post(
                "/api/v1/coding-agent/tasks", json={"goal": "x"},
                headers={"Idempotency-Key": "retry-key-001"},
            )
        assert resp.status_code == 201
        assert mocked.call_args.kwargs["idempotency_key"] == "retry-key-001"

    def test_unknown_workspace_mapping_propagates_as_404(self, client):
        with patch(
            "app.coding_agent.router.coding_agent_client.create_task",
            side_effect=CodingAgentError(404, "Coding task not found."),
        ):
            resp = client.post("/api/v1/coding-agent/tasks", json={"goal": "x"})
        assert resp.status_code == 404

    def test_duplicate_request_conflict_propagates(self, client):
        with patch(
            "app.coding_agent.router.coding_agent_client.create_task",
            side_effect=CodingAgentError(409, "This request is already being processed."),
        ):
            resp = client.post("/api/v1/coding-agent/tasks", json={"goal": "x"})
        assert resp.status_code == 409

    def test_upstream_error_sanitized(self, client):
        with patch(
            "app.coding_agent.router.coding_agent_client.create_task",
            side_effect=CodingAgentError(502, "Coding Agent service error."),
        ):
            resp = client.post("/api/v1/coding-agent/tasks", json={"goal": "x"})
        assert resp.status_code == 502
        text = resp.text
        assert "Traceback" not in text
        assert "sqlite3" not in text
        assert "secret" not in text.lower()


class TestGetCodingTask:
    def test_status_retrieval(self, client):
        upstream = {
            "task_id": "task-abc123", "status": "RUNNING", "phase": "code",
            "termination_code": None, "created_at": 1.0, "updated_at": 2.0,
            "started_at": 1.5, "ended_at": None, "result": None, "error": None,
        }
        with patch("app.coding_agent.router.coding_agent_client.get_task", return_value=upstream):
            resp = client.get("/api/v1/coding-agent/tasks/task-abc123")
        assert resp.status_code == 200
        assert resp.json()["status"] == "RUNNING"

    def test_get_unknown_task_returns_404(self, client):
        with patch(
            "app.coding_agent.router.coding_agent_client.get_task",
            side_effect=CodingAgentError(404, "Coding task not found."),
        ):
            resp = client.get("/api/v1/coding-agent/tasks/task-doesnotexist")
        assert resp.status_code == 404

    def test_get_task_requires_authentication(self, unauthenticated_client):
        resp = unauthenticated_client.get("/api/v1/coding-agent/tasks/task-abc123")
        assert resp.status_code == 401


class TestCancelCodingTask:
    def test_cancel_task(self, client):
        upstream = {
            "task_id": "task-abc123", "status": "CANCELLED",
            "cancel_requested": True, "message": "Task cancelled before it started.",
        }
        with patch("app.coding_agent.router.coding_agent_client.cancel_task", return_value=upstream):
            resp = client.post("/api/v1/coding-agent/tasks/task-abc123/cancel")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "CANCELLED"
        assert body["cancel_requested"] is True

    def test_cancel_rbac_denies_viewer(self, app, client):
        app.dependency_overrides[get_current_user] = lambda: _fake_user(role="viewer")
        resp = client.post("/api/v1/coding-agent/tasks/task-abc123/cancel")
        assert resp.status_code == 403
