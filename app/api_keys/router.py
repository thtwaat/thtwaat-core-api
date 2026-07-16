from fastapi import APIRouter, Depends, HTTPException, Security, Header
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.api_keys.schema import APIKeyCreate, APIKeyResponse, APIKeyGenerateResponse
from app.api_keys.service import APIKeyService
from app.auth.router import get_current_user
from typing import List

router = APIRouter(prefix="/api-keys", tags=["API Keys"])

# Middleware Dependency
def get_api_key_user(
    x_api_key: str = Header(..., description="The API Key for authentication"),
    db: Session = Depends(get_db)
) -> dict:
    service = APIKeyService(db)
    try:
        # Returns {"company_id": ..., "app_label": ...} if valid
        return service.authenticate_key(x_api_key)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Invalid API Key")

# Admin endpoints (protected by normal JWT auth)
@router.post("", response_model=APIKeyGenerateResponse)
def generate_api_key(
    data: APIKeyCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    service = APIKeyService(db)
    # Ensure user has a company
    if not hasattr(current_user, "company_id") or not current_user.company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")
    
    return service.create_api_key(company_id=current_user.company_id, data=data)

@router.get("", response_model=List[APIKeyResponse])
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    service = APIKeyService(db)
    if not hasattr(current_user, "company_id") or not current_user.company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")
    
    return service.list_api_keys(company_id=current_user.company_id)

@router.delete("/{api_key_id}")
def revoke_api_key(
    api_key_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    service = APIKeyService(db)
    if not hasattr(current_user, "company_id") or not current_user.company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")
    
    service.revoke_api_key(api_key_id, company_id=current_user.company_id)
    return {"status": "success", "message": "API key revoked"}
