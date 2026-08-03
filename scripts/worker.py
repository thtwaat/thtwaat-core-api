#!/usr/bin/env python3
"""Background worker — processes Redis job queue (ssl, nginx, backup, webhooks)."""
from __future__ import annotations

import json
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

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


def _handle_webhook_failure(payload: Dict[str, Any], exc: Exception) -> None:
    """Retry with exponential backoff or dead-letter (Week 3 Day 2 + W4 outbox ACK)."""
    from app.config.settings import settings
    from app.database.database import SessionLocal
    from app.monitoring.queue import dead_letter, enqueue_delayed
    from app.webhooks.delivery import WebhookDeliveryError, backoff_seconds
    from app.webhooks.outbox import ack_from_job_payload

    attempt = int(payload.get("attempt") or 1)
    max_attempts = int(getattr(settings, "WEBHOOK_MAX_ATTEMPTS", 5) or 5)
    base = float(getattr(settings, "WEBHOOK_BACKOFF_BASE_SECONDS", 2.0) or 2.0)
    cap = float(getattr(settings, "WEBHOOK_BACKOFF_CAP_SECONDS", 300.0) or 300.0)

    retryable = True
    if isinstance(exc, WebhookDeliveryError):
        retryable = bool(exc.retryable)

    reason = str(exc)
    db = SessionLocal()
    try:
        if (not retryable) or attempt >= max_attempts:
            dead_letter(payload, reason=f"attempt={attempt}/{max_attempts}: {reason}")
            ack_from_job_payload(db, payload, outcome="dead", reason=reason)
            logger.error(
                "webhook_dead event=%s delivery_id=%s attempt=%s reason=%s",
                payload.get("event"),
                payload.get("delivery_id"),
                attempt,
                reason,
            )
            return

        next_attempt = attempt + 1
        delay = backoff_seconds(attempt, base=base, cap=cap)
        ready_at = time.time() + delay
        retry_payload = dict(payload)
        retry_payload["attempt"] = next_attempt
        retry_payload["last_error"] = reason
        enqueue_delayed(retry_payload, ready_at=ready_at)
        next_at = datetime.fromtimestamp(ready_at, tz=timezone.utc)
        ack_from_job_payload(
            db,
            payload,
            outcome="failed",
            reason=reason,
            next_attempt_at=next_at,
        )
        logger.warning(
            "webhook_retry event=%s delivery_id=%s attempt=%s next=%s delay=%.1fs reason=%s",
            payload.get("event"),
            payload.get("delivery_id"),
            attempt,
            next_attempt,
            delay,
            reason,
        )
    finally:
        db.close()


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
        elif job_type == "webhook.dispatch":
            from app.webhooks.delivery import deliver_webhook, new_delivery_id
            from app.webhooks.outbox import ack_from_job_payload

            url = payload.get("url")
            secret = payload.get("secret") or ""
            event = payload.get("event") or "unknown"
            data = payload.get("data") or {}
            if not url:
                raise ValueError("webhook.dispatch missing url")
            body = {
                "event": event,
                "data": data,
                "company_id": payload.get("company_id"),
                "delivery_id": payload.get("delivery_id") or new_delivery_id(),
                "attempt": int(payload.get("attempt") or 1),
            }
            # Keep delivery_id on the job for failure ACK if missing
            if not payload.get("delivery_id"):
                payload["delivery_id"] = body["delivery_id"]

            ack_from_job_payload(db, payload, outcome="attempt")
            status_code, _ = deliver_webhook(url, body, secret)
            ack_from_job_payload(db, payload, outcome="delivered")
            logger.info(
                "webhook_delivered event=%s delivery_id=%s status=%s attempt=%s",
                event,
                body.get("delivery_id"),
                status_code,
                payload.get("attempt") or 1,
            )
        else:
            logger.warning("unknown job type=%s", job_type)
    finally:
        db.close()


def main():
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    # Register ORM relationships before any Session/query (same need as scheduler).
    from app.database.orm_bootstrap import register_orm_models

    register_orm_models()

    from app.config.settings import settings
    from app.database.database import SessionLocal
    from app.monitoring.queue import promote_due_jobs
    from app.webhooks.outbox import redrive_stuck_deliveries
    import redis

    r = redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}", decode_responses=True)
    logger.info("worker started redis=%s:%s", settings.REDIS_HOST, settings.REDIS_PORT)

    while _RUNNING:
        heartbeat(r)
        try:
            promoted = promote_due_jobs(limit=50)
            if promoted:
                logger.info("promoted_delayed count=%s", promoted)
        except Exception as exc:  # noqa: BLE001
            logger.warning("promote_due_jobs error: %s", exc)

        try:
            db = SessionLocal()
            try:
                redriven = redrive_stuck_deliveries(db)
                if redriven:
                    logger.info("outbox_redrive count=%s", redriven)
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("outbox_redrive error: %s", exc)

        item = r.blpop("thtwaat:jobs", timeout=5)
        if not item:
            continue
        _, raw = item
        try:
            payload = json.loads(raw)
        except Exception as exc:
            logger.exception("job_parse_failed: %s", exc)
            r.rpush("thtwaat:jobs:dead", raw)
            continue

        job_type = payload.get("type")
        try:
            logger.info("job_start type=%s attempt=%s", job_type, payload.get("attempt") or 1)
            process_job(payload)
            logger.info("job_done type=%s", job_type)
        except Exception as exc:
            logger.exception("job_failed type=%s: %s", job_type, exc)
            if job_type == "webhook.dispatch":
                try:
                    _handle_webhook_failure(payload, exc)
                except Exception as inner:  # noqa: BLE001
                    logger.exception("webhook_retry_handler_failed: %s", inner)
                    r.rpush("thtwaat:jobs:dead", raw)
            else:
                r.rpush("thtwaat:jobs:dead", raw)
        time.sleep(0.05)

    logger.info("worker stopped")


if __name__ == "__main__":
    main()
