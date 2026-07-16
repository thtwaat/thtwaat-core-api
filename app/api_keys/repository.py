from sqlalchemy.orm import Session
from app.api_keys.model import APIKey
import uuid
from typing import List, Optional
from datetime import datetime, timezone

class APIKeyRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, api_key_id: str) -> Optional[APIKey]:
        return self.db.query(APIKey).filter(APIKey.id == api_key_id).first()

    def get_by_company(self, company_id: str) -> List[APIKey]:
        return self.db.query(APIKey).filter(
            APIKey.company_id == company_id,
            APIKey.revoked_at.is_(None)
        ).all()

    def get_all_active(self) -> List[APIKey]:
        return self.db.query(APIKey).filter(APIKey.revoked_at.is_(None)).all()

    def create(self, data: dict) -> APIKey:
        db_obj = APIKey(**data)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def revoke(self, api_key: APIKey) -> APIKey:
        api_key.revoked_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(api_key)
        return api_key

    def update_last_used(self, api_key: APIKey) -> None:
        api_key.last_used_at = datetime.now(timezone.utc)
        self.db.commit()
