"""Regression tests: static-site vhost mode (app/ssl/nginx_gen.py, app/ssl/manager.py).

Proves the new optional static_root parameter added for THTWAAT Deploy
(app/static_sites) never changes output for any existing proxy-mode domain,
and that static mode itself produces a safe, complete vhost (HTTPS/ACME
config untouched, root/try_files instead of proxy_pass).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from app.domains.models import CompanyDomain, DomainStatus, SslStatus
from app.ssl.manager import SslManager
from app.ssl.nginx_gen import generate_vhost

REPO_ROOT = Path(__file__).resolve().parents[2]


def _proxy_vhost(tmp_path: Path, monkeypatch, **kwargs) -> str:
    conf = tmp_path / "conf"
    conf.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("app.ssl.nginx_gen.conf_dir", lambda: conf)
    with patch("app.ssl.nginx_gen.settings") as s:
        s.SSL_WEBROOT_DIR = str(tmp_path / "acme")
        s.NGINX_CERT_CONTAINER_PREFIX = None
        s.STATIC_SITES_CONTAINER_PREFIX = None
        s.STATIC_SITES_DIR = "data/static-sites"
        path = generate_vhost(
            "site.acme.com",
            str(tmp_path / "fullchain.pem"),
            str(tmp_path / "privkey.pem"),
            **kwargs,
        )
    return path.read_text(encoding="utf-8")


def test_default_call_stays_proxy_mode(tmp_path, monkeypatch):
    """No static_root passed → byte-identical proxy behavior to before this feature."""
    text = _proxy_vhost(tmp_path, monkeypatch)
    assert "proxy_pass http://api_backend;" in text
    assert "try_files" not in text


def test_existing_domain_explicit_none_stays_proxy_mode(tmp_path, monkeypatch):
    text = _proxy_vhost(tmp_path, monkeypatch, static_root=None)
    assert "proxy_pass http://api_backend;" in text
    assert "try_files" not in text


def test_static_root_switches_to_static_mode(tmp_path, monkeypatch):
    static_dir = "/app/data/static-sites/company1/site1/deploy1"
    text = _proxy_vhost(tmp_path, monkeypatch, static_root=static_dir)
    # The port-80 /health redirect-server proxy is shared infra, unrelated to
    # site content — only the port-443 content location must drop proxy_pass.
    assert "proxy_pass http://api_backend;" not in text
    assert "try_files $uri $uri/ /index.html" in text
    assert f"root {static_dir};" in text


def test_static_root_container_prefix_remap(tmp_path, monkeypatch):
    conf = tmp_path / "conf"
    conf.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("app.ssl.nginx_gen.conf_dir", lambda: conf)
    host_path = "data/static-sites/companyA/siteB/deployC"
    with patch("app.ssl.nginx_gen.settings") as s:
        s.SSL_WEBROOT_DIR = str(tmp_path / "acme")
        s.NGINX_CERT_CONTAINER_PREFIX = None
        s.STATIC_SITES_CONTAINER_PREFIX = "/etc/nginx/static-sites"
        s.STATIC_SITES_DIR = "data/static-sites"
        path = generate_vhost(
            "site.acme.com",
            str(tmp_path / "fullchain.pem"),
            str(tmp_path / "privkey.pem"),
            static_root=host_path,
        )
    text = path.read_text(encoding="utf-8")
    assert "root /etc/nginx/static-sites/companyA/siteB/deployC;" in text
    assert "data/static-sites" not in text


def _assert_balanced_braces(text: str) -> None:
    """Minimal nginx-config sanity check: every '{' must be closed, and the
    brace nesting must never go negative. Regression coverage for a real bug
    where PROXY_LOCATION_BLOCK was substituted into VHOST_TEMPLATE without
    ever being run through .format() itself, leaving literal '{{'/'}}' in
    every proxy-mode vhost (i.e. every pre-existing domain) — invalid nginx
    syntax that would fail `nginx -t` and block the self-reload watcher for
    every pending domain, not just static ones."""
    assert "{{" not in text, "unescaped literal '{{' found — a format-string field was never rendered"
    assert "}}" not in text, "unescaped literal '}}' found — a format-string field was never rendered"
    depth = 0
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        assert depth >= 0, "unbalanced braces: an extra '}' appears before its matching '{'"
    assert depth == 0, f"unbalanced braces: {depth} unclosed '{{' at end of file"


def test_proxy_vhost_braces_are_balanced_and_unescaped(tmp_path, monkeypatch):
    text = _proxy_vhost(tmp_path, monkeypatch)
    _assert_balanced_braces(text)


def test_static_vhost_braces_are_balanced_and_unescaped(tmp_path, monkeypatch):
    text = _proxy_vhost(tmp_path, monkeypatch, static_root="/app/data/static-sites/c/s/d")
    _assert_balanced_braces(text)


def test_metrics_exact_match_and_root_prefix_do_not_collide(tmp_path, monkeypatch):
    """location = /metrics (exact match) and location / (prefix match) are
    independent sibling blocks in the same server{} — nginx always prefers
    an exact match over a prefix match regardless of declaration order, so
    /metrics is never reachable through the static/proxy root location.
    Prove the two blocks are syntactically distinct (no nesting) in both
    modes, rather than just asserting deny-all is present somewhere."""
    for kwargs in ({}, {"static_root": "/app/data/static-sites/c/s/d"}):
        text = _proxy_vhost(tmp_path, monkeypatch, **kwargs)
        https_server = text.split("listen 443", 1)[1]

        metrics_start = https_server.index("location = /metrics")
        metrics_block_end = https_server.index("}", metrics_start)
        metrics_block = https_server[metrics_start:metrics_block_end + 1]
        assert "deny all;" in metrics_block

        root_start = https_server.index("location /", metrics_block_end)
        # The root location must start strictly after the metrics block closes
        # — i.e. it's a sibling, not nested inside location = /metrics.
        assert root_start > metrics_block_end
        # And the metrics block's own braces must already be balanced on their
        # own (open count == close count within just that slice).
        assert metrics_block.count("{") == metrics_block.count("}") == 1


def test_https_and_acme_config_intact_in_both_modes(tmp_path, monkeypatch):
    proxy_text = _proxy_vhost(tmp_path, monkeypatch)
    static_text = _proxy_vhost(tmp_path, monkeypatch, static_root="/app/data/static-sites/c/s/d")

    for text in (proxy_text, static_text):
        assert "listen 443 ssl http2;" in text
        assert "listen 80;" in text
        assert "location ^~ /.well-known/acme-challenge/" in text
        assert "return 301 https://$host$request_uri;" in text
        assert "ssl_certificate " in text
        assert "ssl_certificate_key " in text
        assert "Strict-Transport-Security" in text
        assert "location = /metrics {" in text
        assert "deny all;" in text


def _mock_domain(**overrides) -> MagicMock:
    domain = MagicMock(spec=CompanyDomain)
    domain.id = uuid.uuid4()
    domain.company_id = uuid.uuid4()
    domain.hostname = "site.test.local"
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
    domain.static_root_path = None
    domain.runtime_proxy_target = None
    for k, v in overrides.items():
        setattr(domain, k, v)
    return domain


def test_ssl_manager_activate_passes_static_root_through(tmp_path, monkeypatch):
    """SslManager._activate() must forward domain.static_root_path to
    generate_vhost() so async SSL activation (scheduler/worker path) also
    produces a correct static vhost — not just the synchronous deploy path."""
    db = MagicMock()
    # _activate() now re-reads static_root_path/runtime_proxy_target with a
    # fresh, targeted query (see app/ssl/manager.py) rather than trusting
    # the possibly-stale `domain` object it was handed — a bare MagicMock
    # `db.query(...).filter(...).one_or_none()` would otherwise return
    # another MagicMock (truthy, with mock attribute values) instead of the
    # real domain's values. None here means "no fresher row" so the code
    # falls back to `domain`'s own attribute, exactly like before.
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    mgr = SslManager(db)
    domain = _mock_domain(static_root_path="/app/data/static-sites/c/s/d1")
    mgr.repo.get_for_company = MagicMock(return_value=domain)
    mgr.repo.save = MagicMock(side_effect=lambda d: d)

    monkeypatch.setattr("app.ssl.certs.certs_root", lambda: tmp_path / "certs")
    with patch("app.ssl.manager.issue_certificate") as issue:
        cert = tmp_path / "c.pem"
        key = tmp_path / "k.pem"
        cert.write_text("c")
        key.write_text("k")
        issue.return_value = (True, "ok", cert, key, "abc123", datetime.now(timezone.utc) + timedelta(days=90))
        with patch("app.ssl.manager.generate_vhost", return_value=tmp_path / "v.conf") as gen:
            with patch("app.ssl.manager.reload_nginx", return_value=(True, "ok")):
                mgr.request(domain.id, domain.company_id, domain.company_id)

    _, kwargs = gen.call_args
    assert kwargs.get("static_root") == "/app/data/static-sites/c/s/d1"


def test_ssl_manager_activate_proxy_domain_unaffected(tmp_path, monkeypatch):
    """Regression: an ordinary (non-static) domain must still call
    generate_vhost() with static_root=None — proving the new column/param
    doesn't leak into the existing proxy-mode activation path."""
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    mgr = SslManager(db)
    domain = _mock_domain()  # static_root_path=None
    mgr.repo.get_for_company = MagicMock(return_value=domain)
    mgr.repo.save = MagicMock(side_effect=lambda d: d)

    monkeypatch.setattr("app.ssl.certs.certs_root", lambda: tmp_path / "certs")
    with patch("app.ssl.manager.issue_certificate") as issue:
        cert = tmp_path / "c.pem"
        key = tmp_path / "k.pem"
        cert.write_text("c")
        key.write_text("k")
        issue.return_value = (True, "ok", cert, key, "abc123", datetime.now(timezone.utc) + timedelta(days=90))
        with patch("app.ssl.manager.generate_vhost", return_value=tmp_path / "v.conf") as gen:
            with patch("app.ssl.manager.reload_nginx", return_value=(True, "ok")):
                mgr.request(domain.id, domain.company_id, domain.company_id)

    _, kwargs = gen.call_args
    assert kwargs.get("static_root") is None


