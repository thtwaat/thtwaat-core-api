"""
app/notifications/router.py

FastAPI router for Notifications operations.
Includes both external send and in-app inbox endpoints.
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.notifications.schema import (
    SendNotificationRequest, NotificationResponse, InboxResponse, MarkReadRequest
)
from app.notifications.service import NotificationService

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


def get_notification_service(db: Session = Depends(get_db)) -> NotificationService:
    return NotificationService(db)


# ─── External Send ────────────────────────────────────────────────────────

@router.post(
    "/send",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a notification via external channel (email/SMS/push/WhatsApp)",
)
def send_notification(
    payload: SendNotificationRequest,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service)
):
    """Sends a notification via the specified channel provider."""
    return service.send_notification(payload, current_user.company_id, current_user.id)


@router.get(
    "/history",
    response_model=List[NotificationResponse],
    summary="Get full notification history for the company",
)
def get_notification_history(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service)
):
    """Returns all notification records for the current user's company."""
    return service.get_notification_history(current_user.company_id)


# ─── In-App Inbox ───────────────────────────────────────────────────────

@router.get(
    "/inbox",
    response_model=List[InboxResponse],
    summary="Get in-app notification inbox",
)
def get_inbox(
    unread_only: bool = Query(False, description="If true, returns only unread notifications"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserProfileResponse = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service)
):
    """
    Returns in-app inbox notifications for the authenticated user.
    Shows both user-targeted and broadcast company notifications.
    """
    return service.get_inbox(
        company_id=current_user.company_id,
        user_id=current_user.id,
        unread_only=unread_only,
        skip=skip,
        limit=limit
    )


@router.patch(
    "/{notification_id}/read",
    summary="Mark a notification as read",
)
def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service)
):
    """Marks a specific in-app notification as read."""
    return service.mark_read(notification_id, current_user.company_id)


@router.post(
    "/mark-all-read",
    summary="Mark all in-app notifications as read",
)
def mark_all_read(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service)
):
    """Marks all unread in-app notifications for the current user as read."""
    return service.mark_all_read(
        company_id=current_user.company_id,
        user_id=current_user.id
    )


# ─── Get/Delete specific ──────────────────────────────────────────────────

@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
    summary="Get notification details",
)
def get_notification(
    notification_id: uuid.UUID,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service)
):
    """Retrieves details for a specific notification."""
    db_notif = service.get_notification(notification_id)
    if db_notif.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this notification")
    return db_notif


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a notification",
)
def delete_notification(
    notification_id: uuid.UUID,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service)
):
    """Soft-deletes a notification record."""
    db_notif = service.get_notification(notification_id)
    if db_notif.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this notification")
    service.soft_delete_notification(notification_id)
