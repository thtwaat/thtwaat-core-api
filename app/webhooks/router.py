from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.webhooks.schema import WebhookCreate, WebhookResponse, WebhookGenerateResponse
from app.webhooks.service import WebhookService
from app.auth.router import get_current_user
from typing import List

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

@router.post("", response_model=WebhookGenerateResponse)
def register_webhook(
    data: WebhookCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    service = WebhookService(db)
    if not hasattr(current_user, "company_id") or not current_user.company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")
    return service.create_webhook(current_user.company_id, data)

@router.get("", response_model=List[WebhookResponse])
def list_webhooks(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    service = WebhookService(db)
    if not hasattr(current_user, "company_id") or not current_user.company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")
    return service.list_webhooks(current_user.company_id)

@router.delete("/{webhook_id}")
def delete_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    service = WebhookService(db)
    if not hasattr(current_user, "company_id") or not current_user.company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")
    service.delete_webhook(webhook_id, current_user.company_id)
    return {"status": "success", "message": "Webhook deleted"}

@router.post("/{webhook_id}/test")
def test_webhook(
    webhook_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    service = WebhookService(db)
    if not hasattr(current_user, "company_id") or not current_user.company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")
    return service.test_webhook(webhook_id, current_user.company_id, background_tasks)
