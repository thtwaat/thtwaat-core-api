#!/usr/bin/env python3
"""Scheduler — SSL renewal, backups, expiry monitoring on an interval."""
from __future__ import annotations

import json
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure /app is importable when launched as `python scripts/scheduler.py`.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [scheduler] %(message)s")
logger = logging.getLogger("scheduler")

_RUNNING = True


def _stop(*_args):
    global _RUNNING
    _RUNNING = False


def enqueue(r, job: dict) -> None:
    r.rpush("thtwaat:jobs", json.dumps(job))


def tick(r):
    from app.database.database import SessionLocal
    from app.ssl.manager import SslManager
    from app.domains.repository import DomainRepository
    from app.deploy.backup import run_full_backup
    from app.config.settings import settings

    db = SessionLocal()
    try:
        mgr = SslManager(db)
        expired = mgr.mark_expired()
        if expired:
            logger.info("marked_expired count=%s", expired)

        due = mgr.check_expiring(30)
        for d in due:
            enqueue(r, {
                "type": "ssl.renew",
                "domain_id": str(d.id),
                "company_id": str(d.company_id),
            })
            logger.info("enqueued ssl.renew hostname=%s", d.hostname)

        # Vercel-style domain automation: sweep every domain still moving
        # toward LIVE (free *.thtwaat.com subdomains and customer custom
        # domains alike) and let the worker advance it one step.
        progressing = DomainRepository(db).list_active_for_progress()
        for d in progressing:
            enqueue(r, {
                "type": "domain.auto_progress",
                "domain_id": str(d.id),
            })
        if progressing:
            logger.info("enqueued domain.auto_progress count=%s", len(progressing))

        # Daily backup marker
        hour = datetime.now(timezone.utc).hour
        backup_hour = int(getattr(settings, "BACKUP_HOUR_UTC", 3) or 3)
        flag_key = f"thtwaat:backup:ran:{datetime.now(timezone.utc).date().isoformat()}"
        if hour == backup_hour and not r.get(flag_key):
            try:
                result = run_full_backup()
                r.setex(flag_key, 86400, "1")
                logger.info("backup_complete %s", result)
            except Exception as exc:
                logger.error("backup_failed %s", exc)
                enqueue(r, {"type": "backup.full"})

        # Monitoring alert evaluation (idempotent fingerprints inside service)
        alert_key = f"thtwaat:alerts:eval:{datetime.now(timezone.utc).strftime('%Y%m%d%H')}"
        # At most once per hour unless interval is long; use tick-based throttle via Redis TTL
        alert_tick = "thtwaat:alerts:eval:tick"
        if not r.get(alert_tick):
            try:
                from app.monitoring.service import MonitoringOpsService

                raised = MonitoringOpsService(db).evaluate_and_raise()
                r.setex(alert_tick, 300, "1")
                if raised:
                    logger.info("alerts_raised count=%s", len(raised))
                    r.setex(alert_key, 3600, str(len(raised)))
            except Exception as exc:
                logger.error("alert_evaluate_failed %s", exc)

        # Daily enterprise retention application reuses the existing scheduler.
        retention_key = (
            f"thtwaat:enterprise:retention:"
            f"{datetime.now(timezone.utc).date().isoformat()}"
        )
        if not r.get(retention_key):
            from app.enterprise.service import EnterpriseService

            result = EnterpriseService(db).apply_all_retention_policies()
            r.setex(retention_key, 86400, "1")
            logger.info("enterprise_retention_complete %s", result)

        # Daily soft-deleted agent permanent purge (after retention window).
        agent_purge_key = (
            f"thtwaat:agents:purge:"
            f"{datetime.now(timezone.utc).date().isoformat()}"
        )
        if not r.get(agent_purge_key):
            enqueue(r, {"type": "agent.purge_expired"})
            r.setex(agent_purge_key, 86400, "1")
            logger.info("enqueued agent.purge_expired")

        # THTWAAT Deploy Phase 6A — sweep every still-active preview
        # deployment whose expires_at has passed and enqueue its teardown.
        # Mirrors the domain.auto_progress sweep above exactly. A preview
        # closed by its PR being closed is torn down immediately by the
        # webhook itself (see github_webhook_router.py) — this sweep is the
        # backstop for an abandoned/never-closed PR.
        from app.static_sites.repository import StaticSiteRepository as _StaticSiteRepository

        expired_previews = _StaticSiteRepository(db).list_expired_previews(now=datetime.now(timezone.utc))
        for p in expired_previews:
            enqueue(r, {"type": "static_site.preview_teardown", "preview_id": str(p.id), "reason": "expired"})
        if expired_previews:
            logger.info("enqueued static_site.preview_teardown count=%s", len(expired_previews))

        # THTWAAT Deploy — daily purge of expired upload-idempotency records
        # (housekeeping only; get_idempotent_deployment() already ignores
        # expired rows on its own — see app/static_sites/repository.py).
        idempotency_purge_key = (
            f"thtwaat:static_sites:idempotency_purge:"
            f"{datetime.now(timezone.utc).date().isoformat()}"
        )
        if not r.get(idempotency_purge_key):
            from app.static_sites.repository import StaticSiteRepository

            removed = StaticSiteRepository(db).purge_expired_idempotency_keys()
            r.setex(idempotency_purge_key, 86400, "1")
            if removed:
                logger.info("static_site_idempotency_purged count=%s", removed)
    finally:
        db.close()


def main():
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    # Register ORM relationships before any Session/query.
    from app.database.orm_bootstrap import register_orm_models

    register_orm_models()

    from app.config.settings import settings
    import redis

    interval = int(getattr(settings, "SCHEDULER_INTERVAL_SECONDS", 300) or 300)
    r = redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}", decode_responses=True)
    logger.info("scheduler started interval=%ss", interval)

    while _RUNNING:
        try:
            tick(r)
        except Exception as exc:
            logger.exception("scheduler_tick_failed: %s", exc)
        for _ in range(interval):
            if not _RUNNING:
                break
            time.sleep(1)

    logger.info("scheduler stopped")


if __name__ == "__main__":
    main()
