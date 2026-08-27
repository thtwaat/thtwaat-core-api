"""Regression test for the production bug: a freshly deployed static site's
*.thtwaat.com hostname served the Core API's own root JSON
({"message":"Welcome to THTWAAT Core API"}) instead of the deployed files.

Root cause: app/ssl/manager.py::SslManager.request()/renew() load the
`domain` ORM row ONCE, BEFORE the slow, blocking issue_certificate() call
(a real network round-trip to Let's Encrypt), then hand that SAME in-memory
object to _activate(), which reads domain.static_root_path off it to decide
whether generate_vhost() should emit a static (root/try_files) or default
proxy-to-API location block.

app/static_sites/provider.py::bind_hostname_and_ssl() commits
static_root_path onto the SAME domain row via SslManager.set_static_root()
— but that happens in a DIFFERENT process (the API request handling the
deploy) than the one issuing the certificate (scripts/worker.py processing
the "domain.auto_progress" job). If set_static_root()'s commit lands WHILE
issue_certificate() is still in flight, _activate()'s in-memory `domain`
object never sees it — static_root_path reads back None, and
generate_vhost() silently falls back to its default proxy_pass-to-API
location block for a site that IS actually static.

Fix: _activate() now re-reads static_root_path/runtime_proxy_target with a
fresh, targeted query immediately before calling generate_vhost(), instead
of trusting the object it was handed.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import main  # noqa: F401 — registers every model class before any relationship() resolves it by name
from app.domains.models import CompanyDomain, DomainStatus, SslStatus, DomainVerificationMethod
from app.ssl.manager import SslManager


def _make_pending_domain(db_session, *, company_id) -> CompanyDomain:
    # Random suffix (not the fixed literal from the bug report) — db_session
    # commits are never rolled back between tests/runs (see
    # tests/conftest.py), and CompanyDomain.hostname is globally unique, so
    # a hardcoded value would collide with a previous run's leftover row.
    hostname = f"create-a-reusable-thtwaat-co-{uuid.uuid4().hex[:8]}.thtwaat.com"
    now = datetime.now(timezone.utc)
    domain = CompanyDomain(
        id=uuid.uuid4(), company_id=company_id, hostname=hostname,
        status=DomainStatus.SSL_PENDING, verification_method=DomainVerificationMethod.TXT,
        verification_token="token", verified_at=now, last_checked_at=now,
        dns_records=[], ssl_status=SslStatus.PENDING.value, cors_origin=f"https://{hostname}",
    )
    db_session.add(domain)
    db_session.commit()
    return domain


def test_concurrent_static_root_commit_during_ssl_issuance_still_produces_static_vhost(
    db_session, tmp_path, monkeypatch
):
    """The exact race: set_static_root() commits static_root_path on a
    SEPARATE db session WHILE issue_certificate() is "in flight" (simulated
    inside the mocked call) — _activate() must still generate a static
    vhost, not silently fall back to proxying at the Core API."""
    from app.database.database import SessionLocal

    company_id = uuid.uuid4()
    from app.companies.model import Company

    db_session.add(Company(id=company_id, slug=f"race-{uuid.uuid4().hex[:8]}", name="Race Co"))
    db_session.commit()

    domain = _make_pending_domain(db_session, company_id=company_id)
    static_dir = str(tmp_path / "deploy" / str(uuid.uuid4()))

    conf = tmp_path / "conf"
    conf.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("app.ssl.nginx_gen.conf_dir", lambda: conf)
    monkeypatch.setattr("app.ssl.nginx_gen.reload_nginx", lambda: (True, "ok"))
    monkeypatch.setattr("app.ssl.manager.reload_nginx", lambda: (True, "ok"))
    monkeypatch.setattr("app.ssl.nginx_gen.settings.SSL_WEBROOT_DIR", str(tmp_path / "acme"))
    monkeypatch.setattr("app.ssl.nginx_gen.settings.NGINX_CERT_CONTAINER_PREFIX", None)

    def _fake_issue_certificate(hostname, wildcard=False):
        # Simulates set_static_root() (app/static_sites/provider.py's
        # bind_hostname_and_ssl) committing from a DIFFERENT db session —
        # exactly like a concurrent OS process would — WHILE this "ACME
        # call" is in flight, i.e. strictly between when SslManager.request()
        # first loaded `domain` and when it calls _activate() with that
        # same, now-stale object.
        other_session = SessionLocal()
        try:
            SslManager(other_session).set_static_root(
                domain.id, company_id, static_dir, company_id
            )
        finally:
            other_session.close()
        return (
            True, "ok",
            str(tmp_path / "fullchain.pem"), str(tmp_path / "privkey.pem"),
            "serial123", datetime.now(timezone.utc),
        )

    with patch("app.ssl.manager.issue_certificate", side_effect=_fake_issue_certificate):
        SslManager(db_session).request(domain.id, company_id, company_id)

    vhost_path = conf / f"{domain.hostname}.conf"
    assert vhost_path.exists(), "generate_vhost() was never called"
    text = vhost_path.read_text(encoding="utf-8")

    assert "proxy_pass http://api_backend;" not in text, (
        "regression: vhost fell back to proxying at the Core API instead of "
        "serving the deployed static site"
    )
    assert "try_files $uri $uri/ /index.html" in text
