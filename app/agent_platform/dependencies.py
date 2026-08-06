from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
import hashlib

from app.database.database import get_db
from app.agent_platform.models.api_key import AgentApiKey
from app.agent_platform.models.quota import CompanyQuota


def _extract_raw_key(request: Request, body_api_key: str | None = None) -> str:
    if body_api_key and body_api_key.startswith("tht_"):
        return body_api_key

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer tht_"):
        return auth_header.split("Bearer ", 1)[1].strip()

    # Also accept X-API-Key header
    x_key = request.headers.get("X-API-Key")
    if x_key and x_key.startswith("tht_"):
        return x_key.strip()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key. Use Authorization: Bearer tht_live_... or body.api_key",
    )


def verify_api_key_from_value(raw_key: str, db: Session) -> AgentApiKey:
    if not raw_key or not raw_key.startswith("tht_"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    # Short-lived iframe embed credentials (tht_embed_<jwt>) — not live API keys.
    from app.agent_platform.publish.embed_tokens import parse_embed_credential, verify_embed_token
    from app.agent_platform.models.agent import AgentConfig

    embed_jwt = parse_embed_credential(raw_key)
    if embed_jwt is not None:
        claims = verify_embed_token(embed_jwt)
        agent = (
            db.query(AgentConfig)
            .filter(
                AgentConfig.id == claims["aid"],
                AgentConfig.widget_id == claims["wid"],
                AgentConfig.company_id == claims["cid"],
            )
            .first()
        )
        if not agent or agent.status != "PUBLISHED" or agent.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid embed token",
            )
        api_key = (
            db.query(AgentApiKey)
            .filter(
                AgentApiKey.agent_id == agent.id,
                AgentApiKey.company_id == agent.company_id,
                AgentApiKey.is_active.is_(True),
            )
            .order_by(AgentApiKey.created_at.desc())
            .first()
        )
        if not api_key or api_key.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active API key for this widget",
            )
        if api_key.expires_at is not None and api_key.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key expired")
        api_key.last_used_at = datetime.now(timezone.utc)
        db.commit()
        return api_key

    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    api_key = (
        db.query(AgentApiKey)
        .filter(AgentApiKey.key_hash == key_hash, AgentApiKey.is_active.is_(True))
        .first()
    )
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    if api_key.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key revoked")
    if api_key.expires_at is not None and api_key.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key expired")

    # Soft-deleted agents must not accept traffic (keys may still exist until cleanup).
    agent_row = db.query(AgentConfig).filter(AgentConfig.id == api_key.agent_id).first()
    if not agent_row or agent_row.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Agent unavailable")

    api_key.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return api_key


def verify_api_key(request: Request, db: Session = Depends(get_db)) -> AgentApiKey:
    raw_key = _extract_raw_key(request)
    return verify_api_key_from_value(raw_key, db)


def enforce_quota(api_key: AgentApiKey = Depends(verify_api_key), db: Session = Depends(get_db)) -> AgentApiKey:
    """Enforce Usage Meter + legacy CompanyQuota spend/token caps."""
    from app.usage.dimensions import UsageDimension
    from app.usage.service import UsageService

    UsageService(db).check_quota(api_key.company_id, UsageDimension.AI_MESSAGES, quantity=1)
    UsageService(db).check_quota(api_key.company_id, UsageDimension.TOTAL_TOKENS, quantity=1)

    quota = db.query(CompanyQuota).filter(CompanyQuota.company_id == api_key.company_id).first()

    if quota:
        if quota.current_spend >= quota.monthly_spend_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "quota_exceeded",
                    "dimension": "spend",
                    "current_usage": float(quota.current_spend),
                    "plan_limit": float(quota.monthly_spend_limit),
                    "upgrade_url": "/billing",
                },
            )
        if quota.current_tokens >= quota.monthly_token_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "quota_exceeded",
                    "dimension": "total_tokens",
                    "current_usage": int(quota.current_tokens),
                    "plan_limit": int(quota.monthly_token_limit),
                    "upgrade_url": "/billing",
                },
            )

    return api_key
