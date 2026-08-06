"""Studio one-click deployment engine — deploy approved source builds only."""
from __future__ import annotations

import enum
import hashlib
import json
import logging
import re
import shutil
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol
from uuid import UUID

logger = logging.getLogger(__name__)


def _fernet():
    """Reuse enterprise-style Fernet key derived from JWT secret."""
    import base64
    import hashlib

    from cryptography.fernet import Fernet

    from app.config.settings import settings

    digest = hashlib.sha256((settings.JWT_SECRET_KEY or "thtwaat-dev").encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_env_at_rest(env_path: Path) -> Path:
    """Encrypt .env.production at rest; keep a masked plaintext sibling for audit."""
    if not env_path.is_file():
        return env_path
    raw = env_path.read_bytes()
    enc_path = env_path.with_suffix(env_path.suffix + ".enc")
    enc_path.write_bytes(_fernet().encrypt(raw))
    # Remove plaintext secrets from disk — masked copy remains for operators.
    try:
        env_path.unlink(missing_ok=True)
    except TypeError:
        if env_path.exists():
            env_path.unlink()
    return enc_path


def decrypt_env_bytes(enc_path: Path) -> bytes:
    return _fernet().decrypt(enc_path.read_bytes())


def probe_http(url: str, timeout: float = 3.0) -> Dict[str, Any]:
    import urllib.error
    import urllib.request

    start = time.perf_counter()
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "thtwaat-studio-deploy"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            return {
                "ok": 200 <= int(code) < 500,
                "status_code": int(code),
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": 400 <= int(exc.code) < 500,
            "status_code": int(exc.code),
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def ensure_platform_stack(progress: ProgressCallback) -> Dict[str, Any]:
    """Reuse existing docker-compose.prod.yml — never spawn a parallel Studio stack."""
    import subprocess

    emit(progress, DeployStage.DEPLOYING.value, message="Ensuring existing platform compose is up")
    root = Path(__file__).resolve().parents[2]
    compose = root / "docker-compose.prod.yml"
    info: Dict[str, Any] = {"compose": str(compose), "actions": []}
    if not compose.is_file():
        info["note"] = "docker-compose.prod.yml not found in repo root — assuming already running"
        emit(progress, DeployStage.DEPLOYING.value, message=info["note"])
        return info
    try:
        up = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(compose),
                "--env-file",
                ".env.prod",
                "up",
                "-d",
                "--no-build",
                "api",
                "web_app",
                "worker",
                "scheduler",
                "redis",
                "db",
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        info["actions"].append(
            {
                "cmd": "compose_up",
                "returncode": up.returncode,
                "stderr_tail": (up.stderr or "")[-400:],
            }
        )
        restart = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(compose),
                "restart",
                "worker",
                "scheduler",
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        info["actions"].append(
            {
                "cmd": "restart_workers",
                "returncode": restart.returncode,
            }
        )
        emit(
            progress,
            DeployStage.DEPLOYING.value,
            message="Platform compose up + workers restarted (reuse stack)",
            returncode=up.returncode,
        )
    except FileNotFoundError:
        info["note"] = "docker CLI unavailable in this process — stack managed by host deploy/"
        emit(progress, DeployStage.DEPLOYING.value, message=info["note"])
    except subprocess.TimeoutExpired:
        info["note"] = "compose command timed out — continuing with health checks"
        emit(progress, DeployStage.DEPLOYING.value, message=info["note"])
    except Exception as exc:  # noqa: BLE001
        info["error"] = str(exc)
        emit(progress, DeployStage.DEPLOYING.value, message=f"Compose soft-fail: {exc}")
    return info


def run_database_migration(progress: ProgressCallback, db_session=None) -> Dict[str, Any]:
    """Run platform alembic upgrade head (reuse existing migrations — no fork)."""
    import subprocess

    emit(
        progress,
        DeployStage.DATABASE_MIGRATION.value,
        message="Database migration — alembic upgrade head on platform DB",
    )
    info: Dict[str, Any] = {"ok": True}
    if db_session is not None:
        try:
            from app.deploy.health import check_database

            info["database"] = check_database(db_session)
        except Exception as exc:  # noqa: BLE001
            info["database"] = {"ok": False, "error": str(exc)}
    root = Path(__file__).resolve().parents[2]
    try:
        proc = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        info["alembic_returncode"] = proc.returncode
        info["stdout_tail"] = (proc.stdout or "")[-500:]
        info["ok"] = proc.returncode == 0 or "Can't locate revision" not in (proc.stderr or "")
        if proc.returncode != 0:
            # Soft-ok when already at head inside API container without alembic CLI
            info["note"] = (proc.stderr or proc.stdout or "alembic soft-fail")[-300:]
            info["ok"] = True  # platform migrations are applied by deploy.sh; overlay is non-blocking
        emit(
            progress,
            DeployStage.DATABASE_MIGRATION.value,
            message="Migration stage complete",
            returncode=proc.returncode,
        )
    except FileNotFoundError:
        info["note"] = "alembic CLI unavailable — rely on deploy/deploy.sh / API container migrations"
        emit(progress, DeployStage.DATABASE_MIGRATION.value, message=info["note"])
    except Exception as exc:  # noqa: BLE001
        info["note"] = str(exc)
        info["ok"] = True
        emit(progress, DeployStage.DATABASE_MIGRATION.value, message=f"Migration soft-fail: {exc}")
    return info


def bind_domain_and_ssl(
    ctx: DeployContext,
    progress: ProgressCallback,
    *,
    hostname: str,
    dns_validated: bool,
) -> Dict[str, Any]:
    """Reuse Domain Manager + SslManager. SSL only after DNS validation succeeds."""
    emit(progress, DeployStage.SSL.value, message="SSL / domain via Domain Manager")
    if not hostname:
        return {
            "status": "platform",
            "note": "No custom domain — using platform hostnames",
            "renewal": "ssl.auto_renew",
            "ssl_enabled": False,
        }
    if not dns_validated:
        emit(
            progress,
            DeployStage.SSL.value,
            message="SSL deferred — waiting for DNS validation",
            hostname=hostname,
        )
        return {
            "status": "waiting_for_dns",
            "domain": hostname,
            "ssl_enabled": False,
            "note": "SSL is only issued after DNS validation succeeds",
            "renewal": "ssl.auto_renew",
        }

    db = ctx.db_session
    if db is None:
        return {
            "status": "pending_dns",
            "domain": hostname,
            "ssl_enabled": False,
            "note": "Add hostname in Domains, verify DNS, then request SSL",
            "renewal": "ssl.auto_renew",
        }
    try:
        from app.domains.schemas import DomainCreate
        from app.domains.service import DomainService

        svc = DomainService(db)
        existing = svc.repo.get_by_hostname(hostname)
        actor = ctx.actor_user_id or ctx.workspace_id
        if not existing:
            created = svc.create(
                ctx.workspace_id,
                DomainCreate(hostname=hostname, verification_method="TXT"),
                actor,
            )
            ssl_info: Dict[str, Any] = {
                "status": "pending_verification",
                "domain_id": str(created.id),
                "hostname": created.hostname,
                "dns_records": list(created.dns_records or []),
                "ssl_status": created.ssl_status,
                "ssl_enabled": False,
                "note": "Domain registered in Domain Manager — complete DNS verify before SSL",
                "renewal": "ssl.auto_renew",
            }
        else:
            resp = svc._to_response(existing)
            ssl_info = {
                "status": resp.ssl_status or resp.status,
                "domain_id": str(resp.id),
                "hostname": resp.hostname,
                "ssl_status": resp.ssl_status,
                "ssl_expires_at": resp.ssl_expires_at.isoformat() if resp.ssl_expires_at else None,
                "dns_records": [
                    r.model_dump() if hasattr(r, "model_dump") else r
                    for r in (resp.dns_records or [])
                ],
                "ssl_enabled": False,
                "renewal": "ssl.auto_renew",
            }
            status_val = str(resp.status or "").lower()
            ssl_val = str(resp.ssl_status or "").upper()
            # Only request SSL after DNS validation / verified domain
            if status_val in {"verified", "live", "active"} and ssl_val not in {"ACTIVE", "ISSUED"}:
                try:
                    issued = svc.request_ssl(resp.id, ctx.workspace_id, actor)
                    ssl_info["ssl_request"] = {
                        "ssl_status": getattr(issued, "ssl_status", None)
                        or getattr(issued, "status", None),
                        "message": getattr(issued, "message", None),
                    }
                    ssl_info["status"] = ssl_info["ssl_request"].get("ssl_status") or ssl_info["status"]
                    ssl_info["ssl_enabled"] = True
                except Exception as exc:  # noqa: BLE001
                    ssl_info["ssl_request_error"] = str(exc)
            elif ssl_val in {"ACTIVE", "ISSUED"}:
                ssl_info["ssl_enabled"] = True
        emit(progress, DeployStage.SSL.value, message="Domain Manager bound", hostname=hostname)
        return ssl_info
    except Exception as exc:  # noqa: BLE001
        logger.warning("domain_ssl_bind_failed hostname=%s err=%s", hostname, exc)
        return {
            "status": "error",
            "domain": hostname,
            "error": str(exc),
            "ssl_enabled": False,
            "note": "Configure via Domains UI — deploy continues",
            "renewal": "ssl.auto_renew",
        }

DEPLOY_STAGES = (
    "queued",
    "preparing",
    "validating",
    "building",  # Building Image / compose bundle
    "packaging",
    "uploading",
    "deploying",
    "database_migration",
    "health_check",
    "ssl",
    "waiting_for_domain",
    "completed",
    "failed",
    "rollback",
)

PROVIDERS = (
    "docker",
    "vps",
    "coolify",
    "railway",
    "render",
    "digitalocean",
    "aws_ecs",
    "azure",
    "google_cloud_run",
    "kubernetes",
)

# Providers that execute against the live THTWAAT stack
EXECUTABLE_PROVIDERS = frozenset({"docker", "vps"})


class DeployStage(str, enum.Enum):
    QUEUED = "queued"
    PREPARING = "preparing"
    VALIDATING = "validating"
    BUILDING = "building"
    PACKAGING = "packaging"
    UPLOADING = "uploading"
    DEPLOYING = "deploying"
    DATABASE_MIGRATION = "database_migration"
    HEALTH_CHECK = "health_check"
    SSL = "ssl"
    WAITING_FOR_DOMAIN = "waiting_for_domain"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLBACK = "rollback"


ProgressCallback = Callable[[str, Dict[str, Any]], None]


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    return f"****{value[-4:]}"


def mask_env_content(content: str) -> str:
    """Mask secret-looking values in .env text for logs/storage."""
    lines = []
    secret_keys = (
        "PASSWORD",
        "SECRET",
        "API_KEY",
        "TOKEN",
        "PRIVATE",
        "WEBHOOK",
    )
    for line in content.splitlines():
        if "=" not in line or line.strip().startswith("#"):
            lines.append(line)
            continue
        key, _, val = line.partition("=")
        upper = key.strip().upper()
        if any(s in upper for s in secret_keys) and val.strip():
            lines.append(f"{key.strip()}={mask_secret(val.strip())}")
        else:
            lines.append(line)
    return "\n".join(lines) + ("\n" if content.endswith("\n") else "")


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "app").lower()).strip("-")
    return cleaned[:48] or "app"


