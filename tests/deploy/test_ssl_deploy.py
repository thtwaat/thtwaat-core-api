"""SSL Manager + nginx generator + health tests."""
from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from app.domains.models import SslStatus
from app.ssl.certs import certs_root, issue_self_signed, issue_certificate
from app.ssl.nginx_gen import generate_vhost, conf_dir
from app.ssl.manager import SslManager, normalize_ssl_status
from app.deploy.health import check_storage, check_ai_providers
from app.deploy.metrics import snapshot, incr_requests

REPO_ROOT = Path(__file__).resolve().parents[2]


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


def test_issue_certificate_rejects_self_signed_in_production(monkeypatch):
    monkeypatch.setattr("app.config.settings.settings.app_env", "production", raising=False)
    monkeypatch.setattr("app.config.settings.settings.SSL_MODE", "simulate", raising=False)
    with patch("app.ssl.certs.settings") as s:
        s.SSL_MODE = "simulate"
        s.app_env = "production"
        s.is_hardened_env = True
        ok, msg, cert, key, serial, expires = issue_certificate("tailor.thtwaat.com")
    assert ok is False
    assert "production" in msg.lower()
    assert cert is None


def test_certs_root_uses_configured_dir_in_production(tmp_path, monkeypatch):
    """Regression: certs_root() must never hardcode nginx's own /etc/nginx/ssl
    path — api/worker containers mount the shared volume at SSL_CERTS_DIR's
    path instead, so hardcoding nginx's path silently orphans issued certs
    (see docker-compose.prod.yml volume mounts)."""
    configured = tmp_path / "app_view_of_ssl_dir"
    with patch("app.ssl.certs.settings") as s:
        s.app_env = "production"
        s.is_hardened_env = True
        s.SSL_CERTS_DIR = str(configured)
        root = certs_root()
    assert root == configured
    assert root != Path("/etc/nginx/ssl/domains")


def test_prod_compose_defaults_ssl_mode_to_certbot():
    """Regression: docker-compose.prod.yml is production-only. If ops forgets
    to set SSL_MODE explicitly, it must default to certbot, not simulate —
    otherwise issue_certificate() always rejects issuance in production
    (app/ssl/certs.py _is_production_environment guard) and certbot never runs."""
    compose_path = REPO_ROOT / "docker-compose.prod.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    for service_name in ("api", "worker"):
        ssl_mode = compose["services"][service_name]["environment"]["SSL_MODE"]
        assert ssl_mode == "${SSL_MODE:-certbot}", (
            f"{service_name} service SSL_MODE default regressed to: {ssl_mode}"
        )


def test_prod_compose_configures_shared_ssl_certs_dir():
    """Regression: api and worker must explicitly set SSL_CERTS_DIR to the
    same path, and that path must live under their shared ./nginx/ssl mount
    (docker-compose.prod.yml) so the string-based remap in generate_vhost()
    (app/ssl/nginx_gen.py, "nginx/ssl/" substring swap) can retarget it to
    nginx's own /etc/nginx/ssl mount of the identical host directory."""
    compose_path = REPO_ROOT / "docker-compose.prod.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = compose["services"]

    api_dir = services["api"]["environment"]["SSL_CERTS_DIR"]
    worker_dir = services["worker"]["environment"]["SSL_CERTS_DIR"]
    assert api_dir == worker_dir, "api/worker SSL_CERTS_DIR must match — they share one cert volume"
    assert "nginx/ssl/" in api_dir, "SSL_CERTS_DIR must fall under the shared ./nginx/ssl mount"

    api_mount = next(
        v for v in services["api"]["volumes"] if v.split(":")[0] == "./nginx/ssl"
    )
    api_mount_target = api_mount.split(":")[1]
    assert api_dir.startswith(api_mount_target), (
        f"SSL_CERTS_DIR ({api_dir}) must live under the api container's own "
        f"./nginx/ssl mount point ({api_mount_target}), not nginx's absolute path"
    )


def test_prod_image_installs_certbot():
    """Regression: run_certbot_http01() shells out to the certbot binary from
    the api/worker container (built from the root Dockerfile). Without the
    package installed, issuance fails with FileNotFoundError even once
    SSL_MODE=certbot is reached."""
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "certbot" in dockerfile


def test_nginx_image_runs_self_reload_watcher():
    """Regression: reload_nginx() (app/ssl/nginx_gen.py) runs from the
    api/worker containers, which have neither Docker socket access nor a
    local nginx binary, so it always fails silently in production. Newly
    issued vhosts/certs then sat on the shared volume unreloaded and
    requests kept falling through to nginx's self-signed default_server
    cert (NET::ERR_CERT_AUTHORITY_INVALID). nginx must instead watch its
    own conf.d/domains and ssl mounts and reload itself."""
    dockerfile = (REPO_ROOT / "nginx" / "Dockerfile").read_text(encoding="utf-8")
    assert "inotify-tools" in dockerfile
    assert "reload-watch.sh" in dockerfile

    watch_script = REPO_ROOT / "nginx" / "reload-watch.sh"
    assert watch_script.exists()
    script = watch_script.read_text(encoding="utf-8")
    assert "inotifywait" in script
    assert "/etc/nginx/conf.d/domains" in script
    assert "/etc/nginx/ssl" in script
    assert "nginx -s reload" in script


def test_activate_logs_when_reload_fails(tmp_path, monkeypatch, caplog):
    """Regression: SslManager._activate() must not silently discard a
    failed reload_nginx() call — it should at least be logged so a failed
    in-band reload (expected in prod; the nginx-side watcher picks it up
    instead) is visible in ops logs rather than invisible."""
    import logging
    from datetime import datetime, timezone, timedelta
    from app.domains.models import CompanyDomain, DomainStatus

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
        cert = tmp_path / "c.pem"
        key = tmp_path / "k.pem"
        cert.write_text("c")
        key.write_text("k")
        issue.return_value = (True, "ok", cert, key, "abc123", datetime.now(timezone.utc) + timedelta(days=90))
        with patch("app.ssl.manager.generate_vhost", return_value=tmp_path / "v.conf"):
            with patch(
                "app.ssl.manager.reload_nginx",
                return_value=(False, "nginx reload skipped (container/binary unavailable)"),
            ):
                with caplog.at_level(logging.WARNING):
                    result = mgr.request(domain.id, domain.company_id, domain.company_id)

    assert "nginx_reload_deferred" in caplog.text
    # State machine is unchanged — the nginx-side watcher is expected to pick
    # up the change even when the in-band reload attempt fails.
    assert result["ssl_status"] == SslStatus.ACTIVE.value
    assert domain.status == DomainStatus.LIVE


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
