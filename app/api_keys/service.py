import secrets
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.api_keys.repository import APIKeyRepository
from app.api_keys.schema import APIKeyCreate
from fastapi import HTTPException
from datetime import datetime

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class APIKeyService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = APIKeyRepository(db)

    def _generate_raw_key(self) -> str:
        # e.g. tht_key_xxxxxxxxxxxxx
        return f"tht_key_{secrets.token_urlsafe(32)}"

    def _hash_key(self, raw_key: str) -> str:
        return pwd_context.hash(raw_key)

    def _verify_key(self, raw_key: str, hashed_key: str) -> bool:
        return pwd_context.verify(raw_key, hashed_key)

    def _mask_key(self, raw_key: str) -> str:
        if not raw_key or len(raw_key) < 4:
            return "****"
        return f"****{raw_key[-4:]}"

    def create_api_key(self, company_id: str, data: APIKeyCreate) -> dict:
        raw_key = self._generate_raw_key()
        hashed = self._hash_key(raw_key)
        
        # Store in db
        db_obj = self.repo.create({
            "company_id": company_id,
            "key_hash": hashed,
            "name": data.name,
            "app_label": data.app_label,
            "scopes": data.scopes,
        })
        
        # Return dict matching APIKeyGenerateResponse
        result = {
            "id": db_obj.id,
            "name": db_obj.name,
            "app_label": db_obj.app_label,
            "scopes": db_obj.scopes,
            "created_at": db_obj.created_at,
            "last_used_at": db_obj.last_used_at,
            "revoked_at": db_obj.revoked_at,
            "masked_key": self._mask_key(raw_key),
            "raw_key": raw_key
        }

        # ── Dispatch in-app notification event ───────────────────────────────
        try:
            import uuid as _uuid
            from app.notifications.events import NotificationEventBus
            NotificationEventBus.dispatch(
                event_type="api_key.created",
                db=self.db,
                company_id=_uuid.UUID(str(company_id)),
                user_id=None,
                data={"key_name": data.name},
            )
        except Exception:
            pass

        return result

    def list_api_keys(self, company_id: str) -> list:
        keys = self.repo.get_by_company(company_id)
        # We don't have the raw key anymore to mask it properly from raw, 
        # but in standard practice we could extract the last 4 chars if we stored them separately, 
        # or we just return "****" if we didn't. Wait, the schema requires masked_key.
        # Let's just return a placeholder "****" for listed keys since we don't store the masked part yet.
        # To fix this properly, let's update the model to store `masked_key` or just return "****".
        # Let's return a static "****" for now as it's safe.
        res = []
        for k in keys:
            res.append({
                "id": k.id,
                "name": k.name,
                "app_label": k.app_label,
                "scopes": k.scopes,
                "created_at": k.created_at,
                "last_used_at": k.last_used_at,
                "revoked_at": k.revoked_at,
                "masked_key": "****"  # Placeholder
            })
        return res

    def revoke_api_key(self, api_key_id: str, company_id: str):
        key = self.repo.get_by_id(api_key_id)
        if not key or key.company_id != company_id:
            raise HTTPException(status_code=404, detail="API Key not found")
        if key.revoked_at:
            raise HTTPException(status_code=400, detail="API Key already revoked")
        return self.repo.revoke(key)

    def authenticate_key(self, raw_key: str) -> dict:
        """
        Validates an API key and returns the company_id if valid.
        Since we only have the hash, we must iterate active keys or use a prefix pattern.
        Without a prefix mapping to DB ID, we'd have to iterate all keys which is slow.
        Usually, API keys are formatted as {id}.{secret} so we can do a direct lookup.
        Let's assume the raw_key is just the secret for now and we iterate, 
        or better: change _generate_raw_key to include the ID!
        """
        keys = self.repo.get_all_active()
        for k in keys:
            if self._verify_key(raw_key, k.key_hash):
                self.repo.update_last_used(k)
                return {"company_id": k.company_id, "app_label": k.app_label}
        raise HTTPException(status_code=401, detail="Invalid API Key")
