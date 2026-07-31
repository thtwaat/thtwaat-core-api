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
    finally:
        db.close()


def main():
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    # Register ORM relationships before any Session/query (same set as main.py).
    import app.companies.model  # noqa: F401
    import app.users.model  # noqa: F401
    import app.auth.model  # noqa: F401
    import app.apps.model  # noqa: F401
    import app.storage.model  # noqa: F401
    import app.notifications.model  # noqa: F401
    import app.payments.model  # noqa: F401
    import app.ai.model  # noqa: F401
    import app.products.model  # noqa: F401
    import app.api_keys.model  # noqa: F401
    import app.webhooks.model  # noqa: F401
    import app.features.ai_platform.database.models  # noqa: F401
    import app.agent_platform.models  # noqa: F401
    import app.agent_platform.knowledge.models  # noqa: F401
    import app.usage.models  # noqa: F401
    import app.domains.models  # noqa: F401
    import app.marketplace.models  # noqa: F401
    import app.product_generator.models  # noqa: F401
    import app.branding.models  # noqa: F401
    import app.enterprise.models  # noqa: F401
    import app.onboarding.models  # noqa: F401
    import app.monitoring.models  # noqa: F401
    import app.copilot.models  # noqa: F401
    import app.agent_store.models  # noqa: F401
    import app.payments.plans.model  # noqa: F401
    import app.payments.invoices.model  # noqa: F401
    import app.payments.subscriptions.model  # noqa: F401

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