def test_set_static_root_regenerates_vhost_without_reissuing_cert(tmp_path, monkeypatch):
    """Rollback/redeploy path: set_static_root() must rewrite the vhost using
    the EXISTING cert/key (no call to issue_certificate) — proving rollback
    never re-triggers Let's Encrypt issuance."""
    db = MagicMock()
    mgr = SslManager(db)
    cert = tmp_path / "c.pem"
    key = tmp_path / "k.pem"
    cert.write_text("c")
    key.write_text("k")
    domain = _mock_domain(cert_path=str(cert), key_path=str(key), status=DomainStatus.LIVE, ssl_status=SslStatus.ACTIVE.value)
    mgr.repo.get_for_company = MagicMock(return_value=domain)
    mgr.repo.save = MagicMock(side_effect=lambda d: d)

    with patch("app.ssl.manager.issue_certificate") as issue:
        with patch("app.ssl.manager.generate_vhost", return_value=tmp_path / "v.conf") as gen:
            with patch("app.ssl.manager.reload_nginx", return_value=(True, "ok")):
                mgr.set_static_root(domain.id, domain.company_id, "/app/data/static-sites/c/s/d2", domain.company_id)

    issue.assert_not_called()
    _, kwargs = gen.call_args
    assert kwargs.get("static_root") == "/app/data/static-sites/c/s/d2"
    assert domain.static_root_path == "/app/data/static-sites/c/s/d2"