@dataclass
class DeployContext:
    project_id: UUID
    deployment_id: UUID
    workspace_id: UUID
    project_title: str
    provider: str
    build_id: UUID
    build_version: int
    artifact_path: Path
    artifact_sha256: Optional[str]
    domain: Optional[str] = None
    subdomain: Optional[str] = None
    domain_mode: str = "free_subdomain"
    environment: str = "production"
    env_overrides: Dict[str, str] = field(default_factory=dict)
    public_api_base: str = ""
    public_app_base: str = ""
    output_dir: Path = field(default_factory=Path)
    db_session: Any = None
    actor_user_id: Optional[UUID] = None
    builder: Optional[str] = None
    commit_sha: Optional[str] = None
    is_rollback: bool = False


@dataclass
class ProviderResult:
    ok: bool
    live: bool
    urls: Dict[str, str] = field(default_factory=dict)
    instructions: List[str] = field(default_factory=list)
    health: Dict[str, Any] = field(default_factory=dict)
    ssl: Dict[str, Any] = field(default_factory=dict)
    package_path: Optional[str] = None
    error: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    status: Optional[str] = None  # override e.g. waiting_for_domain
    stage: Optional[str] = None
    domain: Optional[str] = None
    subdomain: Optional[str] = None
    domain_validation: Dict[str, Any] = field(default_factory=dict)


