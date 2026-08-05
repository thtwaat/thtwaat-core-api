from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app.database.database import get_db
from app.auth.dependencies import get_current_user_and_company
from app.features.ai_platform.schemas.ai_schemas import (
    AiProviderCreate, AiProviderResponse, AiProviderUpdate,
    AiModelCreate, AiModelResponse, AiModelUpdate,
    AiPromptTemplateCreate, AiPromptTemplateResponse, AiPromptTemplateUpdate,
    AiToolCreate, AiToolResponse, AiToolUpdate,
    AiAgentCreate, AiAgentResponse, AiAgentUpdate,
    AiConversationCreate, AiConversationResponse, AiConversationUpdate
)
from app.features.ai_platform.services.ai_services import AiPlatformService

router = APIRouter(
    prefix="/ai-platform",
    tags=["AI Platform (deprecated)"],
    deprecated=True,
)

# Providers
@router.post("/providers", response_model=AiProviderResponse)
def create_provider(
    provider_in: AiProviderCreate,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    service = AiPlatformService(db)
    return service.create_provider(auth_data["company_id"], provider_in)

@router.get("/providers", response_model=List[AiProviderResponse])
def get_providers(
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    service = AiPlatformService(db)
    return service.get_providers(auth_data["company_id"], skip, limit)

# Models
@router.post("/models", response_model=AiModelResponse)
def create_model(
    model_in: AiModelCreate,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    service = AiPlatformService(db)
    return service.create_model(auth_data["company_id"], model_in)

@router.get("/models", response_model=List[AiModelResponse])
def get_models(
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    service = AiPlatformService(db)
    return service.get_models(auth_data["company_id"], skip, limit)

# Agents
@router.post("/agents", response_model=AiAgentResponse)
def create_agent(
    agent_in: AiAgentCreate,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    service = AiPlatformService(db)
    return service.create_agent(auth_data["company_id"], agent_in)

@router.get("/agents", response_model=List[AiAgentResponse])
def get_agents(
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    service = AiPlatformService(db)
    return service.get_agents(auth_data["company_id"], skip, limit)

# Tools
@router.post("/tools", response_model=AiToolResponse)
def create_tool(
    tool_in: AiToolCreate,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    service = AiPlatformService(db)
    return service.create_tool(auth_data["company_id"], tool_in)

@router.get("/tools", response_model=List[AiToolResponse])
def get_tools(
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    service = AiPlatformService(db)
    return service.get_tools(auth_data["company_id"], skip, limit)

# Prompts
@router.post("/prompts", response_model=AiPromptTemplateResponse)
def create_prompt(
    prompt_in: AiPromptTemplateCreate,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    service = AiPlatformService(db)
    return service.create_prompt(auth_data["company_id"], prompt_in)

@router.get("/prompts", response_model=List[AiPromptTemplateResponse])
def get_prompts(
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    service = AiPlatformService(db)
    return service.get_prompts(auth_data["company_id"], skip, limit)

# Conversations
@router.post("/conversations", response_model=AiConversationResponse)
def create_conversation(
    conversation_in: AiConversationCreate,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    service = AiPlatformService(db)
    return service.create_conversation(auth_data["company_id"], conversation_in)

@router.get("/conversations", response_model=List[AiConversationResponse])
def get_conversations(
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    service = AiPlatformService(db)
    return service.get_conversations(auth_data["company_id"], skip, limit)