def test_prod_compose_mounts_static_sites_readonly_for_nginx():
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"))
    nginx_mounts = compose["services"]["nginx"]["volumes"]
    static_mount = next((v for v in nginx_mounts if v.split(":")[0] == "./data/static-sites"), None)
    assert static_mount is not None, "nginx must mount ./data/static-sites"
    assert static_mount.endswith(":ro"), "nginx must only ever read static site content"


def test_prod_compose_mounts_static_sites_readwrite_for_api_and_worker():
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"))
    for service_name in ("api", "worker"):
        mounts = compose["services"][service_name]["volumes"]
        static_mount = next((v for v in mounts if v.split(":")[0] == "./data/static-sites"), None)
        assert static_mount is not None, f"{service_name} must mount ./data/static-sites"
        assert not static_mount.endswith(":ro"), f"{service_name} needs write access to extract deployments"

        env = compose["services"][service_name]["environment"]
        assert env["STATIC_SITES_DIR"] == "/app/data/static-sites"
        assert env["STATIC_SITES_CONTAINER_PREFIX"] == "/etc/nginx/static-sites"


# ---- THTWAAT Phase 3 — Next.js runtime-proxy vhost mode --------------------


def test_runtime_proxy_target_switches_to_runtime_proxy_mode(tmp_path, monkeypatch):
    target = "thtwaat-nextjs-runtime-abc123:3000"
    text = _proxy_vhost(tmp_path, monkeypatch, runtime_proxy_target=target)
    assert "proxy_pass http://api_backend;" not in text
    assert "try_files" not in text  # not static mode either
    assert f"set $nextjs_upstream {target};" in text
    assert "proxy_pass http://$nextjs_upstream;" in text
    assert "resolver 127.0.0.11" in text