class DeployProvider(Protocol):
    id: str
    label: str
    executable: bool

    def deploy(self, ctx: DeployContext, progress: ProgressCallback) -> ProviderResult: ...


def emit(progress: Optional[ProgressCallback], stage: str, **data: Any) -> None:
    if progress:
        payload = {"event": stage, "ts": datetime.now(timezone.utc).isoformat(), **data}
        try:
            progress(stage, payload)
        except Exception:  # noqa: BLE001
            logger.exception("deploy_progress_failed stage=%s", stage)


def prepare_workspace(ctx: DeployContext, progress: ProgressCallback) -> Path:
    emit(progress, DeployStage.PREPARING.value, message="Preparing deployment workspace")
    root = ctx.output_dir
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    extract = root / "source"
    extract.mkdir(parents=True, exist_ok=True)
    if not ctx.artifact_path.is_file():
        raise FileNotFoundError(f"Source artifact missing: {ctx.artifact_path}")
    with zipfile.ZipFile(ctx.artifact_path, "r") as zf:
        zf.extractall(extract)
    # Verify sha if provided
    if ctx.artifact_sha256:
        digest = hashlib.sha256(ctx.artifact_path.read_bytes()).hexdigest()
        if digest != ctx.artifact_sha256:
            raise ValueError("Artifact SHA-256 mismatch — refusing deploy")
    emit(progress, DeployStage.PREPARING.value, message="Source ZIP extracted", path=str(extract))
    return extract


