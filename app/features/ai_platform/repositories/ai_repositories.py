from app.features.ai_platform.repositories.base import BaseRepository
from app.features.ai_platform.database.models import (
    AiProvider, AiModel, AiPromptTemplate, AiTool, AiAgent, AiConversation, AiMessage, AiUsage, AiAgentTool
)
from app.features.ai_platform.schemas.ai_schemas import (
    AiProviderCreate, AiProviderUpdate,
    AiModelCreate, AiModelUpdate,
    AiPromptTemplateCreate, AiPromptTemplateUpdate,
    AiToolCreate, AiToolUpdate,
    AiAgentCreate, AiAgentUpdate,
    AiConversationCreate, AiConversationUpdate,
    AiUsageCreate
)
from sqlalchemy.orm import Session
from uuid import UUID

class AiProviderRepository(BaseRepository[AiProvider, AiProviderCreate, AiProviderUpdate]):
    def __init__(self, db: Session):
        super().__init__(AiProvider, db)

class AiModelRepository(BaseRepository[AiModel, AiModelCreate, AiModelUpdate]):
    def __init__(self, db: Session):
        super().__init__(AiModel, db)

class AiPromptTemplateRepository(BaseRepository[AiPromptTemplate, AiPromptTemplateCreate, AiPromptTemplateUpdate]):
    def __init__(self, db: Session):
        super().__init__(AiPromptTemplate, db)

class AiToolRepository(BaseRepository[AiTool, AiToolCreate, AiToolUpdate]):
    def __init__(self, db: Session):
        super().__init__(AiTool, db)

class AiAgentRepository(BaseRepository[AiAgent, AiAgentCreate, AiAgentUpdate]):
    def __init__(self, db: Session):
        super().__init__(AiAgent, db)
    
    def create(self, company_id: UUID, obj_in: AiAgentCreate, **kwargs) -> AiAgent:
        obj_data = obj_in.model_dump(exclude={"tool_ids"})
        db_obj = self.model(company_id=company_id, **obj_data, **kwargs)
        self.db.add(db_obj)
        self.db.flush()
        
        for tool_id in obj_in.tool_ids:
            agent_tool = AiAgentTool(agent_id=db_obj.id, tool_id=tool_id)
            self.db.add(agent_tool)
            
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

class AiConversationRepository(BaseRepository[AiConversation, AiConversationCreate, AiConversationUpdate]):
    def __init__(self, db: Session):
        super().__init__(AiConversation, db)

class AiUsageRepository(BaseRepository[AiUsage, AiUsageCreate, AiUsageCreate]): # Using AiUsageCreate for update as placeholder
    def __init__(self, db: Session):
        super().__init__(AiUsage, db)
