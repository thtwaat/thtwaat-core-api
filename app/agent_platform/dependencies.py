from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from uuid import UUID
import hashlib

from app.database.database import get_db
from app.agent_platform.models.api_key import AgentApiKey
from app.agent_platform.models.quota import CompanyQuota

def verify_api_key(request: Request, db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer tht_"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
    
    raw_key = auth_header.split("Bearer ")[1]
    key_hash = hashlib.sha256(f"tht_{raw_key}".encode()).hexdigest()
    
    api_key = db.query(AgentApiKey).filter(AgentApiKey.key_hash == key_hash, AgentApiKey.is_active == True).first()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    
    return api_key

def enforce_quota(api_key: AgentApiKey = Depends(verify_api_key), db: Session = Depends(get_db)):
    quota = db.query(CompanyQuota).filter(CompanyQuota.company_id == api_key.company_id).first()
    
    # If no quota record exists, we might default to allowed, or create one.
    if quota:
        if quota.current_spend >= quota.monthly_spend_limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Monthly spend limit reached")
        
        if quota.current_tokens >= quota.monthly_token_limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Monthly token limit reached")
            
    return api_key
