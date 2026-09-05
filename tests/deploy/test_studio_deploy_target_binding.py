"""Focused tests for the static_root/runtime_proxy_target plumbing added to
app.studio.deploy's bind_free_subdomain()/bind_domain_and_ssl().

Context: app/static_sites/provider.py::bind_hostname_and_ssl() used to bind a
THTWAAT Deploy deployment's static content directory (or Next.js runtime
target) onto a domain via a SEPARATE, post-hoc SslManager call keyed by a
fresh hostname lookup, run AFTER bind_free_subdomain()/bind_domain_and_ssl()
had already returned. These two functions now accept static_root/
runtime_proxy_target directly (default None — every existing caller,
including Studio's own "platform reuse" VpsDockerProvider.deploy(), is
unaffected) and, via the new _bind_deploy_target() helper, persist it onto
the SAME domain row in the SAME call that creates/resolves it — before any
certificate is requested, closing the window for the exact race
tests/deploy/test_static_domain_activation_race.py guards against.

generate_vhost()'s own rendering of static_root/runtime_proxy_target (the
location-block content, STATIC_SITES_CONTAINER_PREFIX remapping) is already
covered by tests/deploy/test_static_nginx.py and is deliberately NOT
duplicated here — these tests prove only that the new parameters correctly
reach SslManager.set_static_root()/set_runtime_proxy_target() and, from
there, an actually-generated vhost file, end to end.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import main  # noqa: F401 — registers every model class before any relationship() resolves it by name
from app.companies.model import Company, CompanyPlan, CompanyStatus
from app.domains.models import CompanyDomain, DomainStatus, DomainVerificationMethod, SslStatus
from app.ssl.manager import SslManager
from app.studio.deploy import DeployContext, bind_domain_and_ssl, bind_free_subdomain


def _make_company(db_session) -> Company:
    company = Company(
        name=f"Deploy Target Co {uuid.uuid4().hex[:6]}",
        slug=f"deploy-target-{uuid.uuid4().hex[:8]}",
        plan=CompanyPlan.FREE,
        status=CompanyStatus.ACTIVE,
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


def _make_verified_domain(db_session, *, company_id, hostname: str) -> CompanyDomain:
    """A custom domain already past DNS verification — the state
    bind_domain_and_ssl()'s "existing domain" branch needs to call
    DomainService.request_ssl() inline (status_val in {"verified", ...}),
    so a single bind_domain_and_ssl() call exercises the real, synchronous
    SSL-issuance path rather than just persistence."""
    now = datetime.now(timezone.utc)
    domain = CompanyDomain(
        id=uuid.uuid4(),
        company_id=company_id,
        hostname=hostname,
        status=DomainStatus.VERIFIED,
        verification_method=DomainVerificationMethod.TXT,
        verification_token="token",
        verified_at=now,
        last_checked_at=now,
        dns_records=[],
        ssl_status=SslStatus.PENDING.value,
        cors_origin=f"https://{hostname}",
    )
    db_session.add(domain)
    db_session.commit()
    return domain


def _deploy_ctx(*, company_id, db_session) -> DeployContext:
    return DeployContext(
        project_id=uuid.uuid4(),
        deployment_id=uuid.uuid4(),
        workspace_id=company_id,
        project_title="Deploy Target Test",
        provider="static",
        build_id=uuid.uuid4(),
        build_version=1,
        artifact_path=Path("."),
        artifact_sha256=None,
        db_session=db_session,
        actor_user_id=company_id,
    )


def _patch_ssl_io(tmp_path, monkeypatch):
    """Same monkeypatch pattern as test_static_domain_activation_race.py —
    real SslManager/generate_vhost, only filesystem/reload/ACME side effects
    are stubbed. STATIC_SITES_CONTAINER_PREFIX is disabled here (None) since
    these tmp_path directories aren't under STATIC_SITES_DIR — the dedicated
    remap test below re-enables it with a path that is."""
    conf = tmp_path / "conf"
    conf.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("app.ssl.nginx_gen.conf_dir", lambda: conf)
    monkeypatch.setattr("app.ssl.nginx_gen.reload_nginx", lambda: (True, "ok"))
    monkeypatch.setattr("app.ssl.manager.reload_nginx", lambda: (True, "ok"))
    monkeypatch.setattr("app.ssl.nginx_gen.settings.SSL_WEBROOT_DIR", str(tmp_path / "acme"))
    monkeypatch.setattr("app.ssl.nginx_gen.settings.NGINX_CERT_CONTAINER_PREFIX", None)
    monkeypatch.setattr("app.ssl.nginx_gen.settings.STATIC_SITES_CONTAINER_PREFIX", None)
    return conf


def _fake_issue_certificate(tmp_path):
    def _issue(hostname, wildcard=False):
        return (
            True, "ok",
            str(tmp_path / "fullchain.pem"), str(tmp_path / "privkey.pem"),
            "serial123", datetime.now(timezone.utc),
        )
    return _issue


# ── (a) static_root through bind_free_subdomain -> real vhost is static ────


def test_bind_free_subdomain_with_static_root_produces_static_vhost(tmp_path, db_session, monkeypatch):
    company = _make_company(db_session)
    hostname = f"static-{uuid.uuid4().hex[:8]}.thtwaat.com"
    static_dir = str(tmp_path / "deploy" / str(uuid.uuid4()))
    ctx = _deploy_ctx(company_id=company.id, db_session=db_session)

    with patch("app.monitoring.queue.enqueue"):
        result = bind_free_subdomain(
            ctx, lambda *a, **k: None, hostname=hostname, dns_validated=True, static_root=static_dir,
        )
    assert "domain_id" in result

    domain = db_session.query(CompanyDomain).filter(CompanyDomain.hostname == hostname).one()
    assert domain.static_root_path == static_dir

    conf = _patch_ssl_io(tmp_path, monkeypatch)
    with patch("app.ssl.manager.issue_certificate", side_effect=_fake_issue_certificate(tmp_path)):
        SslManager(db_session).request(domain.id, company.id, company.id)

    text = (conf / f"{hostname}.conf").read_text(encoding="utf-8")
    assert "proxy_pass http://api_backend;" not in text
    # generate_vhost() normalizes static_root to POSIX form (Path.as_posix())
    # regardless of the host OS's own separator.
    assert f"root {Path(static_dir).as_posix()};" in text
    assert "try_files $uri $uri/ /index.html" in text


# ── (b) no static_root/runtime_proxy_target -> unchanged default proxy ─────


def test_bind_free_subdomain_without_target_stays_default_proxy(tmp_path, db_session, monkeypatch):
    company = _make_company(db_session)
    hostname = f"plain-{uuid.uuid4().hex[:8]}.thtwaat.com"
    ctx = _deploy_ctx(company_id=company.id, db_session=db_session)

    with patch("app.monitoring.queue.enqueue"):
        bind_free_subdomain(ctx, lambda *a, **k: None, hostname=hostname, dns_validated=True)

    domain = db_session.query(CompanyDomain).filter(CompanyDomain.hostname == hostname).one()
    assert domain.static_root_path is None
    assert domain.runtime_proxy_target is None

    conf = _patch_ssl_io(tmp_path, monkeypatch)
    with patch("app.ssl.manager.issue_certificate", side_effect=_fake_issue_certificate(tmp_path)):
        SslManager(db_session).request(domain.id, company.id, company.id)

    text = (conf / f"{hostname}.conf").read_text(encoding="utf-8")
    assert "proxy_pass http://api_backend;" in text
    assert "try_files" not in text


# ── (c) runtime_proxy_target through bind_domain_and_ssl -> runtime vhost ──


def test_bind_domain_and_ssl_with_runtime_proxy_target_produces_runtime_vhost(tmp_path, db_session, monkeypatch):
    company = _make_company(db_session)
    hostname = f"runtime-{uuid.uuid4().hex[:8]}.example.com"
    _make_verified_domain(db_session, company_id=company.id, hostname=hostname)
    ctx = _deploy_ctx(company_id=company.id, db_session=db_session)
    runtime_target = "thtwaat-nextjs-runtime-abc123:3000"

    conf = _patch_ssl_io(tmp_path, monkeypatch)
    with patch("app.ssl.manager.issue_certificate", side_effect=_fake_issue_certificate(tmp_path)):
        result = bind_domain_and_ssl(
            ctx, lambda *a, **k: None, hostname=hostname, dns_validated=True,
            runtime_proxy_target=runtime_target,
        )
    assert "ssl_request_error" not in result
    assert result.get("ssl_enabled") is True

    domain = db_session.query(CompanyDomain).filter(CompanyDomain.hostname == hostname).one()
    assert domain.runtime_proxy_target == runtime_target
    assert domain.static_root_path is None

    text = (conf / f"{hostname}.conf").read_text(encoding="utf-8")
    assert "proxy_pass http://api_backend;" not in text
    assert f"set $nextjs_upstream {runtime_target};" in text
    assert "resolver 127.0.0.11" in text


# ── (d) static root remapping still applies through the new plumbing ───────


def test_bind_domain_and_ssl_static_root_remaps_to_nginx_container_path(tmp_path, db_session, monkeypatch):
    company = _make_company(db_session)
    hostname = f"remap-{uuid.uuid4().hex[:8]}.example.com"
    _make_verified_domain(db_session, company_id=company.id, hostname=hostname)
    ctx = _deploy_ctx(company_id=company.id, db_session=db_session)
    host_path = "data/static-sites/companyA/siteB/deployC"

    conf = _patch_ssl_io(tmp_path, monkeypatch)
    monkeypatch.setattr("app.ssl.nginx_gen.settings.STATIC_SITES_CONTAINER_PREFIX", "/etc/nginx/static-sites")
    monkeypatch.setattr("app.ssl.nginx_gen.settings.STATIC_SITES_DIR", "data/static-sites")
    with patch("app.ssl.manager.issue_certificate", side_effect=_fake_issue_certificate(tmp_path)):
        result = bind_domain_and_ssl(
            ctx, lambda *a, **k: None, hostname=hostname, dns_validated=True,
            static_root=host_path,
        )
    assert "ssl_request_error" not in result

    domain = db_session.query(CompanyDomain).filter(CompanyDomain.hostname == hostname).one()
    assert domain.static_root_path == host_path

    text = (conf / f"{hostname}.conf").read_text(encoding="utf-8")
    assert "root /etc/nginx/static-sites/companyA/siteB/deployC;" in text
    assert "data/static-sites" not in text


# ── Studio's own "platform reuse" call site is untouched ────────────────────


def test_vps_provider_call_site_never_passes_a_target(tmp_path, monkeypatch):
    """Guards the design decision behind this fix: Studio's VpsDockerProvider
    deploys are proxy-mode "platform reuse" overlays, not static content —
    ctx.output_dir there is a staging directory for compose/env bundles, not
    web-servable output, and is never under the nginx-mounted static-sites
    tree. Wiring it in as static_root would break every existing Studio
    deployment. This test only proves the call site's kwargs weren't
    accidentally widened — it does not run the full VPS provider pipeline."""
    import inspect

    from app.studio import deploy as deploy_module

    source = inspect.getsource(deploy_module.VpsDockerProvider.deploy)
    call_site = source[source.index("if mode == \"free_subdomain\":") : source.index("ssl_val = str(ssl_info")]
    assert "static_root" not in call_site
    assert "runtime_proxy_target" not in call_site
