import secrets
import hmac
import hashlib
import logging
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, BackgroundTasks

from app.webhooks.repository import WebhookRepository
from app.webhooks.schema import WebhookCreate, WebhookUpdate

logger = logging.getLogger(__name__)


class WebhookService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = WebhookRepository(db)

    def _generate_secret(self) -> str:
        return f"whsec_{secrets.token_hex(32)}"

    def _serialize(self, db_obj, *, include_secret: bool = False) -> dict:
        out = {
            "id": db_obj.id,
            "url": db_obj.url,
            "event_types": db_obj.event_types or [],
            "is_active": db_obj.is_active,
            "created_at": db_obj.created_at,
        }
        if include_secret:
            out["secret"] = db_obj.secret
        return out

    def create_webhook(self, company_id: str, data: WebhookCreate) -> dict:
        from app.webhooks.url_safety import UnsafeWebhookUrlError, assert_safe_webhook_url

        try:
            safe_url = assert_safe_webhook_url(data.url)
        except UnsafeWebhookUrlError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        secret = self._generate_secret()
        events = data.event_types or ["*"]
        db_obj = self.repo.create(
            {
                "company_id": company_id,
                "url": safe_url,
                "event_types": events,
                "secret": secret,
                "is_active": True,
            }
        )
        return self._serialize(db_obj, include_secret=True)

    def list_webhooks(self, company_id: str) -> list:
        hooks = self.repo.get_by_company(company_id)
        return [self._serialize(h) for h in hooks]

    def get_webhook(self, webhook_id: str, company_id: str) -> dict:
        webhook = self.repo.get_by_id(webhook_id)
        if not webhook or str(webhook.company_id) != str(company_id):
            raise HTTPException(status_code=404, detail="Webhook not found")
        return self._serialize(webhook)

    def update_webhook(self, webhook_id: str, company_id: str, data: WebhookUpdate) -> dict:
        webhook = self.repo.get_by_id(webhook_id)
        if not webhook or str(webhook.company_id) != str(company_id):
            raise HTTPException(status_code=404, detail="Webhook not found")

        patch: dict = {}
        if data.url is not None:
            from app.webhooks.url_safety import UnsafeWebhookUrlError, assert_safe_webhook_url

            try:
                patch["url"] = assert_safe_webhook_url(data.url)
            except UnsafeWebhookUrlError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        if data.event_types is not None:
            patch["event_types"] = data.event_types or ["*"]
        if data.is_active is not None:
            patch["is_active"] = bool(data.is_active)

        if not patch:
            return self._serialize(webhook)
        updated = self.repo.update(webhook, patch)
        return self._serialize(updated)

    def set_active(self, webhook_id: str, company_id: str, is_active: bool) -> dict:
        return self.update_webhook(
            webhook_id, company_id, WebhookUpdate(is_active=is_active)
        )

    def reveal_secret(self, webhook_id: str, company_id: str) -> dict:
        webhook = self.repo.get_by_id(webhook_id)
        if not webhook or str(webhook.company_id) != str(company_id):
            raise HTTPException(status_code=404, detail="Webhook not found")
        return {"id": webhook.id, "secret": webhook.secret}

    def delete_webhook(self, webhook_id: str, company_id: str):
        webhook = self.repo.get_by_id(webhook_id)
        if not webhook or str(webhook.company_id) != str(company_id):
            raise HTTPException(status_code=404, detail="Webhook not found")
        self.repo.delete(webhook)

    def _sign_payload(self, payload_str: str, secret: str) -> str:
        h = hmac.new(secret.encode("utf-8"), payload_str.encode("utf-8"), hashlib.sha256)
        return f"sha256={h.hexdigest()}"

    def _dispatch_worker(self, url: str, payload: dict, secret: str):
        """Sync dispatch used by BackgroundTasks / legacy callers."""
        from app.webhooks.delivery import WebhookDeliveryError, deliver_webhook

        try:
            deliver_webhook(url, payload, secret)
        except WebhookDeliveryError as exc:
            logger.warning("webhook dispatch failed for %s: %s", url, exc)

    def dispatch_event(
        self, company_id: str, event_type: str, payload: dict, background_tasks: BackgroundTasks
    ):
        webhooks = self.repo.get_active_by_company(company_id)
        full_payload = {"event": event_type, "data": payload}
        for wh in webhooks:
            if "*" in (wh.event_types or []) or event_type in (wh.event_types or []):
                background_tasks.add_task(self._dispatch_worker, wh.url, full_payload, wh.secret)

    def test_webhook(
        self, webhook_id: str, company_id: str, background_tasks: BackgroundTasks
    ):
        webhook = self.repo.get_by_id(webhook_id)
        if not webhook or str(webhook.company_id) != str(company_id):
            raise HTTPException(status_code=404, detail="Webhook not found")
        if not webhook.is_active:
            raise HTTPException(status_code=400, detail="Webhook is disabled")

        # Prefer Redis worker path when available so deliveries appear in outbox history
        try:
            from app.openai_compat.notify import enqueue_webhook_dispatch

            result = enqueue_webhook_dispatch(
                company_id=company_id,
                webhook_id=str(webhook.id),
                url=webhook.url,
                secret=webhook.secret,
                event="ping",
                data={"message": "This is a test webhook from THTWAAT"},
                db=self.db,
            )
            if result and result.get("enqueued"):
                return {
                    "status": "success",
                    "message": "Test payload enqueued",
                    "delivery_id": result.get("delivery_id"),
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("webhook test enqueue failed, falling back: %s", exc)

        payload = {"message": "This is a test webhook from THTWAAT"}
        background_tasks.add_task(
            self._dispatch_worker,
            webhook.url,
            {"event": "ping", "data": payload},
            webhook.secret,
        )
        return {"status": "success", "message": "Test payload dispatched"}

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
    ) -> dict:
        rows, total = self.repo.list_deliveries(
            company_id,
            webhook_id=webhook_id,
            status=status,
            event=event,
            q=q,
            limit=limit,
            offset=offset,
        )
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "results": [
                {
                    "id": r.id,
                    "delivery_id": r.delivery_id,
                    "webhook_id": r.webhook_id,
                    "event": r.event,
                    "url": r.url,
                    "status": r.status,
                    "attempts": r.attempts,
                    "last_error": r.last_error,
                    "next_attempt_at": r.next_attempt_at,
                    "delivered_at": r.delivered_at,
                    "created_at": getattr(r, "created_at", None),
                    "updated_at": getattr(r, "updated_at", None),
                }
                for r in rows
            ],
        }

    def retry_delivery(self, delivery_id: str, company_id: str) -> dict:
        from app.monitoring.queue import enqueue
        from app.webhooks.model import (
            WEBHOOK_DELIVERY_DEAD,
            WEBHOOK_DELIVERY_FAILED,
            WEBHOOK_DELIVERY_PENDING,
            Webhook,
        )
        from app.webhooks.outbox import JOB_TYPE_WEBHOOK_DISPATCH, mark_delivery_queued

        row = self.repo.get_delivery_by_id(delivery_id, company_id=company_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Delivery not found")
        if row.status not in {
            WEBHOOK_DELIVERY_FAILED,
            WEBHOOK_DELIVERY_DEAD,
            WEBHOOK_DELIVERY_PENDING,
        }:
            raise HTTPException(
                status_code=400,
                detail=f"Delivery status '{row.status}' cannot be retried",
            )

        secret = ""
        url = row.url
        if row.webhook_id is not None:
            wh = self.db.query(Webhook).filter(Webhook.id == row.webhook_id).first()
            if wh is None or not wh.is_active:
                raise HTTPException(
                    status_code=400,
                    detail="Delivery cannot be retried (webhook missing or inactive)",
                )
            secret = wh.secret or ""
            url = wh.url or row.url

        data = {}
        if isinstance(row.payload, dict):
            data = row.payload.get("data") or {}
        attempt = int(row.attempts or 0) + 1
        job = {
            "type": JOB_TYPE_WEBHOOK_DISPATCH,
            "company_id": str(row.company_id),
            "webhook_id": str(row.webhook_id) if row.webhook_id else None,
            "url": url,
            "secret": secret,
            "event": row.event,
            "data": data,
            "delivery_id": row.delivery_id,
            "attempt": attempt,
            "manual_retry": True,
        }
        result = enqueue(job)
        if not result or not result.get("enqueued"):
            raise HTTPException(status_code=503, detail="Failed to enqueue retry")
        mark_delivery_queued(self.db, row.delivery_id)
        return {
            "status": "success",
            "message": "Delivery retry enqueued",
            "delivery_id": row.delivery_id,
        }
