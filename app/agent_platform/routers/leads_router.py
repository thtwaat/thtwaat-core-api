"""Lead capture list/create for production agents."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_and_company
from app.database.database import get_db
from app.agent_platform.agent_runtime import extract_lead, merge_lead_into_metadata
from app.agent_platform.dependencies import verify_api_key, verify_api_key_from_value
from app.agent_platform.models.api_key import AgentApiKey
from app.agent_platform.models.conversation import Conversation, Message
from app.agent_platform.models.agent import AgentConfig

router = APIRouter(prefix="/v2/leads", tags=["Leads"])
public_leads_router = APIRouter(prefix="/public/v1", tags=["Public Agent API"])


class LeadResponse(BaseModel):
    conversation_id: UUID
    agent_id: UUID
    channel: str
    status: str
    lead: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PublicLeadRequest(BaseModel):
    api_key: Optional[str] = None
    session_id: Optional[str] = None
    lead: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PublicLeadResponse(BaseModel):
    conversation_id: str
    lead: Dict[str, Any]


class PublicHandoffRequest(BaseModel):
    api_key: Optional[str] = None
    session_id: str
    reason: Optional[str] = None


class PublicSessionMessagesResponse(BaseModel):
    conversation_id: str
    status: str
    messages: List[Dict[str, Any]]


def _resolve_public_key(request: Request, api_key: Optional[str], db: Session) -> AgentApiKey:
    if api_key:
        return verify_api_key_from_value(api_key, db)
    return verify_api_key(request, db)


@router.get("", response_model=List[LeadResponse])
def list_leads(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    agent_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company),
):
    """List captured leads from conversation metadata (company-scoped)."""
    company_id = auth_data.get("company_id")
    q = db.query(Conversation).filter(Conversation.company_id == company_id)
    if agent_id:
        q = q.filter(Conversation.agent_id == agent_id)
    # JSONB contains lead key — dialect-friendly filter via Python for SQLite unit tests
    rows = q.order_by(Conversation.updated_at.desc()).offset(skip).limit(limit * 5).all()
    out: List[LeadResponse] = []
    for conv in rows:
        meta = conv.extra_metadata or {}
        lead = meta.get("lead") if isinstance(meta, dict) else None
        if not isinstance(lead, dict) or not lead:
            continue
        out.append(
            LeadResponse(
                conversation_id=conv.id,
                agent_id=conv.agent_id,
                channel=conv.channel or "widget",
                status=conv.status or "open",
                lead=lead,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        )
        if len(out) >= limit:
            break
    return out


@public_leads_router.post("/leads", response_model=PublicLeadResponse, status_code=status.HTTP_201_CREATED)
def public_capture_lead(
    body: PublicLeadRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Capture a lead on a widget session (creates conversation if needed)."""
    key = _resolve_public_key(request, body.api_key, db)
    agent = db.query(AgentConfig).filter(AgentConfig.id == key.agent_id).first()
    if not agent or agent.status != "PUBLISHED":
        raise HTTPException(status_code=403, detail="Agent is not published")

    payload = dict(body.metadata or {})
    payload["lead"] = body.lead
    lead = extract_lead(payload)
    if not lead:
        raise HTTPException(status_code=400, detail="Lead requires name, email, or phone")

    conv: Optional[Conversation] = None
    if body.session_id:
        try:
            conv = (
                db.query(Conversation)
                .filter(
                    Conversation.id == UUID(body.session_id),
                    Conversation.company_id == key.company_id,
                    Conversation.agent_id == agent.id,
                )
                .first()
            )
        except ValueError:
            conv = None

    if not conv:
        conv = Conversation(
            company_id=key.company_id,
            agent_id=agent.id,
            title=f"Lead: {lead.get('name') or lead.get('email') or 'Visitor'}"[:80],
            channel="widget",
            status="open",
            extra_metadata=merge_lead_into_metadata({}, lead),
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
    else:
        conv.extra_metadata = merge_lead_into_metadata(conv.extra_metadata, lead)
        conv.updated_at = datetime.now(timezone.utc)
        db.add(conv)
        db.commit()
        db.refresh(conv)

    return PublicLeadResponse(conversation_id=str(conv.id), lead=lead)


@public_leads_router.post("/handoff")
def public_request_handoff(
    body: PublicHandoffRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Visitor requests human handoff for an existing session."""
    key = _resolve_public_key(request, body.api_key, db)
    try:
        conv_id = UUID(body.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session_id") from exc

    conv = (
        db.query(Conversation)
        .filter(
            Conversation.id == conv_id,
            Conversation.company_id == key.company_id,
            Conversation.agent_id == key.agent_id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv.status = "pending_human"
    note = body.reason or "Visitor requested a human agent."
    db.add(Message(conversation_id=conv.id, role="assistant", content=note))
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"conversation_id": str(conv.id), "status": conv.status, "handoff": True}


@public_leads_router.get("/sessions/{session_id}/messages", response_model=PublicSessionMessagesResponse)
def public_session_messages(
    session_id: str,
    request: Request,
    api_key: Optional[str] = None,
    after: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Poll widget session messages (includes human operator replies)."""
    key = _resolve_public_key(request, api_key, db)
    try:
        conv_id = UUID(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session_id") from exc

    conv = (
        db.query(Conversation)
        .filter(
            Conversation.id == conv_id,
            Conversation.company_id == key.company_id,
            Conversation.agent_id == key.agent_id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    out = []
    seen_after = after is None
    after_id = None
    if after:
        try:
            after_id = UUID(after)
        except ValueError:
            after_id = None
            seen_after = True
    for m in messages:
        if not seen_after:
            if after_id and m.id == after_id:
                seen_after = True
            continue
        out.append(
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
        )

    return PublicSessionMessagesResponse(
        conversation_id=str(conv.id),
        status=conv.status or "open",
        messages=out,
    )
