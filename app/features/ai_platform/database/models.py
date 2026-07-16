import uuid
import enum
from sqlalchemy import Column, String, Text, Boolean, Integer, ForeignKey, Numeric, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin

class AiModelType(str, enum.Enum):
    CHAT = "chat"
    EMBEDDING = "embedding"

class AiConversationStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"

class AiMessageRole(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

class AiProvider(Base, TimestampMixin):
    __tablename__ = "ai_providers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String(100), nullable=False)
    base_url = Column(String(500), nullable=True)
    api_key_encrypted = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    models = relationship("AiModel", back_populates="provider", cascade="all, delete-orphan")

class AiModel(Base, TimestampMixin):
    __tablename__ = "ai_models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("ai_providers.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String(100), nullable=False)
    type = Column(SAEnum(AiModelType, name="ai_model_type_enum"), default=AiModelType.CHAT, nullable=False)
    cost_per_1k_input = Column(Numeric(10, 6), default=0.0, nullable=False)
    cost_per_1k_output = Column(Numeric(10, 6), default=0.0, nullable=False)

    provider = relationship("AiProvider", back_populates="models")
    agents = relationship("AiAgent", back_populates="model")

class AiPromptTemplate(Base, TimestampMixin):
    __tablename__ = "ai_prompt_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String(100), nullable=False)
    template_text = Column(Text, nullable=False)
    variables_json = Column(JSONB, default=list, nullable=False)

    agents = relationship("AiAgent", back_populates="system_prompt")

class AiTool(Base, TimestampMixin):
    __tablename__ = "ai_tools"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    json_schema = Column(JSONB, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    agents = relationship("AiAgentTool", back_populates="tool", cascade="all, delete-orphan")

class AiAgent(Base, TimestampMixin):
    __tablename__ = "ai_agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    system_prompt_id = Column(UUID(as_uuid=True), ForeignKey("ai_prompt_templates.id", ondelete="SET NULL"), nullable=True)
    model_id = Column(UUID(as_uuid=True), ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True)
    configuration_json = Column(JSONB, default=dict, nullable=False)
    
    system_prompt = relationship("AiPromptTemplate", back_populates="agents")
    model = relationship("AiModel", back_populates="agents")
    tools = relationship("AiAgentTool", back_populates="agent", cascade="all, delete-orphan")
    conversations = relationship("AiConversation", back_populates="agent", cascade="all, delete-orphan")

class AiAgentTool(Base, TimestampMixin):
    __tablename__ = "ai_agent_tools"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False)
    tool_id = Column(UUID(as_uuid=True), ForeignKey("ai_tools.id", ondelete="CASCADE"), nullable=False)

    agent = relationship("AiAgent", back_populates="tools")
    tool = relationship("AiTool", back_populates="agents")

class AiConversation(Base, TimestampMixin):
    __tablename__ = "ai_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=True)
    status = Column(SAEnum(AiConversationStatus, name="ai_conversation_status_enum"), default=AiConversationStatus.ACTIVE, nullable=False)

    agent = relationship("AiAgent", back_populates="conversations")
    messages = relationship("AiMessage", back_populates="conversation", cascade="all, delete-orphan")
    usage_records = relationship("AiUsage", back_populates="conversation", cascade="all, delete-orphan")

class AiMessage(Base, TimestampMixin):
    __tablename__ = "ai_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(SAEnum(AiMessageRole, name="ai_message_role_enum"), nullable=False)
    content = Column(Text, nullable=False)

    conversation = relationship("AiConversation", back_populates="messages")

class AiUsage(Base, TimestampMixin):
    __tablename__ = "ai_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False)
    model_id = Column(UUID(as_uuid=True), ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    total_cost = Column(Numeric(10, 6), default=0.0, nullable=False)

    conversation = relationship("AiConversation", back_populates="usage_records")
