from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.features.ai_platform.repositories.ai_repositories import (
    AiProviderRepository, AiModelRepository, AiPromptTemplateRepository,
    AiToolRepository, AiAgentRepository, AiConversationRepository, AiUsageRepository
)
from app.features.ai_platform.schemas.ai_schemas import (
    AiProviderCreate, AiProviderUpdate,
    AiModelCreate, AiModelUpdate,
    AiPromptTemplateCreate, AiPromptTemplateUpdate,
    AiToolCreate, AiToolUpdate,
    AiAgentCreate, AiAgentUpdate,
    AiConversationCreate, AiConversationUpdate
)

class AiPlatformService:
    def __init__(self, db: Session):
        self.db = db
        self.provider_repo = AiProviderRepository(db)
        self.model_repo = AiModelRepository(db)
        self.prompt_repo = AiPromptTemplateRepository(db)
        self.tool_repo = AiToolRepository(db)
        self.agent_repo = AiAgentRepository(db)
        self.conversation_repo = AiConversationRepository(db)
        self.usage_repo = AiUsageRepository(db)

    # Provider Methods
    def create_provider(self, company_id: UUID, provider_in: AiProviderCreate):
        return self.provider_repo.create(company_id=company_id, obj_in=provider_in)
    
    def get_providers(self, company_id: UUID, skip: int = 0, limit: int = 100):
        return self.provider_repo.get_multi(company_id=company_id, skip=skip, limit=limit)

    # Model Methods
    def create_model(self, company_id: UUID, model_in: AiModelCreate):
        return self.model_repo.create(company_id=company_id, obj_in=model_in)

    def get_models(self, company_id: UUID, skip: int = 0, limit: int = 100):
        return self.model_repo.get_multi(company_id=company_id, skip=skip, limit=limit)

    # Prompt Methods
    def create_prompt(self, company_id: UUID, prompt_in: AiPromptTemplateCreate):
        return self.prompt_repo.create(company_id=company_id, obj_in=prompt_in)

    def get_prompts(self, company_id: UUID, skip: int = 0, limit: int = 100):
        return self.prompt_repo.get_multi(company_id=company_id, skip=skip, limit=limit)

    # Tool Methods
    def create_tool(self, company_id: UUID, tool_in: AiToolCreate):
        return self.tool_repo.create(company_id=company_id, obj_in=tool_in)

    def get_tools(self, company_id: UUID, skip: int = 0, limit: int = 100):
        return self.tool_repo.get_multi(company_id=company_id, skip=skip, limit=limit)

    # Agent Methods
    def create_agent(self, company_id: UUID, agent_in: AiAgentCreate):
        return self.agent_repo.create(company_id=company_id, obj_in=agent_in)

    def get_agents(self, company_id: UUID, skip: int = 0, limit: int = 100):
        return self.agent_repo.get_multi(company_id=company_id, skip=skip, limit=limit)

    # Conversation Methods
    def create_conversation(self, company_id: UUID, conversation_in: AiConversationCreate):
        return self.conversation_repo.create(company_id=company_id, obj_in=conversation_in)

    def get_conversations(self, company_id: UUID, skip: int = 0, limit: int = 100):
        return self.conversation_repo.get_multi(company_id=company_id, skip=skip, limit=limit)
