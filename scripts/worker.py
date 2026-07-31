#!/usr/bin/env python3
"""Background worker — processes Redis job queue (ssl, nginx, backup tasks)."""
from __future__ import annotations

import json
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure /app is importable when launched as `python scripts/worker.py`.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [worker] %(message)s")
logger = logging.getLogger("worker")

_RUNNING = True


def _stop(*_args):
    global _RUNNING
    _RUNNING = False


def heartbeat(r):
    r.setex("thtwaat:worker:heartbeat", 60, datetime.now(timezone.utc).isoformat())


def process_job(payload: dict) -> None:
    from app.database.database import SessionLocal

    job_type = payload.get("type")
    db = SessionLocal()
    try:
        if job_type == "ssl.renew":
            from uuid import UUID
            from app.ssl.manager import SslManager

            SslManager(db).renew(
                UUID(payload["domain_id"]),
                UUID(payload["company_id"]),
                UUID(payload.get("user_id") or payload["company_id"]),
            )
        elif job_type == "ssl.auto_renew":
            from app.ssl.manager import SslManager

            SslManager(db).auto_renew_due()
        elif job_type == "backup.full":
            from app.deploy.backup import run_full_backup

            run_full_backup()
        elif job_type == "nginx.reload":
            from app.ssl.nginx_gen import reload_nginx

            reload_nginx()
        else:
            logger.warning("unknown job type=%s", job_type)
    finally:
        db.close()


def main():
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    from app.config.settings import settings
    import redis

    r = redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}", decode_responses=True)
    logger.info("worker started redis=%s:%s", settings.REDIS_HOST, settings.REDIS_PORT)

    while _RUNNING:
        heartbeat(r)
        item = r.blpop("thtwaat:jobs", timeout=5)
        if not item:
            continue
        _, raw = item
        try:
            payload = json.loads(raw)
            logger.info("job_start type=%s", payload.get("type"))
            process_job(payload)
            logger.info("job_done type=%s", payload.get("type"))
        except Exception as exc:
            logger.exception("job_failed: %s", exc)
            # requeue with delay marker
            r.rpush("thtwaat:jobs:dead", raw)
        time.sleep(0.05)

    logger.info("worker stopped")


if __name__ == "__main__":
    main()
