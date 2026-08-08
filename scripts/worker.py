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
    """Refresh worker liveness key (60s TTL). Raises on Redis errors."""
    r.setex("thtwaat:worker:heartbeat", 60, datetime.now(timezone.utc).isoformat())


def _connect_redis():
    from app.config.settings import settings
    import redis

    url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}"
    client = redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=10,
    )
    client.ping()
    return client, settings.REDIS_HOST, settings.REDIS_PORT


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


def _handle_domain_job_failure(payload: Dict[str, Any], exc: Exception) -> None:
    """Retry domain.auto_progress with backoff, then dead-letter.

    Only for unexpected errors (certbot/DNS-resolver/DB exceptions) — a
    domain simply not being ready yet (DNS not propagated, SSL still
    pending) is not an exception here; it's picked up again by the next
    scheduler sweep instead of being retried through this path.
    """
    from app.monitoring.queue import dead_letter, enqueue_delayed

    attempt = int(payload.get("attempt") or 1)
    max_attempts = int(payload.get("max_attempts") or 6)
    reason = str(exc)
    if attempt >= max_attempts:
        dead_letter(
            payload,
            reason=f"domain_auto_progress attempt={attempt}/{max_attempts}: {reason}",
        )
        logger.error(
            "domain_auto_progress_dead domain_id=%s attempt=%s reason=%s",
            payload.get("domain_id"),
            attempt,
            reason,
        )
        return

    delay = min(2.0 ** attempt, 300.0)
    ready_at = time.time() + delay
    retry_payload = dict(payload)
    retry_payload["attempt"] = attempt + 1
    retry_payload["last_error"] = reason
    enqueue_delayed(retry_payload, ready_at=ready_at)
    logger.warning(
        "domain_auto_progress_retry domain_id=%s attempt=%s next=%s delay=%.1fs reason=%s",
        payload.get("domain_id"),
        attempt,
        attempt + 1,
        delay,
        reason,
    )


def _handle_studio_job_failure(payload: Dict[str, Any], exc: Exception) -> None:
    """Retry studio.deploy / studio.build with backoff, then dead-letter."""
    from app.monitoring.queue import dead_letter, enqueue_delayed

    attempt = int(payload.get("attempt") or 1)
    max_attempts = int(payload.get("max_attempts") or 4)
    timeout_seconds = int(payload.get("timeout_seconds") or 900)
    reason = str(exc)
    if "timeout" in reason.lower() or attempt >= max_attempts:
        dead_letter(
            payload,
            reason=f"studio_job attempt={attempt}/{max_attempts} timeout={timeout_seconds}s: {reason}",
        )
        logger.error(
            "studio_job_dead type=%s id=%s attempt=%s reason=%s",
            payload.get("type"),
            payload.get("deployment_id") or payload.get("build_id"),
            attempt,
            reason,
        )
        return

    delay = min(2.0 ** attempt, 120.0)
    ready_at = time.time() + delay
    retry_payload = dict(payload)
    retry_payload["attempt"] = attempt + 1
    retry_payload["last_error"] = reason
    enqueue_delayed(retry_payload, ready_at=ready_at)
    logger.warning(
        "studio_job_retry type=%s attempt=%s next=%s delay=%.1fs reason=%s",
        payload.get("type"),
        attempt,
        attempt + 1,
        delay,
        reason,
    )


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
        elif job_type == "domain.auto_progress":
            from uuid import UUID
            from app.domains.service import DomainService

            domain_id = payload.get("domain_id")
            if not domain_id:
                raise ValueError("domain.auto_progress missing domain_id")
            DomainService(db).progress(UUID(str(domain_id)))
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
        elif job_type == "studio.build":
            from uuid import UUID

            from app.studio.service import StudioService

            build_id = payload.get("build_id")
            if not build_id:
                raise ValueError("studio.build missing build_id")
            StudioService(db).run_build(UUID(str(build_id)))
        elif job_type == "studio.deploy":
            from uuid import UUID

            from app.studio.service import StudioService

            deployment_id = payload.get("deployment_id")
            if not deployment_id:
                raise ValueError("studio.deploy missing deployment_id")
            timeout_seconds = int(payload.get("timeout_seconds") or 900)
            started = time.time()
            StudioService(db).run_deploy(UUID(str(deployment_id)))
            if time.time() - started > timeout_seconds:
                raise TimeoutError(f"studio.deploy exceeded {timeout_seconds}s")
        elif job_type == "agent.cleanup":
            from uuid import UUID

            from app.agent_platform.lifecycle import AgentLifecycleService

            agent_id = payload.get("agent_id")
            if not agent_id:
                raise ValueError("agent.cleanup missing agent_id")
            AgentLifecycleService(db).run_cleanup(UUID(str(agent_id)))
        elif job_type == "agent.purge_expired":
            from app.agent_platform.lifecycle import AgentLifecycleService, RETENTION_DAYS

            days = int(payload.get("retention_days") or RETENTION_DAYS)
            AgentLifecycleService(db).purge_expired(retention_days=days)
        else:
            logger.warning("unknown job type=%s", job_type)
    finally:
        db.close()


