from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.auth.router import get_current_user
from app.database.database import get_db
from app.webhooks.schema import (
    WebhookCreate,
    WebhookDeliveryListResponse,
    WebhookGenerateResponse,
    WebhookResponse,
    WebhookUpdate,
)
from app.webhooks.service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def _company_id(current_user) -> str:
    if not hasattr(current_user, "company_id") or not current_user.company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")
    return str(current_user.company_id)


@router.post("", response_model=WebhookGenerateResponse)
def register_webhook(
    data: WebhookCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return WebhookService(db).create_webhook(_company_id(current_user), data)


@router.get("", response_model=List[WebhookResponse])
def list_webhooks(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return WebhookService(db).list_webhooks(_company_id(current_user))


@router.get("/deliveries", response_model=WebhookDeliveryListResponse)
def list_deliveries(
    webhook_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    event: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return WebhookService(db).list_deliveries(
        _company_id(current_user),
        webhook_id=webhook_id,
        status=status,
        event=event,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.post("/deliveries/{delivery_id}/retry")
def retry_delivery(
    delivery_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return WebhookService(db).retry_delivery(delivery_id, _company_id(current_user))


@router.get("/{webhook_id}", response_model=WebhookResponse)
def get_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return WebhookService(db).get_webhook(webhook_id, _company_id(current_user))


@router.patch("/{webhook_id}", response_model=WebhookResponse)
def update_webhook(
    webhook_id: str,
    data: WebhookUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return WebhookService(db).update_webhook(webhook_id, _company_id(current_user), data)


@router.post("/{webhook_id}/enable", response_model=WebhookResponse)
def enable_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return WebhookService(db).set_active(webhook_id, _company_id(current_user), True)


@router.post("/{webhook_id}/disable", response_model=WebhookResponse)
def disable_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return WebhookService(db).set_active(webhook_id, _company_id(current_user), False)


@router.get("/{webhook_id}/secret")
def reveal_secret(
    webhook_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return WebhookService(db).reveal_secret(webhook_id, _company_id(current_user))


@router.delete("/{webhook_id}")
def delete_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    WebhookService(db).delete_webhook(webhook_id, _company_id(current_user))
    return {"status": "success", "message": "Webhook deleted"}


@router.post("/{webhook_id}/test")
def test_webhook(
    webhook_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return WebhookService(db).test_webhook(
        webhook_id, _company_id(current_user), background_tasks
    )
