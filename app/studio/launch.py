"""Studio Phase 11 — production launch hardening (checklist, diagnostics, domain wizard).

Reuses Auth/Billing/AI Gateway/Domain Manager/SSL/deploy health — does not fork them.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.studio.review import SECRET_CATALOG


# Public launch-facing status labels (map from engine snake_case)
LAUNCH_STATUS_LIVE = "live"
LAUNCH_STATUS_BUILDING = "building"
LAUNCH_STATUS_WAITING_FOR_DNS = "waiting_for_dns"
LAUNCH_STATUS_PROVISIONING_SSL = "provisioning_ssl"
LAUNCH_STATUS_FAILED = "failed"

DIAG_HEALTHY = "healthy"
DIAG_WARNING = "warning"
DIAG_FAILED = "failed"

DOMAIN_WIZARD_PENDING_DNS = "pending_dns"
DOMAIN_WIZARD_DNS_VERIFIED = "dns_verified"
DOMAIN_WIZARD_SSL_ISSUING = "ssl_issuing"
DOMAIN_WIZARD_SSL_ACTIVE = "ssl_active"
DOMAIN_WIZARD_FAILED = "failed"


def compute_launch_status(
    *,
    live: bool,
    status: str,
    stage: str,
    ssl: Optional[Dict[str, Any]] = None,
) -> str:
    """Map deployment row fields to Phase 11 launch labels."""
    st = (status or "").lower()
    sg = (stage or "").lower()
    ssl = ssl or {}
    if live and st in {"completed", "live"}:
        return LAUNCH_STATUS_LIVE
    if st in {"failed"} or sg in {"failed"}:
        return LAUNCH_STATUS_FAILED
    if st in {"waiting_for_domain"} or sg in {"waiting_for_domain"}:
        return LAUNCH_STATUS_WAITING_FOR_DNS
    if st in {"provisioning_ssl"} or sg in {"provisioning_ssl", "ssl"}:
        ssl_val = str(ssl.get("ssl_status") or ssl.get("status") or "").upper()
        if ssl_val in {"ACTIVE", "ISSUED"} and live:
            return LAUNCH_STATUS_LIVE
        if not live:
            return LAUNCH_STATUS_PROVISIONING_SSL
    if st in {"queued", "deploying"} or sg in {
        "queued",
        "preparing",
        "validating",
        "building",
        "packaging",
        "uploading",
        "deploying",
        "database_migration",
        "health_check",
    }:
        return LAUNCH_STATUS_BUILDING
    if live:
        return LAUNCH_STATUS_LIVE
    return LAUNCH_STATUS_BUILDING


def launch_status_label(code: str) -> str:
    return {
        LAUNCH_STATUS_LIVE: "LIVE",
        LAUNCH_STATUS_BUILDING: "Building",
        LAUNCH_STATUS_WAITING_FOR_DNS: "Waiting for DNS",
        LAUNCH_STATUS_PROVISIONING_SSL: "Provisioning SSL",
        LAUNCH_STATUS_FAILED: "Failed",
    }.get(code, code)


def _env_present(keys: tuple[str, ...]) -> bool:
    import os

    from app.config import settings as settings_mod

    s = settings_mod.settings
    for key in keys:
        val = getattr(s, key, None)
        if val is None:
            val = os.environ.get(key)
        if val is not None and str(val).strip():
            return True
    return False


def _item(
    key: str,
    title: str,
    *,
    ok: bool,
    required: bool = True,
    detail: str = "",
    href: str = "",
) -> Dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "ok": ok,
        "required": required,
        "detail": detail,
        "href": href,
    }


def build_launch_checklist(
    db: Session,
    *,
    workspace_id: UUID,
    project_id: UUID,
    deployment: Optional[Any] = None,
) -> Dict[str, Any]:
    """Pre-launch checklist reusing platform config + last deployment health."""
    from app.config.settings import settings
    from app.studio.deploy import run_platform_health
    from app.studio.domain_validation import free_subdomain_zone

    health = run_platform_health(
        db,
        api_base=getattr(settings, "PUBLIC_API_BASE_URL", "") or "",
        app_base=getattr(settings, "PUBLIC_APP_BASE_URL", "") or "",
    )

    ai_ok = any(
        _env_present(keys)
        for group, _label, keys in SECRET_CATALOG
        if group in {"openai", "gemini", "anthropic", "openrouter"}
    ) or bool((health.get("ai_gateway") or {}).get("ok"))

    billing_ok = any(
        _env_present(keys)
        for group, _label, keys in SECRET_CATALOG
        if group in {"stripe", "razorpay"}
    ) or bool(getattr(settings, "BILLING_ENABLE_STRIPE", False) and _env_present(("STRIPE_SECRET_KEY",)))

    email_ok = _env_present(("SMTP_HOST", "SMTP_FROM")) or _env_present(("RESEND_API_KEY",))
    storage_ok = bool((health.get("storage") or {}).get("ok"))

    domain_ok = False
    https_ok = False
    domain_detail = "No domain yet — deploy with free subdomain or custom domain"
    if deployment is not None:
        host = getattr(deployment, "domain", None) or getattr(deployment, "subdomain", None)
        live = bool(getattr(deployment, "live", False))
        ssl = getattr(deployment, "ssl", None) or {}
        validation = None
        if isinstance(getattr(deployment, "health", None), dict):
            validation = (deployment.health or {}).get("domain")
        reachable = bool((validation or {}).get("reachable")) if isinstance(validation, dict) else live
        domain_ok = bool(host) and (reachable or live)
        zone = free_subdomain_zone()
        ssl_val = str(ssl.get("ssl_status") or ssl.get("status") or "").upper()
        https_ok = bool(ssl.get("ssl_enabled")) or ssl_val in {"ACTIVE", "ISSUED", "PLATFORM_WILDCARD"}
        if host and str(host).endswith(f".{zone}") and domain_ok:
            # Free zone is served behind platform TLS once DNS is live.
            https_ok = https_ok or True
        domain_detail = f"{host or '—'} · {'reachable' if domain_ok else 'pending DNS'}"

    health_ok = bool((health.get("api") or {}).get("ok")) and bool(
        (health.get("database") or {}).get("ok")
    )
    workers_ok = bool((health.get("workers") or {}).get("ok"))

    items = [
        _item(
            "ai_provider",
            "AI provider configured",
            ok=ai_ok,
            detail="OPENAI/GEMINI/ANTHROPIC/OPENROUTER or AI gateway healthy",
            href="/app/ai",
        ),
        _item(
            "billing",
            "Billing configured",
            ok=billing_ok,
            detail="Stripe or Razorpay credentials present",
            href="/app/billing",
        ),
        _item(
            "email",
            "Email configured",
            ok=email_ok,
            detail="SMTP_HOST/SMTP_FROM or RESEND_API_KEY",
            href="/app/settings",
        ),
        _item(
            "storage",
            "Storage configured",
            ok=storage_ok,
            detail="Local/S3 storage writable",
        ),
        _item(
            "domain",
            "Domain or free subdomain",
            ok=domain_ok,
            detail=domain_detail,
            href="/app/domains",
        ),
        _item(
            "https",
            "HTTPS",
            ok=https_ok,
            detail="SSL active / platform wildcard for *.thtwaat.app",
        ),
        _item(
            "health",
            "Health",
            ok=health_ok,
            detail="API /health and database OK",
        ),
        _item(
            "workers",
            "Background workers",
            ok=workers_ok,
            detail="Worker heartbeat on Redis",
        ),
    ]
    required = [i for i in items if i["required"]]
    ready = all(i["ok"] for i in required)
    return {
        "project_id": str(project_id),
        "workspace_id": str(workspace_id),
        "ready": ready,
        "passed": sum(1 for i in items if i["ok"]),
        "total": len(items),
        "items": items,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def _diag_status(probe: Optional[Dict[str, Any]], *, soft: bool = False) -> str:
    if not isinstance(probe, dict):
        return DIAG_WARNING if soft else DIAG_FAILED
    ok = probe.get("ok")
    if ok is True:
        return DIAG_HEALTHY
    if ok is None:
        return DIAG_WARNING
    return DIAG_WARNING if soft and probe.get("note") else DIAG_FAILED


def check_smtp_config() -> Dict[str, Any]:
    from app.notifications.config import notifications_settings

    host = (notifications_settings.SMTP_HOST or "").strip()
    from_addr = (notifications_settings.SMTP_FROM or "").strip()
    if host and from_addr:
        return {"ok": True, "host": host, "from": from_addr}
    if (notifications_settings.RESEND_API_KEY or "").strip():
        return {"ok": True, "provider": "resend"}
    return {"ok": False, "error": "SMTP_HOST/SMTP_FROM or RESEND_API_KEY not configured"}


def build_launch_diagnostics(
    db: Session,
    *,
    workspace_id: UUID,
    project_id: UUID,
    deployment: Optional[Any] = None,
) -> Dict[str, Any]:
    """Production health surface for Studio launch diagnostics page."""
    from app.config.settings import settings
    from app.studio.deploy import run_platform_health

    health = run_platform_health(
        db,
        api_base=getattr(settings, "PUBLIC_API_BASE_URL", "") or "",
        app_base=getattr(settings, "PUBLIC_APP_BASE_URL", "") or "",
    )
    smtp = check_smtp_config()

    deploy_probe: Dict[str, Any]
    if deployment is None:
        deploy_probe = {"ok": None, "note": "No deployment yet"}
    elif bool(getattr(deployment, "live", False)):
        deploy_probe = {
            "ok": True,
            "status": getattr(deployment, "status", None),
            "stage": getattr(deployment, "stage", None),
            "live": True,
        }
    elif str(getattr(deployment, "status", "")).lower() == "failed":
        deploy_probe = {
            "ok": False,
            "status": getattr(deployment, "status", None),
            "error": getattr(deployment, "error", None),
        }
    else:
        deploy_probe = {
            "ok": None,
            "status": getattr(deployment, "status", None),
            "stage": getattr(deployment, "stage", None),
            "live": False,
            "note": "Deployment in progress or waiting",
        }

    components = [
        {
            "key": "api",
            "title": "API",
            "status": _diag_status(health.get("api")),
            "detail": health.get("api") or {},
        },
        {
            "key": "workers",
            "title": "Workers",
            "status": _diag_status(health.get("workers"), soft=True),
            "detail": health.get("workers") or {},
        },
        {
            "key": "redis",
            "title": "Redis",
            "status": _diag_status(health.get("redis")),
            "detail": health.get("redis") or {},
        },
        {
            "key": "database",
            "title": "Database",
            "status": _diag_status(health.get("database")),
            "detail": health.get("database") or {},
        },
        {
            "key": "storage",
            "title": "Storage",
            "status": _diag_status(health.get("storage")),
            "detail": health.get("storage") or {},
        },
        {
            "key": "smtp",
            "title": "SMTP",
            "status": _diag_status(smtp, soft=True),
            "detail": smtp,
        },
        {
            "key": "ai_providers",
            "title": "AI Providers",
            "status": _diag_status(health.get("ai_gateway"), soft=True),
            "detail": health.get("ai_gateway") or {},
        },
        {
            "key": "deployment",
            "title": "Deployment",
            "status": _diag_status(deploy_probe, soft=True),
            "detail": deploy_probe,
        },
    ]
    failed = sum(1 for c in components if c["status"] == DIAG_FAILED)
    warnings = sum(1 for c in components if c["status"] == DIAG_WARNING)
    overall = DIAG_HEALTHY
    if failed:
        overall = DIAG_FAILED
    elif warnings:
        overall = DIAG_WARNING
    return {
        "project_id": str(project_id),
        "workspace_id": str(workspace_id),
        "overall": overall,
        "failed": failed,
        "warnings": warnings,
        "components": components,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def domain_wizard_phase(
    *,
    dns_reachable: bool,
    dns_verified: bool,
    ssl_status: str,
    domain_status: str = "",
) -> str:
    ssl_u = (ssl_status or "").upper()
    dom = (domain_status or "").lower()
    if ssl_u in {"ACTIVE", "ISSUED"} or dom == "live":
        return DOMAIN_WIZARD_SSL_ACTIVE
    if ssl_u in {"PENDING", "REQUESTING"} or dom in {"ssl_pending"}:
        return DOMAIN_WIZARD_SSL_ISSUING
    if dns_verified or dns_reachable or dom in {"verified"}:
        return DOMAIN_WIZARD_DNS_VERIFIED
    if dom in {"failed"}:
        return DOMAIN_WIZARD_FAILED
    return DOMAIN_WIZARD_PENDING_DNS


def build_domain_wizard(
    db: Session,
    *,
    workspace_id: UUID,
    hostname: str,
    actor_id: UUID,
    auto_verify: bool = True,
) -> Dict[str, Any]:
    """Domain wizard payload — reuses Domain Manager verify + SSL status."""
    from app.domains.schemas import DomainCreate
    from app.domains.service import DomainService
    from app.studio.domain_validation import validate_hostname

    hostname = (hostname or "").strip().lower().rstrip(".")
    if not hostname:
        return {
            "hostname": "",
            "phase": DOMAIN_WIZARD_FAILED,
            "phase_label": "Failed",
            "error": "hostname required",
            "dns_records": [],
            "poll_interval_seconds": 30,
        }

    validation = validate_hostname(hostname)
    svc = DomainService(db)
    existing = svc.repo.get_by_hostname(hostname)
    if not existing:
        created = svc.create(
            workspace_id,
            DomainCreate(hostname=hostname, verification_method="TXT"),
            actor_id,
        )
        domain_id = created.id
        dns_records = list(created.dns_records or [])
        domain_status = str(created.status or "")
        ssl_status = str(created.ssl_status or "")
    else:
        domain_id = existing.id
        resp = svc._to_response(existing)
        dns_records = [
            r.model_dump() if hasattr(r, "model_dump") else r for r in (resp.dns_records or [])
        ]
        domain_status = str(resp.status or "")
        ssl_status = str(resp.ssl_status or "")

    verify_result = None
    if auto_verify:
        try:
            verify_result = svc.verify(domain_id, workspace_id, actor_id)
            domain_status = str(getattr(verify_result, "status", None) or domain_status)
            # Refresh SSL after verify
            row = svc.repo.get_by_id(domain_id)
            if row:
                ssl_status = str(row.ssl_status or ssl_status)
                domain_status = str(getattr(row.status, "value", row.status) or domain_status)
        except Exception as exc:  # noqa: BLE001
            verify_result = {"error": str(exc)}

    dns_verified = str(domain_status).lower() in {
        "verified",
        "ssl_pending",
        "live",
        "active",
    }
    phase = domain_wizard_phase(
        dns_reachable=bool(validation.reachable),
        dns_verified=dns_verified,
        ssl_status=ssl_status,
        domain_status=domain_status,
    )
    # Optionally kick SSL when DNS verified
    ssl_request = None
    if phase == DOMAIN_WIZARD_DNS_VERIFIED:
        try:
            issued = svc.request_ssl(domain_id, workspace_id, actor_id)
            ssl_request = {
                "ssl_status": getattr(issued, "ssl_status", None),
                "message": getattr(issued, "message", None),
            }
            ssl_status = str(ssl_request.get("ssl_status") or ssl_status)
            phase = domain_wizard_phase(
                dns_reachable=True,
                dns_verified=True,
                ssl_status=ssl_status,
                domain_status=domain_status,
            )
        except Exception as exc:  # noqa: BLE001
            ssl_request = {"error": str(exc)}

    labels = {
        DOMAIN_WIZARD_PENDING_DNS: "Pending DNS",
        DOMAIN_WIZARD_DNS_VERIFIED: "DNS Verified",
        DOMAIN_WIZARD_SSL_ISSUING: "SSL Issuing",
        DOMAIN_WIZARD_SSL_ACTIVE: "SSL Active",
        DOMAIN_WIZARD_FAILED: "Failed",
    }
    return {
        "hostname": hostname,
        "domain_id": str(domain_id),
        "phase": phase,
        "phase_label": labels.get(phase, phase),
        "dns_reachable": bool(validation.reachable),
        "dns_verified": dns_verified,
        "domain_status": domain_status,
        "ssl_status": ssl_status,
        "dns_records": dns_records,
        "validation": validation.to_dict(),
        "verify": verify_result.model_dump()
        if hasattr(verify_result, "model_dump")
        else verify_result,
        "ssl_request": ssl_request,
        "poll_interval_seconds": 30,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def verify_deployment_gates(
    *,
    stack_ok: bool,
    health: Dict[str, Any],
    dns_ok: bool,
    ssl_ok: bool,
    build_ok: bool = True,
) -> Dict[str, Any]:
    """Strict LIVE gate evaluation used by deploy + unit tests."""
    critical_keys = ("api", "database", "storage", "redis", "workers")
    failed = [
        k
        for k in critical_keys
        if isinstance(health.get(k), dict) and health[k].get("ok") is False
    ]
    # API must be strict HTTP 200 when present
    api = health.get("api") or {}
    if isinstance(api, dict) and api.get("status_code") is not None:
        if int(api.get("status_code") or 0) != 200:
            if "api" not in failed:
                failed.append("api")

    live = bool(build_ok and stack_ok and not failed and dns_ok and ssl_ok)
    if not build_ok or not stack_ok or failed:
        status = LAUNCH_STATUS_FAILED if (not build_ok or not stack_ok or failed) else LAUNCH_STATUS_BUILDING
        if failed and build_ok and stack_ok:
            status = LAUNCH_STATUS_FAILED
    elif not dns_ok:
        status = LAUNCH_STATUS_WAITING_FOR_DNS
    elif not ssl_ok:
        status = LAUNCH_STATUS_PROVISIONING_SSL
    else:
        status = LAUNCH_STATUS_LIVE

    return {
        "live": live,
        "launch_status": status if live else status,
        "failed_checks": failed,
        "dns_ok": dns_ok,
        "ssl_ok": ssl_ok,
        "stack_ok": stack_ok,
        "build_ok": build_ok,
    }