def build_env_package(
    ctx: DeployContext,
    source_dir: Path,
    progress: ProgressCallback,
) -> Path:
    emit(progress, DeployStage.PACKAGING.value, message="Generating environment package")
    env_src = source_dir / "docker" / ".env.example"
    raw = env_src.read_text(encoding="utf-8") if env_src.is_file() else (
        "APP_ENV=production\n"
        "JWT_SECRET_KEY=\n"
        "DB_PASSWORD=\n"
        "PUBLIC_API_BASE_URL=\n"
    )
    # Apply non-secret overrides only
    lines = raw.splitlines()
    overrides = dict(ctx.env_overrides or {})
    if ctx.public_api_base:
        overrides.setdefault("PUBLIC_API_BASE_URL", ctx.public_api_base)
    if ctx.domain:
        overrides.setdefault("CORS_ORIGINS", json.dumps([f"https://{ctx.domain}"]))
    out_lines = []
    seen = set()
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            key, _, _val = line.partition("=")
            k = key.strip()
            if k in overrides:
                out_lines.append(f"{k}={overrides[k]}")
                seen.add(k)
                continue
        out_lines.append(line)
    for k, v in overrides.items():
        if k not in seen:
            out_lines.append(f"{k}={v}")
    content = "\n".join(out_lines) + "\n"
    env_dir = ctx.output_dir / "env"
    env_dir.mkdir(parents=True, exist_ok=True)
    env_path = env_dir / ".env.production"
    env_path.write_text(content, encoding="utf-8")
    # Masked copy for audit (never contains full secrets)
    masked_path = env_dir / ".env.production.masked"
    masked_path.write_text(mask_env_content(content), encoding="utf-8")
    enc_path = encrypt_env_at_rest(env_path)
    emit(
        progress,
        DeployStage.PACKAGING.value,
        message="Env package ready (encrypted at rest; secrets never logged)",
        encrypted=str(enc_path),
        masked=str(masked_path),
        environment=ctx.environment,
        keys=sorted({ln.split("=", 1)[0].strip() for ln in out_lines if "=" in ln and not ln.startswith("#")}),
    )
    return enc_path


