"""
app/ai/router.py

FastAPI router for the Enterprise AI Gateway.
"""
import uuid
from typing import List, Dict
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.ai.service import AIService
from app.ai.schema import (
    ChatRequest, ChatResponse, 
    GenerateRequest, GenerateResponse, 
    AIHistoryResponse
)
from app.ai.providers.factory import AIProviderFactory

router = APIRouter(
    prefix="/ai",
    tags=["AI Gateway"],
)

def get_ai_service(db: Session = Depends(get_db)) -> AIService:
    return AIService(db)

@router.post("/chat", response_model=ChatResponse, summary="Interactive multi-turn chat")
async def chat_endpoint(
    payload: ChatRequest,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: AIService = Depends(get_ai_service)
):
    return await service.chat(company_id=current_user.company_id, user_id=current_user.id, payload=payload)

@router.post("/generate", response_model=GenerateResponse, summary="Single prompt text generation")
async def generate_endpoint(
    payload: GenerateRequest,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: AIService = Depends(get_ai_service)
):
    return await service.generate(company_id=current_user.company_id, user_id=current_user.id, payload=payload)

@router.get("/history", response_model=List[AIHistoryResponse], summary="Get user AI request history")
def get_history_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserProfileResponse = Depends(get_current_user),
    service: AIService = Depends(get_ai_service)
):
    return service.get_history(company_id=current_user.company_id, user_id=current_user.id, page=page, page_size=page_size)

@router.delete("/history/{request_id}", status_code=status.HTTP_200_OK, summary="Delete history record")
def delete_history_endpoint(
    request_id: uuid.UUID,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: AIService = Depends(get_ai_service)
):
    service.delete_history(company_id=current_user.company_id, request_id=request_id)
    return {"message": "History deleted successfully"}

@router.get("/providers", summary="List supported AI Providers")
def list_providers_endpoint():
    return {
        "providers": ["openai", "gemini", "anthropic", "ollama", "openrouter"],
        "default": "openai"
    }

@router.get("/models", summary="List supported models for a provider")
async def list_models_endpoint(provider: str = Query("openai")):
    provider_instance = AIProviderFactory.get_provider(provider)
    models = await provider_instance.models()
    return {"provider": provider, "models": models}

@router.get("/health", summary="Check Provider Health / Configuration")
async def health_endpoint(service: AIService = Depends(get_ai_service)):
    return await service.get_health()