def main():
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    # Heartbeat ASAP — before ORM/DB imports (those can block for a long time).
    try:
        r, host, port = _connect_redis()
    except Exception as exc:
        logger.exception("redis_connect_failed: %s", exc)
        raise SystemExit(1) from exc

    logger.info("worker started redis=%s:%s", host, port)
    try:
        heartbeat(r)
        logger.info("worker heartbeat ok key=thtwaat:worker:heartbeat")
    except Exception as exc:
        logger.exception("worker_heartbeat_failed: %s", exc)
        raise SystemExit(1) from exc

    # Register ORM relationships before any Session/query (same need as scheduler).
    from app.database.orm_bootstrap import register_orm_models

    register_orm_models()

    from app.database.database import SessionLocal
    from app.monitoring.queue import promote_due_jobs
    from app.webhooks.outbox import redrive_stuck_deliveries

    while _RUNNING:
        try:
            heartbeat(r)
        except Exception as exc:  # noqa: BLE001
            logger.error("worker_heartbeat_failed: %s", exc)
            time.sleep(1)
            try:
                r, host, port = _connect_redis()
                logger.info("worker redis reconnected %s:%s", host, port)
            except Exception as reconnect_exc:  # noqa: BLE001
                logger.error("worker_redis_reconnect_failed: %s", reconnect_exc)
                time.sleep(2)
                continue

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

        try:
            item = r.blpop("thtwaat:jobs", timeout=5)
        except Exception as exc:  # noqa: BLE001
            logger.error("worker_blpop_failed: %s", exc)
            time.sleep(1)
            continue

        if not item:
            continue
        _, raw = item
        try:
            payload = json.loads(raw)
        except Exception as exc:
            logger.exception("job_parse_failed: %s", exc)
            try:
                r.rpush("thtwaat:jobs:dead", raw)
            except Exception:  # noqa: BLE001
                pass
            continue

        job_type = payload.get("type")
        try:
            logger.info("job_start type=%s attempt=%s", job_type, payload.get("attempt") or 1)
            # Refresh liveness while long jobs run (Studio deploy can exceed 60s).
            heartbeat(r)
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
            elif job_type in {"studio.deploy", "studio.build"}:
                try:
                    _handle_studio_job_failure(payload, exc)
                except Exception as inner:  # noqa: BLE001
                    logger.exception("studio_retry_handler_failed: %s", inner)
                    r.rpush("thtwaat:jobs:dead", raw)
            elif job_type == "domain.auto_progress":
                try:
                    _handle_domain_job_failure(payload, exc)
                except Exception as inner:  # noqa: BLE001
                    logger.exception("domain_retry_handler_failed: %s", inner)
                    r.rpush("thtwaat:jobs:dead", raw)
            else:
                r.rpush("thtwaat:jobs:dead", raw)
        time.sleep(0.05)

    logger.info("worker stopped")


if __name__ == "__main__":
    main()