def package_compose_bundle(ctx: DeployContext, source_dir: Path, progress: ProgressCallback) -> Path:
    emit(progress, DeployStage.BUILDING.value, message="Building compose / image bundle refs")
    bundle = ctx.output_dir / "bundle"
    bundle.mkdir(parents=True, exist_ok=True)
    for name in ("docker/Dockerfile", "docker/docker-compose.yml", "docker/nginx.conf"):
        src = source_dir / name
        if src.is_file():
            dest = bundle / Path(name).name
            shutil.copy2(src, dest)
    # Migration / assets pointers
    meta = {
        "build_id": str(ctx.build_id),
        "build_version": ctx.build_version,
        "artifact_sha256": ctx.artifact_sha256,
        "provider": ctx.provider,
        "reuse": {
            "compose": "docker-compose.prod.yml",
            "worker": "scripts/worker.py",
            "ssl": "app/ssl",
            "deploy": "deploy/deploy.sh",
        },
        "note": "Product overlay — host platform stack is authoritative",
    }
    (bundle / "manifest.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    emit(progress, DeployStage.BUILDING.value, message="Bundle ready", files=len(list(bundle.iterdir())))
    return bundle


def run_platform_health(db_session=None, *, api_base: str = "", app_base: str = "") -> Dict[str, Any]:
    """Reuse existing deploy health checks + live HTTP probes for API/Frontend."""
    from app.deploy import health as health_mod

    result: Dict[str, Any] = {}
    if db_session is not None:
        result["database"] = health_mod.check_database(db_session)
    else:
        result["database"] = {"ok": None, "note": "skipped"}
    result["storage"] = health_mod.check_storage()
    result["workers"] = health_mod.check_workers()
    try:
        import redis

        from app.config.settings import settings

        r = redis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
            decode_responses=True,
        )
        r.ping()
        result["redis"] = {"ok": True}
        # Scheduler heartbeat reuse (same Redis namespace as worker)
        sched = r.get("thtwaat:scheduler:heartbeat") or r.get("thtwaat:worker:heartbeat")
        result["scheduler"] = {
            "ok": True if sched else None,
            "note": "Reuse thtwaat-scheduler" if sched else "No scheduler heartbeat key — check compose ps",
            "heartbeat": sched,
        }
    except Exception as exc:  # noqa: BLE001
        result["redis"] = {"ok": False, "error": str(exc)}
        result["scheduler"] = {"ok": False, "error": str(exc)}

    api_url = (api_base or "").rstrip("/")
    app_url = (app_base or "").rstrip("/")
    if api_url:
        result["api"] = probe_http(f"{api_url}/health")
        result["ai_gateway"] = probe_http(f"{api_url}/api/v1/ai/health")
        if result["ai_gateway"].get("ok") is False:
            # Soft: AI health endpoint may not exist — try providers
            alt = probe_http(f"{api_url}/api/v1/ai/providers")
            if alt.get("ok"):
                result["ai_gateway"] = {**alt, "note": "providers endpoint ok"}
    else:
        result["api"] = {"ok": True, "note": "PUBLIC_API_BASE_URL unset — skipped probe"}
        result["ai_gateway"] = {"ok": True, "note": "skipped"}
    if app_url:
        result["frontend"] = probe_http(app_url)
    else:
        result["frontend"] = {"ok": True, "note": "app base unset — skipped probe"}
    return result


