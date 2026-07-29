"""
app/notifications/repository.py

Database access for Notifications.
"""
import uuid
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, update

from app.notifications.model import Notification, NotificationStatus, NotificationChannel


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> Notification:
        notif = Notification(**data)
        self.db.add(notif)
        self.db.commit()
        self.db.refresh(notif)
        return notif

    def get_by_id(self, notification_id: uuid.UUID) -> Optional[Notification]:
        return self.db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.deleted_at.is_(None)
            )
        ).scalar_one_or_none()

    def get_history_by_company(self, company_id: uuid.UUID) -> List[Notification]:
        return list(self.db.execute(
            select(Notification)
            .where(
                Notification.company_id == company_id,
                Notification.deleted_at.is_(None)
            )
            .order_by(Notification.created_at.desc())
        ).scalars().all())

    def get_inbox(
        self,
        company_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50
    ) -> List[Notification]:
        """Get IN_APP notifications for a company, optionally filtering by user."""
        stmt = select(Notification).where(
            Notification.channel == NotificationChannel.IN_APP,
            Notification.company_id == company_id,
            Notification.deleted_at.is_(None)
        )
        if user_id:
            # Show notifications targeted at this user OR broadcast (user_id is None)
            stmt = stmt.where(
                (Notification.user_id == user_id) | Notification.user_id.is_(None)
            )
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        stmt = stmt.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def mark_read(self, notification_id: uuid.UUID) -> bool:
        """Mark a single notification as read."""
        now = datetime.now(timezone.utc)
        result = self.db.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.read_at.is_(None),
                Notification.deleted_at.is_(None)
            )
            .values(read_at=now, status=NotificationStatus.READ)
        )
        self.db.commit()
        return result.rowcount > 0

    def mark_all_read(self, company_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> int:
        """Mark all unread IN_APP notifications as read for a company/user."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(Notification)
            .where(
                Notification.channel == NotificationChannel.IN_APP,
                Notification.company_id == company_id,
                Notification.read_at.is_(None),
                Notification.deleted_at.is_(None)
            )
        )
        if user_id:
            stmt = stmt.where(
                (Notification.user_id == user_id) | Notification.user_id.is_(None)
            )
        result = self.db.execute(stmt.values(read_at=now, status=NotificationStatus.READ))
        self.db.commit()
        return result.rowcount

    def update_status(
        self,
        notification_id: uuid.UUID,
        status: NotificationStatus,
        error_message: Optional[str] = None
    ) -> None:
        update_vals = {"status": status}
        if status == NotificationStatus.SENT:
            update_vals["sent_at"] = datetime.now(timezone.utc)
        if error_message:
            update_vals["error_message"] = error_message
        self.db.execute(
            update(Notification).where(Notification.id == notification_id).values(**update_vals)
        )
        self.db.commit()

    def soft_delete(self, notification_id: uuid.UUID) -> bool:
        notif = self.get_by_id(notification_id)
        if notif:
            notif.deleted_at = datetime.now(timezone.utc)
            self.db.commit()
            return True
        return False
