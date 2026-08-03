from sqlalchemy.orm import Session
from app.webhooks.model import Webhook, WebhookDelivery
from typing import List, Optional


class WebhookRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, webhook_id: str) -> Optional[Webhook]:
        return self.db.query(Webhook).filter(Webhook.id == webhook_id).first()

    def get_by_company(self, company_id: str) -> List[Webhook]:
        return (
            self.db.query(Webhook)
            .filter(Webhook.company_id == company_id)
            .order_by(Webhook.created_at.desc())
            .all()
        )

    def get_active_by_company(self, company_id: str) -> List[Webhook]:
        return self.db.query(Webhook).filter(
            Webhook.company_id == company_id,
            Webhook.is_active == True,  # noqa: E712
        ).all()

    def create(self, data: dict) -> Webhook:
        db_obj = Webhook(**data)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(self, webhook: Webhook, data: dict) -> Webhook:
        for key, value in data.items():
            setattr(webhook, key, value)
        self.db.commit()
        self.db.refresh(webhook)
        return webhook

    def delete(self, webhook: Webhook) -> None:
        self.db.delete(webhook)
        self.db.commit()

    def get_delivery_by_id(
        self, delivery_id: str, *, company_id: str
    ) -> Optional[WebhookDelivery]:
        return (
            self.db.query(WebhookDelivery)
            .filter(
                WebhookDelivery.delivery_id == delivery_id,
                WebhookDelivery.company_id == company_id,
            )
            .first()
        )

    def list_deliveries(
        self,
        company_id: str,
        *,
        webhook_id: Optional[str] = None,
        status: Optional[str] = None,
        event: Optional[str] = None,
        q: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[List[WebhookDelivery], int]:
        query = self.db.query(WebhookDelivery).filter(
            WebhookDelivery.company_id == company_id
        )
        if webhook_id:
            query = query.filter(WebhookDelivery.webhook_id == webhook_id)
        if status:
            query = query.filter(WebhookDelivery.status == status)
        if event:
            query = query.filter(WebhookDelivery.event == event)
        if q:
            like = f"%{q.strip()}%"
            query = query.filter(
                (WebhookDelivery.delivery_id.ilike(like))
                | (WebhookDelivery.url.ilike(like))
                | (WebhookDelivery.event.ilike(like))
                | (WebhookDelivery.last_error.ilike(like))
            )
        total = query.count()
        rows = (
            query.order_by(WebhookDelivery.created_at.desc())
            .offset(max(0, offset))
            .limit(max(1, min(limit, 100)))
            .all()
        )
        return rows, total
