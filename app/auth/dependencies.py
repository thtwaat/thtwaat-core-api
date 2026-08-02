from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.auth.service import AuthService
from app.auth.security import bearer_scheme

security = bearer_scheme

def get_current_user_and_company(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    service = AuthService(db)
    user_profile = service.get_current_user_profile(credentials.credentials)
    return {"company_id": user_profile.company_id, "user_id": user_profile.id}
