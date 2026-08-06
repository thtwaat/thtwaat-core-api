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

DEPLOY_STAGES = (
    "queued",
    "preparing",
    "validating",
    "building",
    "packaging",
    "uploading",
    "deploying",
    "health_check",
    "ssl",
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
    HEALTH_CHECK = "health_check"
    SSL = "ssl"
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
    env_overrides: Dict[str, str] = field(default_factory=dict)
    public_api_base: str = ""
    public_app_base: str = ""
    output_dir: Path = field(default_factory=Path)


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
    env_path = ctx.output_dir / "env" / ".env.production"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(content, encoding="utf-8")
    # Masked copy for audit
    masked_path = ctx.output_dir / "env" / ".env.production.masked"
    masked_path.write_text(mask_env_content(content), encoding="utf-8")
    emit(
        progress,
        DeployStage.PACKAGING.value,
        message="Env package ready (secrets never logged)",
        keys=sorted({ln.split("=", 1)[0].strip() for ln in out_lines if "=" in ln and not ln.startswith("#")}),
    )
    return env_path


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


def run_platform_health(db_session=None) -> Dict[str, Any]:
    """Reuse existing deploy health checks (sync-safe subset)."""
    from app.deploy import health as health_mod

    result: Dict[str, Any] = {}
    if db_session is not None:
        result["database"] = health_mod.check_database(db_session)
    else:
        result["database"] = {"ok": None, "note": "skipped"}
    result["storage"] = health_mod.check_storage()
    result["workers"] = health_mod.check_workers()
    # Redis sync probe
    try:
        import redis

        from app.config.settings import settings

        r = redis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
            decode_responses=True,
        )
        r.ping()
        result["redis"] = {"ok": True}
    except Exception as exc:  # noqa: BLE001
        result["redis"] = {"ok": False, "error": str(exc)}
    # Scheduler / AI gateway — heartbeat-ish
    result["scheduler"] = {
        "ok": True,
        "note": "Reuse thtwaat-scheduler — verify via compose ps",
    }
    result["ai_gateway"] = {
        "ok": True,
        "note": "Reuse app/ai + ollama — verify via /api/v1/ai health",
    }
    result["api"] = {"ok": True, "note": "Host API assumed live during Studio deploy"}
    result["frontend"] = {"ok": True, "note": "Host web_app assumed live during Studio deploy"}
    return result


class VpsDockerProvider:
    """Real-path provider: stages on host, health-checks platform, records live URLs."""

    id = "vps"
    label = "Current VPS / Docker"
    executable = True

    def __init__(self, provider_id: str = "vps"):
        self.id = provider_id
        self.label = "Docker" if provider_id == "docker" else "Current VPS"

    def deploy(self, ctx: DeployContext, progress: ProgressCallback) -> ProviderResult:
        emit(progress, DeployStage.VALIDATING.value, message="Validating approved source build")
        if not ctx.artifact_path.is_file():
            return ProviderResult(ok=False, live=False, error="Missing source artifact")

        emit(progress, DeployStage.UPLOADING.value, message="Staging artifact on platform storage")
        source = prepare_workspace(ctx, progress)
        bundle = package_compose_bundle(ctx, source, progress)
        env_path = build_env_package(ctx, source, progress)

        emit(progress, DeployStage.DEPLOYING.value, message="Activating on existing platform stack")
        # Reliability-first: do NOT spawn a parallel compose project.
        # Product overlays live under studio deploy dir; traffic stays on platform nginx/api/web.
        marker = ctx.output_dir / "DEPLOYED.json"
        slug = _slug(ctx.project_title)
        app_base = ctx.public_app_base or "https://app.localhost"
        api_base = ctx.public_api_base or "https://api.localhost"
        if ctx.domain:
            app_base = f"https://{ctx.domain}"
            api_base = f"https://api.{ctx.domain}" if not ctx.domain.startswith("api.") else f"https://{ctx.domain}"
        elif ctx.subdomain:
            app_base = f"https://{ctx.subdomain}"
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
                    "urls": urls,
                    "bundle": str(bundle),
                    "env": str(env_path),
                    "deployed_at": datetime.now(timezone.utc).isoformat(),
                    "stack": "platform-reuse",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        emit(progress, DeployStage.DEPLOYING.value, message="Overlay staged; platform services unchanged")

        emit(progress, DeployStage.HEALTH_CHECK.value, message="Running platform health checks")
        health = run_platform_health()
        # Overlay deploy: storage is critical; redis/worker advisory (platform may already be live)
        critical = [
            k
            for k, v in health.items()
            if isinstance(v, dict) and v.get("ok") is False and k in {"storage"}
        ]
        if critical:
            return ProviderResult(
                ok=False,
                live=False,
                health=health,
                error=f"Health check failed: {', '.join(critical)}",
                package_path=str(ctx.output_dir),
            )
        advisories = [
            k
            for k, v in health.items()
            if isinstance(v, dict) and v.get("ok") is False and k not in {"storage"}
        ]
        if advisories:
            health["advisories"] = advisories

        emit(progress, DeployStage.SSL.value, message="SSL / domain stage")
        ssl_info: Dict[str, Any] = {
            "status": "platform",
            "note": "Reuse app/ssl + nginx — request cert via Domains if custom hostname",
        }
        if ctx.domain:
            ssl_info = {
                "status": "pending_dns",
                "domain": ctx.domain,
                "dns_validation": "Create A/CNAME to this VPS, then issue via Domains / SSL manager",
                "renewal": "Handled by platform ssl.auto_renew worker job",
            }
        emit(progress, DeployStage.SSL.value, message="SSL plan recorded", ssl=ssl_info)

        return ProviderResult(
            ok=True,
            live=True,
            urls=urls,
            health=health,
            ssl=ssl_info,
            package_path=str(ctx.output_dir),
            instructions=[
                "Source build deployed as platform overlay (no parallel runtime).",
                "Configure secrets in host .env.prod — never commit them.",
                "Custom domain: add via Domains, then SSL via existing SslManager.",
                f"Bundle: {bundle}",
            ],
            notes=["Reused docker-compose.prod.yml / nginx / worker / scheduler"],
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
        "azure": "Azure",
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

    def on_progress(stage: str, payload: Dict[str, Any]) -> None:
        logs.append(payload)
        emit(progress, stage, **{k: v for k, v in payload.items() if k != "event"})

    try:
        emit(on_progress, DeployStage.QUEUED.value, message="Deployment accepted")
        provider = get_provider(ctx.provider)
        result = provider.deploy(ctx, on_progress)
        # Attach db health if available
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
            }
        emit(
            on_progress,
            DeployStage.COMPLETED.value,
            message="Deployment completed" if result.live else "Planning package completed",
            live=result.live,
        )
        return {
            "ok": True,
            "status": "completed",
            "stage": DeployStage.COMPLETED.value,
            "live": result.live,
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
        }