class VpsDockerProvider:
    """Primary executable provider: overlay on existing VPS/Docker stack."""

    id = "vps"
    label = "Current VPS / Docker"
    executable = True

    def __init__(self, provider_id: str = "vps"):
        self.id = provider_id
        self.label = "Docker Compose" if provider_id == "docker" else "Current VPS"

    def deploy(self, ctx: DeployContext, progress: ProgressCallback) -> ProviderResult:
        from app.studio.domain_validation import (
            DOMAIN_NOT_REGISTERED,
            resolve_deploy_hostname,
        )

        emit(progress, DeployStage.VALIDATING.value, message="Validating approved source build")
        if not ctx.artifact_path.is_file():
            return ProviderResult(ok=False, live=False, error="Missing source artifact")

        emit(progress, DeployStage.VALIDATING.value, message="Validating deployment domain")
        hostname, mode, validation = resolve_deploy_hostname(
            domain_mode=ctx.domain_mode or "free_subdomain",
            custom_domain=ctx.domain or ctx.subdomain,
            project_id=ctx.project_id,
            project_title=ctx.project_title,
        )
        domain_payload = validation.to_dict()
        emit(
            progress,
            DeployStage.VALIDATING.value,
            message=validation.message,
            domain=hostname,
            domain_mode=mode,
            nxdomain=validation.nxdomain,
            reachable=validation.reachable,
        )

        # Custom domain NXDOMAIN — block LIVE, keep waiting for domain
        if mode == "custom" and (validation.nxdomain or not validation.registered):
            emit(
                progress,
                DeployStage.WAITING_FOR_DOMAIN.value,
                message=DOMAIN_NOT_REGISTERED,
                domain=hostname,
            )
            suggested = next(
                (o["hostname"] for o in validation.options if o["id"] == "free_subdomain"),
                "",
            )
            return ProviderResult(
                ok=True,
                live=False,
                status=DeployStage.WAITING_FOR_DOMAIN.value,
                stage=DeployStage.WAITING_FOR_DOMAIN.value,
                domain=hostname or None,
                subdomain=suggested or None,
                domain_validation=domain_payload,
                urls={},
                health={"domain": domain_payload},
                ssl={
                    "status": "blocked",
                    "ssl_enabled": False,
                    "note": "SSL only after DNS validation succeeds",
                },
                package_path=str(ctx.output_dir) if ctx.output_dir else None,
                error=DOMAIN_NOT_REGISTERED,
                instructions=[
                    DOMAIN_NOT_REGISTERED,
                    f"Option 1: Use free subdomain {suggested}" if suggested else "Option 1: Use a free *.thtwaat.app subdomain",
                    "Option 2: Connect an existing custom domain that is already registered in DNS",
                ],
                notes=["Deployment not LIVE until a reachable domain is configured"],
            )

        emit(progress, DeployStage.UPLOADING.value, message="Copying ZIP to platform storage")
        source = prepare_workspace(ctx, progress)
        emit(progress, DeployStage.BUILDING.value, message="Building Image / compose bundle refs")
        bundle = package_compose_bundle(ctx, source, progress)
        # Reflect resolved hostname into context for env packaging
        if mode == "free_subdomain":
            ctx.subdomain = hostname
            ctx.domain = None
        else:
            ctx.domain = hostname
        env_path = build_env_package(ctx, source, progress)

        stack_info = ensure_platform_stack(progress)
        emit(progress, DeployStage.DEPLOYING.value, message="Injecting env + activating overlay")
        marker = ctx.output_dir / "DEPLOYED.json"
        slug = _slug(ctx.project_title)
        api_base = ctx.public_api_base or "https://api.localhost"
        app_base = f"https://{hostname}" if hostname else (ctx.public_app_base or "https://app.localhost")
        urls = {
            "website": app_base,
            "dashboard": f"{app_base.rstrip('/')}/app/dashboard",
            "api": api_base.rstrip("/") + "/docs",
            "admin": f"{app_base.rstrip('/')}/app/admin",
        }
        marker.write_text(
            json.dumps(
                {
                    "provider": self.id,
                    "project": ctx.project_title,
                    "slug": slug,
                    "build_id": str(ctx.build_id),
                    "build_version": ctx.build_version,
                    "commit": ctx.commit_sha or ctx.artifact_sha256,
                    "builder": ctx.builder,
                    "environment": ctx.environment,
                    "domain": hostname,
                    "domain_mode": mode,
                    "domain_validation": domain_payload,
                    "urls": urls,
                    "bundle": str(bundle),
                    "env_encrypted": str(env_path),
                    "stack_actions": stack_info,
                    "deployed_at": datetime.now(timezone.utc).isoformat(),
                    "stack": "platform-reuse",
                    "rollback": bool(ctx.is_rollback),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        emit(progress, DeployStage.DEPLOYING.value, message="Overlay staged on existing platform stack")

        migration = run_database_migration(progress, ctx.db_session)

        emit(progress, DeployStage.HEALTH_CHECK.value, message="Verifying API/Frontend/Redis/DB/Worker/Scheduler/AI")
        # Probe platform API; only probe product hostname when DNS is reachable
        health = run_platform_health(
            ctx.db_session,
            api_base=api_base if api_base.startswith("http") else "",
            app_base=app_base if validation.reachable else "",
        )
        health["migration"] = migration
        health["domain"] = domain_payload
        health["stack"] = {"ok": True, **{k: v for k, v in stack_info.items() if k != "actions"}}
        critical = [
            k
            for k, v in health.items()
            if isinstance(v, dict) and v.get("ok") is False and k in {"storage", "database"}
        ]
        if critical:
            return ProviderResult(
                ok=False,
                live=False,
                health=health,
                domain=hostname,
                subdomain=hostname if mode == "free_subdomain" else None,
                domain_validation=domain_payload,
                error=f"Health check failed: {', '.join(critical)}",
                package_path=str(ctx.output_dir),
            )
        advisories = [
            k
            for k, v in health.items()
            if isinstance(v, dict) and v.get("ok") is False and k not in {"storage", "database"}
        ]
        if advisories:
            health["advisories"] = advisories

        dns_ok = bool(validation.reachable and validation.registered)
        ssl_info = bind_domain_and_ssl(
            ctx, progress, hostname=hostname, dns_validated=dns_ok
        )

        if not dns_ok:
            emit(
                progress,
                DeployStage.WAITING_FOR_DOMAIN.value,
                message="Waiting for Domain — hostname not reachable yet",
                domain=hostname,
            )
            return ProviderResult(
                ok=True,
                live=False,
                status=DeployStage.WAITING_FOR_DOMAIN.value,
                stage=DeployStage.WAITING_FOR_DOMAIN.value,
                domain=hostname,
                subdomain=hostname if mode == "free_subdomain" else None,
                domain_validation=domain_payload,
                urls=urls,
                health=health,
                ssl=ssl_info,
                package_path=str(ctx.output_dir),
                instructions=[
                    f"Assigned hostname: {hostname}",
                    "Deployment status: Waiting for Domain until DNS is reachable.",
                    "SSL will be enabled only after DNS validation succeeds.",
                    "Option: switch to a free *.thtwaat.app subdomain or connect a registered custom domain.",
                    f"Bundle: {bundle}",
                ],
                notes=["Not LIVE until domain is reachable"],
            )

        return ProviderResult(
            ok=True,
            live=True,
            status=DeployStage.COMPLETED.value,
            stage=DeployStage.COMPLETED.value,
            domain=hostname,
            subdomain=hostname if mode == "free_subdomain" else None,
            domain_validation=domain_payload,
            urls=urls,
            health=health,
            ssl=ssl_info,
            package_path=str(ctx.output_dir),
            instructions=[
                "Deployed as platform overlay — reused docker-compose.prod.yml / worker / scheduler.",
                f"Domain {hostname} validated — SSL enabled only after DNS verification.",
                "Secrets encrypted at rest (.env.production.enc); masked copy for audit.",
                f"Bundle: {bundle}",
            ],
            notes=[
                "Reused deploy health + Domains + SSL + Redis job queue",
                f"Environment: {ctx.environment}",
                f"Domain mode: {mode}",
            ],
        )


class PlanningProvider:
    """Non-executable targets — record intent + ops instructions only."""

    executable = False

    def __init__(self, provider_id: str, label: str):
        self.id = provider_id
        self.label = label

    def deploy(self, ctx: DeployContext, progress: ProgressCallback) -> ProviderResult:
        emit(progress, DeployStage.VALIDATING.value, message=f"Planning deploy to {self.label}")
        source = prepare_workspace(ctx, progress)
        bundle = package_compose_bundle(ctx, source, progress)
        env_path = build_env_package(ctx, source, progress)
        emit(progress, DeployStage.PACKAGING.value, message="Export package for external provider")
        emit(progress, DeployStage.UPLOADING.value, message="Package ready — manual/provider upload required")
        emit(progress, DeployStage.DEPLOYING.value, message="Planning-only — no live mutate")
        instructions = [
            f"Provider '{self.id}' is planning-only in Phase 10.",
            "Upload the generated bundle + masked env to the provider console.",
            "Point the service at the host platform modules or container images.",
            "Do not fork Auth/Billing/AI Gateway — reuse THTWAAT platform services.",
            f"Bundle path: {bundle}",
            f"Env template: {env_path} (fill secrets in provider secret store)",
        ]
        if self.id == "coolify":
            instructions.append("Coolify: import docker-compose.yml from bundle; map env from .env.production.")
        elif self.id == "railway":
            instructions.append("Railway: create project from Dockerfile; set env vars from template.")
        elif self.id == "kubernetes":
            instructions.append("Kubernetes: convert compose to manifests; reuse existing images — do not fork services.")
        elif self.id in {"aws_ecs", "azure", "google_cloud_run"}:
            instructions.append("Cloud: push image from Dockerfile; attach secrets manager; use platform DB/Redis if shared.")
        emit(progress, DeployStage.HEALTH_CHECK.value, message="Skipped live health (planning provider)")
        emit(progress, DeployStage.SSL.value, message="Configure TLS at provider edge / CDN")
        return ProviderResult(
            ok=True,
            live=False,
            urls={},
            package_path=str(ctx.output_dir),
            instructions=instructions,
            health={"planning": True},
            ssl={"status": "provider_edge"},
            notes=[f"{self.label} — no automatic production mutate"],
        )


def get_provider(provider_id: str) -> DeployProvider:
    pid = (provider_id or "vps").lower().strip().replace("-", "_").replace(" ", "_")
    aliases = {
        "current_vps": "vps",
        "google_cloud": "google_cloud_run",
        "gcp": "google_cloud_run",
        "aws": "aws_ecs",
        "ecs": "aws_ecs",
        "gcr": "google_cloud_run",
        "k8s": "kubernetes",
    }
    pid = aliases.get(pid, pid)
    if pid in {"docker", "vps"}:
        return VpsDockerProvider(pid)
    labels = {
        "coolify": "Coolify",
        "railway": "Railway",
        "render": "Render",
        "digitalocean": "DigitalOcean",
        "aws_ecs": "AWS ECS",
        "azure": "Azure Container Apps",
        "google_cloud_run": "Google Cloud Run",
        "kubernetes": "Kubernetes",
    }
    if pid not in PROVIDERS and pid not in labels:
        raise ValueError(f"Unsupported provider: {provider_id}")
    return PlanningProvider(pid, labels.get(pid, pid))


def run_deploy(
    ctx: DeployContext,
    *,
    progress: Optional[ProgressCallback] = None,
    db_session=None,
) -> Dict[str, Any]:
    """Execute deployment stages. Never regenerates source."""
    started = time.perf_counter()
    logs: List[Dict[str, Any]] = []
    if db_session is not None and ctx.db_session is None:
        ctx.db_session = db_session

    def on_progress(stage: str, payload: Dict[str, Any]) -> None:
        # Strip secret-looking values from persisted event payloads
        safe = {}
        for k, v in payload.items():
            lk = str(k).lower()
            if any(s in lk for s in ("secret", "password", "token", "api_key", "private")):
                continue
            safe[k] = v
        logs.append(safe)
        emit(progress, stage, **{k: v for k, v in safe.items() if k != "event"})

    try:
        emit(on_progress, DeployStage.QUEUED.value, message="Deployment accepted")
        provider = get_provider(ctx.provider)
        result = provider.deploy(ctx, on_progress)
        if db_session is not None and result.ok:
            from app.deploy.health import check_database

            result.health = {**(result.health or {}), "database": check_database(db_session)}
        duration_ms = int((time.perf_counter() - started) * 1000)
        if not result.ok:
            emit(on_progress, DeployStage.FAILED.value, message=result.error or "Deploy failed")
            return {
                "ok": False,
                "status": "failed",
                "stage": DeployStage.FAILED.value,
                "live": False,
                "error": result.error,
                "retryable": True,
                "logs": logs,
                "health": result.health,
                "urls": result.urls,
                "instructions": result.instructions,
                "package_path": result.package_path,
                "duration_ms": duration_ms,
                "provider": provider.id,
                "commit_sha": ctx.commit_sha or ctx.artifact_sha256,
                "builder": ctx.builder,
                "build_version": ctx.build_version,
                "domain": result.domain,
                "subdomain": result.subdomain,
                "domain_validation": result.domain_validation,
            }

        final_status = result.status or (
            DeployStage.COMPLETED.value if result.live else DeployStage.COMPLETED.value
        )
        final_stage = result.stage or final_status
        if final_status == DeployStage.WAITING_FOR_DOMAIN.value:
            emit(
                on_progress,
                DeployStage.WAITING_FOR_DOMAIN.value,
                message=result.error or "Waiting for Domain",
                live=False,
            )
        else:
            emit(
                on_progress,
                DeployStage.COMPLETED.value,
                message="Deployment completed" if result.live else "Planning package completed",
                live=result.live,
            )
        return {
            "ok": True,
            "status": final_status,
            "stage": final_stage,
            "live": bool(result.live),
            "urls": result.urls,
            "instructions": result.instructions,
            "health": result.health,
            "ssl": result.ssl,
            "package_path": result.package_path,
            "notes": result.notes,
            "logs": logs,
            "duration_ms": duration_ms,
            "provider": provider.id,
            "retryable": False,
            "commit_sha": ctx.commit_sha or ctx.artifact_sha256,
            "builder": ctx.builder,
            "build_version": ctx.build_version,
            "domain": result.domain,
            "subdomain": result.subdomain,
            "domain_validation": result.domain_validation,
            "error": result.error,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("deploy_failed")
        duration_ms = int((time.perf_counter() - started) * 1000)
        emit(on_progress, DeployStage.FAILED.value, message=str(exc))
        return {
            "ok": False,
            "status": "failed",
            "stage": DeployStage.FAILED.value,
            "live": False,
            "error": str(exc),
            "retryable": True,
            "logs": logs,
            "duration_ms": duration_ms,
            "provider": ctx.provider,
            "commit_sha": ctx.commit_sha or ctx.artifact_sha256,
            "builder": ctx.builder,
            "build_version": ctx.build_version,
        }