def test_runtime_proxy_and_static_root_together_prefers_runtime(tmp_path, monkeypatch):
    """generate_vhost() docstring promises runtime_proxy_target wins if both
    are somehow set — never silently pick static instead."""
    text = _proxy_vhost(
        tmp_path, monkeypatch,
        static_root="/app/data/static-sites/c/s/d",
        runtime_proxy_target="thtwaat-nextjs-runtime-abc123:3000",
    )
    assert "try_files" not in text
    assert "set $nextjs_upstream" in text


def test_runtime_proxy_vhost_braces_are_balanced_and_unescaped(tmp_path, monkeypatch):
    text = _proxy_vhost(tmp_path, monkeypatch, runtime_proxy_target="thtwaat-nextjs-runtime-abc123:3000")
    _assert_balanced_braces(text)


def test_https_and_acme_config_intact_in_runtime_proxy_mode(tmp_path, monkeypatch):
    """Same regression coverage as test_https_and_acme_config_intact_in_both_modes
    above, for the third (runtime-proxy) mode."""
    text = _proxy_vhost(tmp_path, monkeypatch, runtime_proxy_target="thtwaat-nextjs-runtime-abc123:3000")
    assert "listen 443 ssl http2;" in text
    assert "listen 80;" in text
    assert "location ^~ /.well-known/acme-challenge/" in text
    assert "ssl_certificate " in text
    assert "Strict-Transport-Security" in text
    assert "location = /metrics {" in text
    assert "deny all;" in text


def test_default_and_static_modes_unaffected_by_runtime_proxy_param(tmp_path, monkeypatch):
    """Regression: adding runtime_proxy_target must not change proxy-mode or
    static-mode output when it's left at its default (None)."""
    proxy_text = _proxy_vhost(tmp_path, monkeypatch)
    assert "proxy_pass http://api_backend;" in proxy_text
    assert "nextjs_upstream" not in proxy_text

    static_text = _proxy_vhost(tmp_path, monkeypatch, static_root="/app/data/static-sites/c/s/d")
    assert "try_files $uri $uri/ /index.html" in static_text
    assert "nextjs_upstream" not in static_text


