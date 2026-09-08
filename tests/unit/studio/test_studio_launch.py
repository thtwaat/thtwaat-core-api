"""Phase 11 — production launch hardening unit tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.studio.deploy import probe_http
from app.studio.launch import (
    DOMAIN_WIZARD_DNS_VERIFIED,
    DOMAIN_WIZARD_PENDING_DNS,
    DOMAIN_WIZARD_SSL_ACTIVE,
    DOMAIN_WIZARD_SSL_ISSUING,
    LAUNCH_STATUS_BUILDING,
    LAUNCH_STATUS_FAILED,
    LAUNCH_STATUS_LIVE,
    LAUNCH_STATUS_PROVISIONING_SSL,
    LAUNCH_STATUS_WAITING_FOR_DNS,
    build_launch_checklist,
    build_launch_diagnostics,
    compute_launch_status,
    domain_wizard_phase,
    verify_deployment_gates,
)


@pytest.mark.unit
def test_probe_http_require_200_rejects_404():
    class FakeResp:
        status = 404

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def getcode(self):
            return 404

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        soft = probe_http("http://example/health")
        strict = probe_http("http://example/health", require_200=True)
    assert soft["ok"] is True  # 4xx still ok in soft mode
    assert strict["ok"] is False


@pytest.mark.unit
def test_probe_http_require_200_accepts_200():
    class FakeResp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def getcode(self):
            return 200

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        result = probe_http("http://example/health", require_200=True)
    assert result["ok"] is True
    assert result["status_code"] == 200


@pytest.mark.unit
def test_verify_deployment_gates_live_requires_all():
    health = {
        "api": {"ok": True, "status_code": 200},
        "database": {"ok": True},
        "storage": {"ok": True},
        "redis": {"ok": True},
        "workers": {"ok": True},
    }
    ok = verify_deployment_gates(
        stack_ok=True, health=health, dns_ok=True, ssl_ok=True, build_ok=True
    )
    assert ok["live"] is True
    assert ok["launch_status"] == LAUNCH_STATUS_LIVE

    waiting = verify_deployment_gates(
        stack_ok=True, health=health, dns_ok=False, ssl_ok=False, build_ok=True
    )
    assert waiting["live"] is False
    assert waiting["launch_status"] == LAUNCH_STATUS_WAITING_FOR_DNS

    ssl = verify_deployment_gates(
        stack_ok=True, health=health, dns_ok=True, ssl_ok=False, build_ok=True
    )
    assert ssl["live"] is False
    assert ssl["launch_status"] == LAUNCH_STATUS_PROVISIONING_SSL

    bad = verify_deployment_gates(
        stack_ok=True,
        health={**health, "api": {"ok": False, "status_code": 500}},
        dns_ok=True,
        ssl_ok=True,
        build_ok=True,
    )
    assert bad["live"] is False
    assert bad["launch_status"] == LAUNCH_STATUS_FAILED
    assert "api" in bad["failed_checks"]


@pytest.mark.unit
def test_compute_launch_status_labels():
    assert (
        compute_launch_status(live=True, status="completed", stage="completed")
        == LAUNCH_STATUS_LIVE
    )
    assert (
        compute_launch_status(live=False, status="waiting_for_domain", stage="waiting_for_domain")
        == LAUNCH_STATUS_WAITING_FOR_DNS
    )
    assert (
        compute_launch_status(live=False, status="provisioning_ssl", stage="provisioning_ssl")
        == LAUNCH_STATUS_PROVISIONING_SSL
    )
    assert (
        compute_launch_status(live=False, status="failed", stage="failed") == LAUNCH_STATUS_FAILED
    )
    assert (
        compute_launch_status(live=False, status="deploying", stage="building")
        == LAUNCH_STATUS_BUILDING
    )


@pytest.mark.unit
def test_domain_wizard_phase_progression():
    assert (
        domain_wizard_phase(
            dns_reachable=False, dns_verified=False, ssl_status="NONE"
        )
        == DOMAIN_WIZARD_PENDING_DNS
    )
    assert (
        domain_wizard_phase(
            dns_reachable=True, dns_verified=True, ssl_status="NONE"
        )
        == DOMAIN_WIZARD_DNS_VERIFIED
    )
    assert (
        domain_wizard_phase(
            dns_reachable=True, dns_verified=True, ssl_status="PENDING"
        )
        == DOMAIN_WIZARD_SSL_ISSUING
    )
    assert (
        domain_wizard_phase(
            dns_reachable=True, dns_verified=True, ssl_status="ACTIVE"
        )
        == DOMAIN_WIZARD_SSL_ACTIVE
    )


@pytest.mark.unit
def test_launch_checklist_structure():
    db = MagicMock()
    with patch("app.studio.deploy.run_platform_health", return_value={
        "api": {"ok": True},
        "database": {"ok": True},
        "storage": {"ok": True},
        "workers": {"ok": True},
        "ai_gateway": {"ok": True},
    }), patch("app.studio.launch._env_present", return_value=True):
        result = build_launch_checklist(
            db, workspace_id=uuid4(), project_id=uuid4(), deployment=None
        )
    keys = {i["key"] for i in result["items"]}
    assert keys >= {
        "ai_provider",
        "billing",
        "email",
        "storage",
        "domain",
        "https",
        "health",
        "workers",
    }
    assert "ready" in result
    assert result["total"] == 8


@pytest.mark.unit
def test_launch_checklist_health_item_warns_on_unconfigured_public_url():
    """The checklist's "Health" item must not pass, and must show the
    actual reason, when the API health probe was never run because
    PUBLIC_API_BASE_URL isn't configured (ok=None from run_platform_health,
    not ok=True)."""
    db = MagicMock()
    with patch(
        "app.studio.deploy.run_platform_health",
        return_value={
            "api": {"ok": None, "note": "PUBLIC_API_BASE_URL is not configured"},
            "database": {"ok": True},
            "storage": {"ok": True},
            "workers": {"ok": True},
            "ai_gateway": {"ok": None, "note": "PUBLIC_API_BASE_URL is not configured"},
        },
    ), patch("app.studio.launch._env_present", return_value=False):
        result = build_launch_checklist(
            db, workspace_id=uuid4(), project_id=uuid4(), deployment=None
        )
    health_item = next(i for i in result["items"] if i["key"] == "health")
    assert health_item["ok"] is False
    assert "not configured" in health_item["detail"].lower()


@pytest.mark.unit
def test_launch_diagnostics_components():
    db = MagicMock()
    with patch("app.studio.deploy.run_platform_health", return_value={
        "api": {"ok": True},
        "database": {"ok": True},
        "storage": {"ok": True},
        "redis": {"ok": True},
        "workers": {"ok": False, "error": "no heartbeat"},
        "ai_gateway": {"ok": True},
    }), patch("app.studio.launch.check_smtp_config", return_value={"ok": True}):
        result = build_launch_diagnostics(
            db, workspace_id=uuid4(), project_id=uuid4(), deployment=None
        )
    titles = {c["title"] for c in result["components"]}
    assert titles == {
        "API",
        "App",
        "Workers",
        "Redis",
        "Database",
        "Storage",
        "SMTP",
        "AI Providers",
        "Deployment",
    }
    assert result["overall"] in {"healthy", "warning", "failed"}
    workers = next(c for c in result["components"] if c["key"] == "workers")
    assert workers["status"] in {"warning", "failed"}
    # PUBLIC_APP_BASE_URL was not part of the mocked health payload above
    # (no "frontend" key) — must read as a warning, never a silent pass.
    app_component = next(c for c in result["components"] if c["key"] == "frontend")
    assert app_component["status"] == "warning"


@pytest.mark.unit
def test_run_platform_health_warns_when_public_urls_unset():
    """PUBLIC_API_BASE_URL/PUBLIC_APP_BASE_URL empty must never read as a
    successful pass — ok=None (warning), with a note explaining why."""
    from app.studio.deploy import run_platform_health

    with patch("app.deploy.health.check_storage", return_value={"ok": True}), patch(
        "app.deploy.health.check_workers", return_value={"ok": True}
    ), patch("redis.from_url") as mock_redis:
        mock_redis.return_value.ping.return_value = True
        mock_redis.return_value.get.return_value = None
        result = run_platform_health(None, api_base="", app_base="")

    assert result["api"]["ok"] is None
    assert "not configured" in result["api"]["note"].lower()
    assert result["ai_gateway"]["ok"] is None
    assert result["frontend"]["ok"] is None
    assert "not configured" in result["frontend"]["note"].lower()


@pytest.mark.unit
def test_run_platform_health_warns_when_public_urls_are_localhost_default():
    """The shipped Settings() defaults are localhost URLs — an operator who
    never overrides them must still get a warning, not a false pass."""
    from app.studio.deploy import run_platform_health

    with patch("app.deploy.health.check_storage", return_value={"ok": True}), patch(
        "app.deploy.health.check_workers", return_value={"ok": True}
    ), patch("redis.from_url") as mock_redis:
        mock_redis.return_value.ping.return_value = True
        mock_redis.return_value.get.return_value = None
        result = run_platform_health(
            None, api_base="http://localhost:8000", app_base="http://localhost:3300"
        )

    assert result["api"]["ok"] is None
    assert result["frontend"]["ok"] is None


@pytest.mark.unit
def test_run_platform_health_probes_when_public_urls_configured():
    """A real, non-localhost URL still gets a real probe (no regression)."""
    from app.studio.deploy import run_platform_health

    fake_probe = {"ok": True, "status_code": 200}
    with patch("app.deploy.health.check_storage", return_value={"ok": True}), patch(
        "app.deploy.health.check_workers", return_value={"ok": True}
    ), patch("redis.from_url") as mock_redis, patch(
        "app.studio.deploy.probe_http", return_value=fake_probe
    ) as mock_probe:
        mock_redis.return_value.ping.return_value = True
        mock_redis.return_value.get.return_value = None
        result = run_platform_health(
            None, api_base="https://api.example.com", app_base="https://app.example.com"
        )

    assert result["api"]["ok"] is True
    assert result["frontend"]["ok"] is True
    assert mock_probe.called


@pytest.mark.unit
def test_deploy_stages_include_provisioning_ssl():
    from app.studio.deploy import DEPLOY_STAGES, DeployStage

    assert "provisioning_ssl" in DEPLOY_STAGES
    assert DeployStage.PROVISIONING_SSL.value == "provisioning_ssl"
