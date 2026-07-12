"""
app/notifications/service.py

Business logic for the Notifications module.
"""
import uuid
import logging
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.notifications.schema import SendNotificationRequest
from app.notifications.model import Notification, NotificationStatus
from app.notifications.repository import NotificationRepository
from app.notifications.providers.factory import get_notification_provider

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self, db: Session):
        self.repo = NotificationRepository(db)

    def send_notification(self, payload: SendNotificationRequest, company_id: uuid.UUID, user_id: uuid.UUID) -> Notification:
        # 1. Select provider
        provider = get_notification_provider(payload.channel)
        
        # 2. Basic Template logic (Stub)
        body = payload.body
        if payload.template_name and payload.template_data:
            # A real implementation would parse the template and inject data.
            # Here we just do a naive replacement if we can
            for k, v in payload.template_data.items():
                body = body.replace(f"{{{k}}}", str(v))
        
        # 3. Save initial record
        db_notif = self.repo.create({
            "company_id": company_id,
            "user_id": user_id,
            "channel": payload.channel,
            "recipient": payload.recipient,
            "subject": payload.subject,
            "body": body,
            "template_name": payload.template_name,
            "status": NotificationStatus.PENDING,
            "provider": provider.provider_name
        })

        # 4. Attempt to Send (Synchronous stub)
        try:
            result = provider.send(
                recipient=payload.recipient, 
                subject=payload.subject, 
                body=body
            )
            
            if result.success:
                self.repo.update_status(db_notif.id, NotificationStatus.SENT)
            else:
                self.repo.update_status(db_notif.id, NotificationStatus.FAILED, result.error_message)
                
        except Exception as e:
            logger.error(f"Notification sending failed: {str(e)}")
            self.repo.update_status(db_notif.id, NotificationStatus.FAILED, str(e))
            
        # Refresh to get updated status
        self.repo.db.refresh(db_notif)
        return db_notif

    def get_notification_history(self, company_id: uuid.UUID) -> List[Notification]:
        return self.repo.get_history_by_company(company_id)
        
    def get_notification(self, notification_id: uuid.UUID) -> Notification:
        db_notif = self.repo.get_by_id(notification_id)
        if not db_notif:
            raise HTTPException(status_code=404, detail="Notification not found")
        return db_notif

    def soft_delete_notification(self, notification_id: uuid.UUID) -> None:
        if not self.repo.soft_delete(notification_id):
            raise HTTPException(status_code=404, detail="Notification not found")
