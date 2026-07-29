#!/usr/bin/env python3
"""Scheduler — SSL renewal, backups, expiry monitoring on an interval."""
from __future__ import annotations

import json
import logging
import signal
import time
from datetime import datetime, timezone

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
    finally:
        db.close()


def main():
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

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
