from sqlalchemy.orm import Session
from app.webhooks.model import Webhook
from typing import List, Optional

class WebhookRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, webhook_id: str) -> Optional[Webhook]:
        return self.db.query(Webhook).filter(Webhook.id == webhook_id).first()

    def get_by_company(self, company_id: str) -> List[Webhook]:
        return self.db.query(Webhook).filter(Webhook.company_id == company_id).all()

    def get_active_by_company(self, company_id: str) -> List[Webhook]:
        return self.db.query(Webhook).filter(
            Webhook.company_id == company_id, 
            Webhook.is_active == True
        ).all()

    def create(self, data: dict) -> Webhook:
        db_obj = Webhook(**data)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, webhook: Webhook) -> None:
        self.db.delete(webhook)
        self.db.commit()
