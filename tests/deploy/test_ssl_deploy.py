"""SSL Manager + nginx generator + health tests."""
from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.domains.models import SslStatus
from app.ssl.certs import issue_self_signed, issue_certificate
from app.ssl.nginx_gen import generate_vhost, conf_dir
from app.ssl.manager import SslManager, normalize_ssl_status
from app.deploy.health import check_storage, check_ai_providers
from app.deploy.metrics import snapshot, incr_requests


def test_normalize_ssl_status_legacy():
    assert normalize_ssl_status("pending") == "PENDING"
    assert normalize_ssl_status("issued") == "ISSUED"
    assert normalize_ssl_status("ACTIVE") == "ACTIVE"


def test_issue_self_signed_writes_pem(tmp_path, monkeypatch):
    monkeypatch.setattr("app.ssl.certs.certs_root", lambda: tmp_path / "certs")
    cert, key, serial, expires = issue_self_signed("chat.example.com")
    assert cert.exists()
    assert key.exists()
    assert serial
    assert expires


def test_issue_certificate_simulate(tmp_path, monkeypatch):
    monkeypatch.setattr("app.ssl.certs.certs_root", lambda: tmp_path / "certs")
    monkeypatch.setattr("app.config.settings.settings.SSL_MODE", "simulate", raising=False)
    with patch("app.ssl.certs.settings") as s:
        s.SSL_MODE = "simulate"
        ok, msg, cert, key, serial, expires = issue_certificate("ai.example.com")
    assert ok is True
    assert cert and cert.exists()


def test_generate_vhost(tmp_path, monkeypatch):
    conf = tmp_path / "conf"
    conf.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("app.ssl.nginx_gen.conf_dir", lambda: conf)
    with patch("app.ssl.nginx_gen.settings") as s:
        s.SSL_WEBROOT_DIR = str(tmp_path / "acme")
        s.NGINX_CERT_CONTAINER_PREFIX = None
        path = generate_vhost(
            "chat.acme.com",
            str(tmp_path / "fullchain.pem"),
            str(tmp_path / "privkey.pem"),
        )
    text = path.read_text(encoding="utf-8")
    assert "server_name chat.acme.com" in text
    assert "listen 443 ssl" in text
    assert "return 301 https" in text


def test_ssl_manager_request_flow(tmp_path, monkeypatch):
    from app.domains.models import CompanyDomain, DomainStatus, DomainVerificationMethod

    db = MagicMock()
    mgr = SslManager(db)
    domain = MagicMock(spec=CompanyDomain)
    domain.id = uuid.uuid4()
    domain.company_id = uuid.uuid4()
    domain.hostname = "chat.test.local"
    domain.verified_at = True
    domain.status = DomainStatus.VERIFIED
    domain.ssl_status = SslStatus.NONE.value
    domain.renew_attempts = 0
    domain.is_wildcard = False
    domain.cert_path = None
    domain.key_path = None
    domain.ssl_expires_at = None
    domain.ssl_issued_at = None
    domain.ssl_renewal_at = None
    domain.ssl_last_checked_at = None
    domain.certificate_serial = None
    domain.renewal_error = None
    domain.nginx_config_path = None
    domain.ssl_provider = "letsencrypt"
    domain.ssl_challenge = "http-01"

    mgr.repo.get_for_company = MagicMock(return_value=domain)
    mgr.repo.save = MagicMock(side_effect=lambda d: d)

    monkeypatch.setattr("app.ssl.certs.certs_root", lambda: tmp_path / "certs")
    with patch("app.ssl.manager.issue_certificate") as issue:
        from datetime import datetime, timezone, timedelta

        cert = tmp_path / "c.pem"
        key = tmp_path / "k.pem"
        cert.write_text("c")
        key.write_text("k")
        issue.return_value = (True, "ok", cert, key, "abc123", datetime.now(timezone.utc) + timedelta(days=90))
        with patch("app.ssl.manager.generate_vhost", return_value=tmp_path / "v.conf"):
            with patch("app.ssl.manager.reload_nginx", return_value=(True, "ok")):
                result = mgr.request(domain.id, domain.company_id, domain.company_id)

    assert result["ssl_status"] == SslStatus.ACTIVE.value
    assert domain.status == DomainStatus.LIVE


def test_check_storage_ok():
    assert check_storage()["ok"] is True


def test_check_ai_providers_shape():
    out = check_ai_providers()
    assert "providers" in out
    assert "ok" in out


def test_metrics_snapshot_increments():
    incr_requests()
    snap = snapshot()
    assert snap["api_requests"] >= 1
    assert "uptime_seconds" in snap
