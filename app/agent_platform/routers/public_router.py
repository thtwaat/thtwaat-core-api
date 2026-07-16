from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID

from app.database.database import get_db
from app.agent_platform.schemas import UnifiedChatRequest, UnifiedChatResponse
from app.agent_platform.gateway.service import AIGatewayService
from app.agent_platform.dependencies import enforce_quota
from app.agent_platform.models.api_key import AgentApiKey
from app.agent_platform.models.agent import AgentConfig

router = APIRouter(prefix="/public/v1", tags=["Public Agent API"])

@router.post("/chat", response_model=UnifiedChatResponse)
async def public_chat(
    request: UnifiedChatRequest,
    api_key: AgentApiKey = Depends(enforce_quota),
    db: Session = Depends(get_db)
):
    # Ensure the requested agent_id matches the one bound to the API key
    if str(api_key.agent_id) != str(request.agent_id):
        raise HTTPException(status_code=403, detail="API key is not authorized for this agent")
        
    # Get the agent config to find default provider/model if not specified
    agent = db.query(AgentConfig).filter(AgentConfig.id == api_key.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    # Inject company_id from API key securely
    request.company_id = str(api_key.company_id)
    
    # Prepend system prompt if it exists
    if agent.system_prompt_template:
        request.messages.insert(0, {"role": "system", "content": agent.system_prompt_template})
    
    # Process through the Universal AI Gateway
    response = await AIGatewayService.process_request(request)
    
    # Add usage to current spend/tokens (normally async via BackgroundTasks)
    # ... Update CompanyQuota ...
    
    return response
