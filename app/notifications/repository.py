"""
app/notifications/repository.py

Database operations for Notifications.
"""
import uuid
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, update

from app.notifications.model import Notification, NotificationStatus


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, notification_data: dict) -> Notification:
        db_notif = Notification(**notification_data)
        self.db.add(db_notif)
        self.db.commit()
        self.db.refresh(db_notif)
        return db_notif

    def get_by_id(self, notification_id: uuid.UUID) -> Optional[Notification]:
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one_or_none()
        
    def get_history_by_company(self, company_id: uuid.UUID) -> List[Notification]:
        stmt = select(Notification).where(
            Notification.company_id == company_id,
            Notification.deleted_at.is_(None)
        ).order_by(Notification.created_at.desc())
        
        return list(self.db.execute(stmt).scalars().all())

    def update_status(self, notification_id: uuid.UUID, status: NotificationStatus, error_message: Optional[str] = None):
        update_data = {"status": status}
        if status == NotificationStatus.SENT:
            update_data["sent_at"] = datetime.now(timezone.utc)
        if status == NotificationStatus.FAILED:
            update_data["error_message"] = error_message
            
        stmt = update(Notification).where(Notification.id == notification_id).values(**update_data)
        self.db.execute(stmt)
        self.db.commit()
        
    def increment_retry(self, notification_id: uuid.UUID):
        stmt = update(Notification).where(Notification.id == notification_id).values(
            retry_count=Notification.retry_count + 1
        )
        self.db.execute(stmt)
        self.db.commit()

    def soft_delete(self, notification_id: uuid.UUID) -> bool:
        db_notif = self.get_by_id(notification_id)
        if db_notif:
            db_notif.deleted_at = datetime.now(timezone.utc)
            self.db.commit()
            return True
        return False
