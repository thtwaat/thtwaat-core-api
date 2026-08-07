"""SSL certificate issuance helpers (Let's Encrypt HTTP-01 + simulate mode)."""
from __future__ import annotations

import logging
import secrets
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.config.settings import settings

logger = logging.getLogger(__name__)


def _is_production_environment() -> bool:
    app_env = getattr(settings, "app_env", None)
    if isinstance(app_env, str):
        app_env = app_env.strip().lower()
    else:
        app_env = ""

    hardened = getattr(settings, "is_hardened_env", False)
    if isinstance(hardened, bool):
        hardened_value = hardened
    elif isinstance(hardened, str):
        hardened_value = hardened.strip().lower() in {"1", "true", "yes", "on"}
    else:
        hardened_value = False

    return hardened_value or app_env in {"production", "prod", "staging"}


def certs_root() -> Path:
    # NOTE: this runs inside the api/worker containers, which mount the shared
    # ssl volume at SSL_CERTS_DIR's path (./nginx/ssl -> /app/nginx/ssl in prod),
    # not at nginx's own /etc/nginx/ssl. generate_vhost() remaps the path for
    # nginx's consumption via NGINX_CERT_CONTAINER_PREFIX — don't hardcode
    # nginx's absolute path here or issued certs never reach the shared volume.
    root = Path(getattr(settings, "SSL_CERTS_DIR", "nginx/ssl/domains"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def webroot_path() -> Path:
    root = Path(getattr(settings, "SSL_WEBROOT_DIR", "nginx/acme-webroot"))
    root.mkdir(parents=True, exist_ok=True)
    (root / ".well-known" / "acme-challenge").mkdir(parents=True, exist_ok=True)
    return root


def domain_cert_dir(hostname: str) -> Path:
    safe = hostname.replace("*", "_wildcard_")
    d = certs_root() / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


def issue_self_signed(hostname: str, days: int = 90) -> Tuple[Path, Path, str, datetime]:
    """Simulate Let's Encrypt for local/dev — produces real PEM files nginx can load."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=days)
    serial = x509.random_serial_number()
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(serial)
        .not_valid_before(now)
        .not_valid_after(expires)
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(hostname)]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    d = domain_cert_dir(hostname)
    cert_path = d / "fullchain.pem"
    key_path = d / "privkey.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return cert_path, key_path, format(serial, "x"), expires


def run_certbot_http01(hostname: str, email: Optional[str] = None) -> Tuple[bool, str, Optional[Path], Optional[Path]]:
    """
    Issue via certbot HTTP-01 (production).
    Requires certbot installed and nginx serving SSL_WEBROOT_DIR at /.well-known/acme-challenge/
    """
    email = email or getattr(settings, "SSL_ACME_EMAIL", None) or "ops@thtwaat.com"
    staging = getattr(settings, "SSL_ACME_STAGING", True)
    if _is_production_environment():
        staging = False
    webroot = str(webroot_path())
    cmd = [
        "certbot",
        "certonly",
        "--non-interactive",
        "--agree-tos",
        "--email",
        email,
        "--webroot",
        "-w",
        webroot,
        "-d",
        hostname,
    ]
    if staging:
        cmd.append("--staging")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "certbot failed").strip()
            logger.error("certbot failed for %s: %s", hostname, err)
            return False, err, None, None

        live = Path("/etc/letsencrypt/live") / hostname
        cert = live / "fullchain.pem"
        key = live / "privkey.pem"
        # Copy into our managed dir for nginx volume mount
        dest = domain_cert_dir(hostname)
        if cert.exists() and key.exists():
            dest_cert = dest / "fullchain.pem"
            dest_key = dest / "privkey.pem"
            dest_cert.write_bytes(cert.read_bytes())
            dest_key.write_bytes(key.read_bytes())
            return True, "certificate issued", dest_cert, dest_key
        return True, "certbot succeeded but live files missing", None, None
    except FileNotFoundError:
        return False, "certbot not installed", None, None
    except Exception as exc:
        return False, str(exc), None, None


def issue_certificate(hostname: str, *, wildcard: bool = False) -> Tuple[bool, str, Optional[Path], Optional[Path], Optional[str], Optional[datetime]]:
    """
    Issue certificate based on SSL_MODE setting.
    DNS-01 / wildcard: future-ready — currently returns guidance error unless simulate.
    """
    mode = (getattr(settings, "SSL_MODE", None) or "simulate").lower()

    if wildcard and mode != "simulate":
        return (
            False,
            "Wildcard requires DNS-01 challenge (not yet automated). Use SSL_MODE=simulate for lab.",
            None,
            None,
            None,
            None,
        )

    if mode == "certbot":
        ok, msg, cert, key = run_certbot_http01(hostname)
        if not ok:
            return False, msg, None, None, None, None
        serial = secrets.token_hex(8)
        expires = datetime.now(timezone.utc) + timedelta(days=90)
        return True, msg, cert, key, serial, expires

    if _is_production_environment():
        return (
            False,
            "Production deployments must request a Let's Encrypt certificate after DNS verification. Set SSL_MODE=certbot and ensure the hostname resolves.",
            None,
            None,
            None,
            None,
        )

    # Default: simulate (dev / one-click lab)
    cert, key, serial, expires = issue_self_signed(hostname)
    return True, "simulated certificate issued", cert, key, serial, expires


def read_cert_expiry(cert_path: Path) -> Optional[datetime]:
    try:
        data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(data)
        exp = cert.not_valid_after_utc if hasattr(cert, "not_valid_after_utc") else cert.not_valid_after.replace(tzinfo=timezone.utc)
        return exp
    except Exception as exc:
        logger.warning("read_cert_expiry failed: %s", exc)
        return None