def test_ssl_manager_activate_passes_runtime_proxy_target_through(tmp_path, monkeypatch):
    """SslManager._activate() must forward domain.runtime_proxy_target to
    generate_vhost() — the async SSL activation path (scheduler/worker),
    not just the synchronous deploy path."""
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    mgr = SslManager(db)
    domain = _mock_domain(runtime_proxy_target="thtwaat-nextjs-runtime-abc123:3000")
    mgr.repo.get_for_company = MagicMock(return_value=domain)
    mgr.repo.save = MagicMock(side_effect=lambda d: d)

    monkeypatch.setattr("app.ssl.certs.certs_root", lambda: tmp_path / "certs")
    with patch("app.ssl.manager.issue_certificate") as issue:
        cert = tmp_path / "c.pem"
        key = tmp_path / "k.pem"
        cert.write_text("c")
        key.write_text("k")
        issue.return_value = (True, "ok", cert, key, "abc123", datetime.now(timezone.utc) + timedelta(days=90))
        with patch("app.ssl.manager.generate_vhost", return_value=tmp_path / "v.conf") as gen:
            with patch("app.ssl.manager.reload_nginx", return_value=(True, "ok")):
                mgr.request(domain.id, domain.company_id, domain.company_id)

    _, kwargs = gen.call_args
    assert kwargs.get("runtime_proxy_target") == "thtwaat-nextjs-runtime-abc123:3000"


def test_set_runtime_proxy_target_regenerates_vhost_without_reissuing_cert(tmp_path, monkeypatch):
    """Zero-downtime cutover / rollback path: set_runtime_proxy_target() must
    rewrite the vhost using the EXISTING cert/key (no call to
    issue_certificate) and clear static_root_path."""
    db = MagicMock()
    mgr = SslManager(db)
    cert = tmp_path / "c.pem"
    key = tmp_path / "k.pem"
    cert.write_text("c")
    key.write_text("k")
    domain = _mock_domain(
        cert_path=str(cert), key_path=str(key), status=DomainStatus.LIVE, ssl_status=SslStatus.ACTIVE.value,
        static_root_path="/app/data/static-sites/c/s/old",
    )
    mgr.repo.get_for_company = MagicMock(return_value=domain)
    mgr.repo.save = MagicMock(side_effect=lambda d: d)

    with patch("app.ssl.manager.issue_certificate") as issue:
        with patch("app.ssl.manager.generate_vhost", return_value=tmp_path / "v.conf") as gen:
            with patch("app.ssl.manager.reload_nginx", return_value=(True, "ok")):
                mgr.set_runtime_proxy_target(
                    domain.id, domain.company_id, "thtwaat-nextjs-runtime-v2:3000", domain.company_id
                )

    issue.assert_not_called()
    _, kwargs = gen.call_args
    assert kwargs.get("runtime_proxy_target") == "thtwaat-nextjs-runtime-v2:3000"
    assert domain.runtime_proxy_target == "thtwaat-nextjs-runtime-v2:3000"
    assert domain.static_root_path is None  # mutually exclusive with static mode


def test_prod_compose_nginx_and_build_orchestrator_attach_runtime_network():
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"))
    assert "thtwaat_nextjs_runtime_net" in compose["networks"]
    assert "thtwaat_nextjs_runtime_net" in compose["services"]["nginx"]["networks"]
    assert "thtwaat_nextjs_runtime_net" in compose["services"]["build-orchestrator"]["networks"]
    # nginx never gets a filesystem mount for Next.js runtimes — it reaches
    # them purely over the network, unlike static_root_path's bind mount.
    nginx_mounts = [v.split(":")[0] for v in compose["services"]["nginx"]["volumes"]]
    assert "./data/nextjs-runtimes" not in nginx_mounts
