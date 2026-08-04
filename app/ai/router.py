"""
app/ai/router.py

FastAPI router for the Enterprise AI Gateway.
"""
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.gateway_workspace import (
    KNOWN_PROVIDERS,
    PROVIDER_CAPABILITIES,
    build_gateway_dashboard,
    get_or_create_workspace_settings,
    update_workspace_settings,
    workspace_settings_dict,
)
from app.ai.providers.factory import AIProviderFactory
from app.ai.schema import (
    AIHistoryResponse,
    ChatRequest,
    ChatResponse,
    GenerateRequest,
    GenerateResponse,
)
from app.ai.service import AIService
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.config.settings import settings
from app.database.database import get_db

router = APIRouter(
    prefix="/ai",
    tags=["AI Gateway"],
)


def get_ai_service(db: Session = Depends(get_db)) -> AIService:
    return AIService(db)


class WorkspaceSettingsUpdate(BaseModel):
    default_provider: Optional[str] = None
    allowed_providers: Optional[List[str]] = None
    monthly_token_limit: Optional[int] = Field(default=None, ge=0)
    monthly_request_limit: Optional[int] = Field(default=None, ge=0)
    monthly_cost_limit_usd: Optional[float] = Field(default=None, ge=0)
    routing_policy: Optional[str] = None
    retry_max_attempts: Optional[int] = Field(default=None, ge=1, le=10)
    timeout_seconds: Optional[float] = Field(default=None, ge=1, le=600)


@router.post("/chat", response_model=ChatResponse, summary="Interactive multi-turn chat")
async def chat_endpoint(
    payload: ChatRequest,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: AIService = Depends(get_ai_service),
):
    return await service.chat(
        company_id=current_user.company_id, user_id=current_user.id, payload=payload
    )


@router.post("/generate", response_model=GenerateResponse, summary="Single prompt text generation")
async def generate_endpoint(
    payload: GenerateRequest,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: AIService = Depends(get_ai_service),
):
    return await service.generate(
        company_id=current_user.company_id, user_id=current_user.id, payload=payload
    )


@router.get("/history", response_model=List[AIHistoryResponse], summary="Get user AI request history")
def get_history_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserProfileResponse = Depends(get_current_user),
    service: AIService = Depends(get_ai_service),
):
    return service.get_history(
        company_id=current_user.company_id,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )


@router.delete("/history/{request_id}", status_code=status.HTTP_200_OK, summary="Delete history record")
def delete_history_endpoint(
    request_id: uuid.UUID,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: AIService = Depends(get_ai_service),
):
    service.delete_history(company_id=current_user.company_id, request_id=request_id)
    return {"message": "History deleted successfully"}


@router.get("/providers", summary="List supported AI Providers")
def list_providers_endpoint(
    current_user: UserProfileResponse = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ws = get_or_create_workspace_settings(db, uuid.UUID(str(current_user.company_id)))
    return {
        "providers": list(KNOWN_PROVIDERS),
        "default": ws.default_provider or settings.AI_PROVIDER or "openai",
        # Additive fields — existing clients ignore extras
        "allowed_providers": list(ws.allowed_providers or KNOWN_PROVIDERS),
        "capabilities": PROVIDER_CAPABILITIES,
        "routing_policy": ws.routing_policy,
    }


@router.get("/models", summary="List supported models for a provider")
async def list_models_endpoint(
    provider: str = Query("openai"),
    current_user: UserProfileResponse = Depends(get_current_user),
):
    _ = current_user
    provider_instance = AIProviderFactory.get_provider(provider)
    models = await provider_instance.models()
    return {"provider": provider, "models": models}


@router.get("/health", summary="Check Provider Health / Configuration")
async def health_endpoint(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: AIService = Depends(get_ai_service),
):
    _ = current_user
    # Backward-compatible map of provider -> status string
    return await service.get_health()


@router.get("/gateway/dashboard", summary="Enterprise AI Gateway analytics dashboard")
def gateway_dashboard(
    current_user: UserProfileResponse = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return build_gateway_dashboard(db, uuid.UUID(str(current_user.company_id)))


@router.get("/gateway/capabilities", summary="Provider capability registry")
def gateway_capabilities(
    current_user: UserProfileResponse = Depends(get_current_user),
):
    _ = current_user
    return {"providers": PROVIDER_CAPABILITIES, "known_providers": KNOWN_PROVIDERS}


@router.get("/workspace-settings", summary="Workspace AI gateway settings")
def get_workspace_settings(
    current_user: UserProfileResponse = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_or_create_workspace_settings(db, uuid.UUID(str(current_user.company_id)))
    return workspace_settings_dict(row)


@router.put("/workspace-settings", summary="Update workspace AI gateway settings")
def put_workspace_settings(
    payload: WorkspaceSettingsUpdate,
    current_user: UserProfileResponse = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        row = update_workspace_settings(
            db,
            uuid.UUID(str(current_user.company_id)),
            **payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return workspace_settings_dict(row)


@router.get("/gateway/health-detail", summary="Live provider health with latency hints")
async def gateway_health_detail(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: AIService = Depends(get_ai_service),
    db: Session = Depends(get_db),
):
    """Additive rich health payload (does not replace GET /ai/health)."""
    basic = await service.get_health()
    dash = build_gateway_dashboard(db, uuid.UUID(str(current_user.company_id)))
    live = dash.get("live_routing") or {}
    latency = live.get("provider_latency_ms") or {}
    details: Dict[str, Any] = {}
    for name in KNOWN_PROVIDERS:
        lat = latency.get(name) or {}
        details[name] = {
            "status": basic.get(name, "unknown"),
            "avg_latency_ms": lat.get("avg"),
            "last_latency_ms": lat.get("last"),
            "capabilities": PROVIDER_CAPABILITIES.get(name, []),
        }
    return {
        "providers": details,
        "success_rate": dash.get("success_rate"),
        "avg_latency_ms": dash.get("avg_latency_ms"),
        "cost": dash.get("cost"),
        "tokens": dash.get("tokens"),
        "requests": dash.get("requests"),
    }
