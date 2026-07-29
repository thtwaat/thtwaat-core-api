"""
app/notifications/service.py

Business logic for the Notifications module.
Supports both external channel sending and in-app notifications.
"""
import uuid
import logging
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.notifications.schema import SendNotificationRequest, InboxResponse
from app.notifications.model import Notification, NotificationStatus, NotificationChannel
from app.notifications.repository import NotificationRepository
from app.notifications.providers.factory import get_notification_provider

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, db: Session):
        self.repo = NotificationRepository(db)

    def send_notification(self, payload: SendNotificationRequest, company_id: uuid.UUID, user_id: uuid.UUID) -> Notification:
        provider = get_notification_provider(payload.channel)

        body = payload.body
        if payload.template_name and payload.template_data:
            for k, v in payload.template_data.items():
                body = body.replace(f"{{{k}}}", str(v))

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

        try:
            result = provider.send(recipient=payload.recipient, subject=payload.subject, body=body)
            if result.success:
                self.repo.update_status(db_notif.id, NotificationStatus.SENT)
            else:
                self.repo.update_status(db_notif.id, NotificationStatus.FAILED, result.error_message)
        except Exception as e:
            logger.error(f"Notification sending failed: {str(e)}")
            self.repo.update_status(db_notif.id, NotificationStatus.FAILED, str(e))

        self.repo.db.refresh(db_notif)
        return db_notif

    def create_in_app_notification(
        self,
        event_type: str,
        company_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        title: str,
        body: str,
        extra_data: Optional[dict] = None,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Notification:
        """Creates an in-app notification record directly (no external provider call)."""
        notif = self.repo.create({
            "company_id": company_id,
            "user_id": user_id,
            "actor_id": actor_id,
            "channel": NotificationChannel.IN_APP,
            "recipient": str(user_id) if user_id else str(company_id),
            "subject": title,
            "body": body,
            "event_type": event_type,
            "extra_data": extra_data,
            "status": NotificationStatus.SENT,
            "provider": "in_app",
            "sent_at": datetime.now(timezone.utc),
        })
        return notif

    def get_inbox(
        self,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50
    ) -> List[InboxResponse]:
        """Returns in-app inbox for the current user."""
        items = self.repo.get_inbox(
            company_id=company_id,
            user_id=user_id,
            unread_only=unread_only,
            skip=skip,
            limit=limit
        )
        return [InboxResponse.from_notification(n) for n in items]

    def mark_read(self, notification_id: uuid.UUID, company_id: uuid.UUID) -> dict:
        """Marks a single notification as read, ensuring ownership."""
        notif = self.repo.get_by_id(notification_id)
        if not notif or notif.company_id != company_id:
            raise HTTPException(status_code=404, detail="Notification not found.")
        if notif.channel != NotificationChannel.IN_APP:
            raise HTTPException(status_code=400, detail="Only in-app notifications can be marked as read.")
        self.repo.mark_read(notification_id)
        return {"detail": "Notification marked as read."}

    def mark_all_read(self, company_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        """Marks all unread in-app notifications for the user as read."""
        count = self.repo.mark_all_read(company_id=company_id, user_id=user_id)
        return {"detail": f"{count} notification(s) marked as read."}

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
