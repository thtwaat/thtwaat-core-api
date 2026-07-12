"""
app/notifications/router.py

FastAPI router for Notifications operations.
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.notifications.schema import SendNotificationRequest, NotificationResponse
from app.notifications.service import NotificationService

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)

def get_notification_service(db: Session = Depends(get_db)) -> NotificationService:
    return NotificationService(db)

@router.post(
    "/send",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a notification",
)
def send_notification(
    payload: SendNotificationRequest,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service)
):
    """
    Sends a notification (Email, SMS, WhatsApp, Push). 
    If a template is provided, naive text replacement is applied.
    """
    return service.send_notification(payload, current_user.company_id, current_user.id)


@router.get(
    "/history",
    response_model=List[NotificationResponse],
    summary="Get notification history",
)
def get_notification_history(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service)
):
    """
    Retrieves the notification history for the current user's company.
    """
    return service.get_notification_history(current_user.company_id)


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
    """
    Retrieves details for a specific notification.
    """
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
    """
    Soft-deletes a notification record.
    """
    db_notif = service.get_notification(notification_id)
    if db_notif.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this notification")
        
    service.soft_delete_notification(notification_id)
