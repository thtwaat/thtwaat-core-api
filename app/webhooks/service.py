import secrets
import hmac
import hashlib
import json
from sqlalchemy.orm import Session
from fastapi import HTTPException, BackgroundTasks
from app.webhooks.repository import WebhookRepository
from app.webhooks.schema import WebhookCreate

class WebhookService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = WebhookRepository(db)

    def _generate_secret(self) -> str:
        return f"whsec_{secrets.token_hex(32)}"

    def create_webhook(self, company_id: str, data: WebhookCreate) -> dict:
        secret = self._generate_secret()
        db_obj = self.repo.create({
            "company_id": company_id,
            "url": data.url,
            "event_types": data.event_types,
            "secret": secret
        })
        return {
            "id": db_obj.id,
            "url": db_obj.url,
            "event_types": db_obj.event_types,
            "is_active": db_obj.is_active,
            "created_at": db_obj.created_at,
            "secret": secret
        }

    def list_webhooks(self, company_id: str) -> list:
        hooks = self.repo.get_by_company(company_id)
        return [{
            "id": h.id,
            "url": h.url,
            "event_types": h.event_types,
            "is_active": h.is_active,
            "created_at": h.created_at
        } for h in hooks]

    def delete_webhook(self, webhook_id: str, company_id: str):
        webhook = self.repo.get_by_id(webhook_id)
        if not webhook or webhook.company_id != company_id:
            raise HTTPException(status_code=404, detail="Webhook not found")
        self.repo.delete(webhook)

    def _sign_payload(self, payload_str: str, secret: str) -> str:
        # Create HMAC signature
        h = hmac.new(secret.encode('utf-8'), payload_str.encode('utf-8'), hashlib.sha256)
        return f"sha256={h.hexdigest()}"

    def _dispatch_worker(self, url: str, payload: dict, secret: str):
        """Sync dispatch used by BackgroundTasks / legacy callers."""
        from app.webhooks.delivery import WebhookDeliveryError, deliver_webhook

        try:
            deliver_webhook(url, payload, secret)
        except WebhookDeliveryError as exc:
            # Legacy path: log only (Week 3 worker path raises for retries).
            logger = __import__("logging").getLogger(__name__)
            logger.warning("webhook dispatch failed for %s: %s", url, exc)

    def dispatch_event(self, company_id: str, event_type: str, payload: dict, background_tasks: BackgroundTasks):
        """
        Dispatches an event to all active webhooks for a company that subscribe to this event_type.
        """
        webhooks = self.repo.get_active_by_company(company_id)
        
        full_payload = {
            "event": event_type,
            "data": payload
        }
        
        for wh in webhooks:
            # If event_types is empty, maybe it listens to all, or we check explicit subscription
            if "*" in wh.event_types or event_type in wh.event_types:
                background_tasks.add_task(self._dispatch_worker, wh.url, full_payload, wh.secret)

    def test_webhook(self, webhook_id: str, company_id: str, background_tasks: BackgroundTasks):
        webhook = self.repo.get_by_id(webhook_id)
        if not webhook or webhook.company_id != company_id:
            raise HTTPException(status_code=404, detail="Webhook not found")
        
        payload = {"message": "This is a test webhook from THTWAAT"}
        self.dispatch_event(company_id, "ping", payload, background_tasks)
        return {"status": "success", "message": "Test payload dispatched"}
