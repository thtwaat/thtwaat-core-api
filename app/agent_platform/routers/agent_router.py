from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database.database import get_db
from app.auth.dependencies import get_current_user_and_company
from app.agent_platform.schemas import AgentCreate, AgentUpdate, AgentResponse, ApiKeyResponse
from app.agent_platform.models.agent import AgentConfig
from app.agent_platform.models.api_key import AgentApiKey
import uuid
import hashlib

router = APIRouter(prefix="/v2/agents", tags=["Agent Platform"])

@router.post("", response_model=AgentResponse)
def create_agent(
    agent_in: AgentCreate,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    company_id = auth_data.get("company_id")
    new_agent = AgentConfig(
        company_id=company_id,
        name=agent_in.name,
        description=agent_in.description,
        system_prompt_template=agent_in.system_prompt_template,
        temperature=agent_in.temperature,
        is_template=agent_in.is_template,
        web_config=agent_in.web_config,
        status="DRAFT",
        version=1
    )
    db.add(new_agent)
    db.commit()
    db.refresh(new_agent)
    return new_agent

@router.get("", response_model=List[AgentResponse])
def list_agents(
    is_template: bool = False,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    company_id = auth_data.get("company_id")
    query = db.query(AgentConfig).filter(AgentConfig.company_id == company_id)
    if is_template:
        query = query.filter(AgentConfig.is_template == True)
    return query.all()

@router.get("/templates", response_model=List[AgentResponse])
def list_templates(
    db: Session = Depends(get_db),
):
    # Fetch global templates (or accessible templates)
    # For now, just return where is_template = True
    return db.query(AgentConfig).filter(AgentConfig.is_template == True).all()

@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: UUID,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    company_id = auth_data.get("company_id")
    agent = db.query(AgentConfig).filter(AgentConfig.id == agent_id, AgentConfig.company_id == company_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@router.post("/{agent_id}/publish", response_model=AgentResponse)
def publish_agent(
    agent_id: UUID,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    company_id = auth_data.get("company_id")
    agent = db.query(AgentConfig).filter(AgentConfig.id == agent_id, AgentConfig.company_id == company_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent.status = "PUBLISHED"
    agent.version += 1
    db.commit()
    db.refresh(agent)
    return agent

@router.post("/{agent_id}/clone", response_model=AgentResponse)
def clone_agent(
    agent_id: UUID,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    company_id = auth_data.get("company_id")
    source_agent = db.query(AgentConfig).filter(AgentConfig.id == agent_id).first()
    if not source_agent:
        raise HTTPException(status_code=404, detail="Source agent not found")
        
    cloned = AgentConfig(
        company_id=company_id, # Re-bind to current company
        name=f"Copy of {source_agent.name}",
        description=source_agent.description,
        system_prompt_template=source_agent.system_prompt_template,
        temperature=source_agent.temperature,
        web_config=source_agent.web_config,
        status="DRAFT",
        version=1,
        is_template=False
    )
    db.add(cloned)
    db.commit()
    db.refresh(cloned)
    return cloned

@router.post("/{agent_id}/api-keys")
def generate_api_key(
    agent_id: UUID,
    name: str = "Default Key",
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company)
):
    company_id = auth_data.get("company_id")
    agent = db.query(AgentConfig).filter(AgentConfig.id == agent_id, AgentConfig.company_id == company_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    raw_key = f"tht_{uuid.uuid4().hex}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    
    api_key = AgentApiKey(
        company_id=company_id,
        agent_id=agent_id,
        key_hash=key_hash,
        name=name
    )
    db.add(api_key)
    db.commit()
    
    return {"api_key": raw_key, "message": "Save this key, it will not be shown again."}
