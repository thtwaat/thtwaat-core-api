"""Enterprise AI Gateway workspace settings + analytics."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Session

from app.models.base import Base, TimestampMixin


class AIGatewayWorkspaceSettings(Base, TimestampMixin):
    __tablename__ = "ai_gateway_workspace_settings"

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    default_provider = Column(String(64), nullable=False, default="openai")
    allowed_providers = Column(JSONB, nullable=False, default=list)
    monthly_token_limit = Column(Integer, nullable=True)
    monthly_request_limit = Column(Integer, nullable=True)
    monthly_cost_limit_usd = Column(Float, nullable=True)
    routing_policy = Column(String(64), nullable=False, default="default")
    retry_max_attempts = Column(Integer, nullable=False, default=2)
    timeout_seconds = Column(Float, nullable=False, default=60.0)


KNOWN_PROVIDERS = ["openai", "gemini", "anthropic", "ollama", "openrouter"]

PROVIDER_CAPABILITIES: Dict[str, List[str]] = {
    "openai": ["chat", "streaming", "vision", "tools", "embeddings"],
    "gemini": ["chat", "streaming", "vision", "embeddings"],
    "anthropic": ["chat", "streaming", "vision", "tools"],
    "ollama": ["chat", "streaming", "embeddings"],
    "openrouter": ["chat", "streaming", "vision", "tools"],
}


def get_or_create_workspace_settings(db: Session, company_id: uuid.UUID) -> AIGatewayWorkspaceSettings:
    row = db.get(AIGatewayWorkspaceSettings, company_id)
    if row:
        return row
    from app.config.settings import settings

    row = AIGatewayWorkspaceSettings(
        company_id=company_id,
        default_provider=(settings.AI_PROVIDER or "openai").strip().lower(),
        allowed_providers=list(KNOWN_PROVIDERS),
        routing_policy=getattr(settings, "INFERENCE_ROUTING_POLICY", "default") or "default",
        retry_max_attempts=int(getattr(settings, "GATEWAY_RETRY_MAX_ATTEMPTS", 2) or 2),
        timeout_seconds=float(getattr(settings, "GATEWAY_REQUEST_TIMEOUT_SECONDS", 60.0) or 60.0),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_workspace_settings(
    db: Session,
    company_id: uuid.UUID,
    *,
    default_provider: Optional[str] = None,
    allowed_providers: Optional[List[str]] = None,
    monthly_token_limit: Optional[int] = None,
    monthly_request_limit: Optional[int] = None,
    monthly_cost_limit_usd: Optional[float] = None,
    routing_policy: Optional[str] = None,
    retry_max_attempts: Optional[int] = None,
    timeout_seconds: Optional[float] = None,
) -> AIGatewayWorkspaceSettings:
    row = get_or_create_workspace_settings(db, company_id)
    if default_provider is not None:
        name = default_provider.strip().lower()
        if name not in KNOWN_PROVIDERS:
            raise ValueError(f"Unknown provider: {default_provider}")
        row.default_provider = name
    if allowed_providers is not None:
        cleaned = [p.strip().lower() for p in allowed_providers if p and p.strip().lower() in KNOWN_PROVIDERS]
        if not cleaned:
            raise ValueError("allowed_providers must include at least one known provider")
        row.allowed_providers = cleaned
        if row.default_provider not in cleaned:
            row.default_provider = cleaned[0]
    if monthly_token_limit is not None:
        row.monthly_token_limit = monthly_token_limit
    if monthly_request_limit is not None:
        row.monthly_request_limit = monthly_request_limit
    if monthly_cost_limit_usd is not None:
        row.monthly_cost_limit_usd = monthly_cost_limit_usd
    if routing_policy is not None:
        row.routing_policy = routing_policy.strip().lower() or "default"
    if retry_max_attempts is not None:
        row.retry_max_attempts = max(1, int(retry_max_attempts))
    if timeout_seconds is not None:
        row.timeout_seconds = max(1.0, float(timeout_seconds))
    db.commit()
    db.refresh(row)
    return row


def workspace_settings_dict(row: AIGatewayWorkspaceSettings) -> Dict[str, Any]:
    return {
        "company_id": str(row.company_id),
        "default_provider": row.default_provider,
        "allowed_providers": list(row.allowed_providers or []),
        "monthly_token_limit": row.monthly_token_limit,
        "monthly_request_limit": row.monthly_request_limit,
        "monthly_cost_limit_usd": row.monthly_cost_limit_usd,
        "routing_policy": row.routing_policy,
        "retry_max_attempts": row.retry_max_attempts,
        "timeout_seconds": row.timeout_seconds,
        "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
    }


def build_gateway_dashboard(db: Session, company_id: uuid.UUID) -> Dict[str, Any]:
    """Aggregate tokens / cost / latency / success for workspace + live routing metrics."""
    from app.ai.model import AIRequest, AIRequestStatus
    from app.openai_compat.providers.metrics import get_routing_metrics

    since = datetime.now(timezone.utc) - timedelta(days=30)
    rows = (
        db.query(AIRequest)
        .filter(
            AIRequest.company_id == company_id,
            AIRequest.deleted_at.is_(None),
            AIRequest.created_at >= since,
        )
        .all()
    )
    total = len(rows)
    success = sum(1 for r in rows if r.status == AIRequestStatus.SUCCESS)
    failed = total - success
    tokens = sum(int(r.tokens_input or 0) + int(r.tokens_output or 0) for r in rows)
    cost = sum(float(r.estimated_cost or 0) for r in rows)
    latencies = [float(r.latency or 0) for r in rows if r.latency]
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
    success_rate = round((success / total) * 100, 2) if total else 100.0

    by_provider: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        key = (r.provider or "unknown").lower()
        bucket = by_provider.setdefault(
            key,
            {"requests": 0, "tokens": 0, "cost": 0.0, "errors": 0, "latency_sum": 0.0, "latency_n": 0},
        )
        bucket["requests"] += 1
        bucket["tokens"] += int(r.tokens_input or 0) + int(r.tokens_output or 0)
        bucket["cost"] += float(r.estimated_cost or 0)
        if r.status != AIRequestStatus.SUCCESS:
            bucket["errors"] += 1
        if r.latency:
            bucket["latency_sum"] += float(r.latency)
            bucket["latency_n"] += 1

    provider_stats = []
    for name, b in sorted(by_provider.items()):
        provider_stats.append(
            {
                "provider": name,
                "requests": b["requests"],
                "tokens": b["tokens"],
                "cost": round(b["cost"], 6),
                "error_rate": round((b["errors"] / b["requests"]) * 100, 2) if b["requests"] else 0.0,
                "avg_latency_ms": round(b["latency_sum"] / b["latency_n"], 2) if b["latency_n"] else 0.0,
            }
        )

    live = get_routing_metrics().snapshot()
    settings_row = get_or_create_workspace_settings(db, company_id)

    return {
        "window_days": 30,
        "requests": total,
        "success": success,
        "failed": failed,
        "success_rate": success_rate,
        "tokens": tokens,
        "cost": round(cost, 6),
        "currency": "USD",
        "avg_latency_ms": avg_latency,
        "providers": provider_stats,
        "live_routing": live,
        "workspace": workspace_settings_dict(settings_row),
        "capabilities": PROVIDER_CAPABILITIES,
    }
