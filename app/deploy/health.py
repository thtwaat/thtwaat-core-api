"""Production health checks — DB, Redis, storage, workers, AI providers."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config.settings import settings

logger = logging.getLogger(__name__)


def check_database(db: Session) -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        return {"ok": True, "latency_ms": round((time.perf_counter() - start) * 1000, 2)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def check_redis() -> Dict[str, Any]:
    import redis.asyncio as redis

    start = time.perf_counter()
    try:
        r = redis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
            encoding="utf-8",
            decode_responses=True,
        )
        await r.ping()
        await r.aclose()
        return {"ok": True, "latency_ms": round((time.perf_counter() - start) * 1000, 2)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def check_storage() -> Dict[str, Any]:
    try:
        upload = Path(settings.LOCAL_STORAGE_DIR)
        knowledge = Path("data/knowledge")
        upload.mkdir(parents=True, exist_ok=True)
        knowledge.mkdir(parents=True, exist_ok=True)
        probe = upload / ".healthcheck"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return {
            "ok": True,
            "uploads": str(upload.resolve()),
            "knowledge": str(knowledge.resolve()),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def check_workers() -> Dict[str, Any]:
    """Worker heartbeat via Redis key written by worker process."""
    try:
        import redis as sync_redis

        r = sync_redis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
            decode_responses=True,
        )
        beat = r.get("thtwaat:worker:heartbeat")
        queue_len = r.llen("thtwaat:jobs") or 0
        return {
            "ok": beat is not None,
            "heartbeat": beat,
            "queue_depth": int(queue_len),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def check_ai_providers() -> Dict[str, Any]:
    providers = {
        "openai": bool(settings.OPENAI_API_KEY),
        "anthropic": bool(settings.ANTHROPIC_API_KEY),
        "gemini": bool(settings.GEMINI_API_KEY),
        "openrouter": bool(settings.OPENROUTER_API_KEY),
        "ollama": bool(settings.OLLAMA_URL),
    }
    configured = sum(1 for v in providers.values() if v)
    out: Dict[str, Any] = {
        "ok": configured > 0,
        "configured": configured,
        "providers": providers,
    }
    if settings.OLLAMA_URL:
        try:
            from app.openai_compat.inference_adapter import probe_ollama

            out["ollama_live"] = probe_ollama(settings.OLLAMA_URL)
        except Exception as exc:  # noqa: BLE001
            out["ollama_live"] = {"ok": False, "error": str(exc)}
    return out


async def check_inference_providers() -> Dict[str, Any]:
    """Aggregate health for enabled Sem03 inference providers (fail-soft each)."""
    try:
        from app.openai_compat.providers import ensure_providers_registered

        registry = ensure_providers_registered()
        return await registry.aggregate_health()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


async def full_health(db: Session) -> Dict[str, Any]:
    db_c = check_database(db)
    redis_c = await check_redis()
    storage_c = check_storage()
    workers_c = check_workers()
    ai_c = check_ai_providers()
    inference_c = await check_inference_providers()
    ai_c["inference_providers"] = inference_c
    # Overall health stays DB/Redis/storage — inference outage does not 503 the API
    critical_ok = db_c.get("ok") and redis_c.get("ok") and storage_c.get("ok")
    return {
        "status": "healthy" if critical_ok else "degraded",
        "checks": {
            "database": db_c,
            "redis": redis_c,
            "storage": storage_c,
            "workers": workers_c,
            "ai_providers": ai_c,
            "inference_providers": inference_c,
        },
    }
