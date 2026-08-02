"""
app/payments/router.py

FastAPI router for Payments operations.
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.payments.schema import PaymentCreate, PaymentUpdateStatus, PaymentResponse
from app.payments.model import PaymentStatus, Gateway
from app.payments.service import PaymentService

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
)

def get_payment_service(db: Session = Depends(get_db)) -> PaymentService:
    return PaymentService(db)

@router.post(
    "/",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new payment",
)
def create_payment(
    payload: PaymentCreate,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service)
):
    """
    Creates and processes a new payment via the selected gateway.
    """
    return service.create_payment(payload, current_user.company_id, current_user.id)

@router.get(
    "/",
    response_model=List[PaymentResponse],
    summary="List payments",
)
def list_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[PaymentStatus] = Query(None, alias="status"),
    gateway_filter: Optional[Gateway] = Query(None, alias="gateway"),
    current_user: UserProfileResponse = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service)
):
    """
    Returns a paginated list of payments for the authenticated user's company.
    Supports filtering by status and gateway.
    """
    return service.list_payments(
        company_id=current_user.company_id,
        skip=skip,
        limit=limit,
        status_filter=status_filter,
        gateway_filter=gateway_filter
    )

# Use the `:uuid` path converter so static siblings like /payments/plans are not
# captured by this dynamic segment (string `{payment_id}` would match first and 422).
@router.get(
    "/{payment_id:uuid}",
    response_model=PaymentResponse,
    summary="Get payment details",
)
def get_payment(
    payment_id: uuid.UUID,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service)
):
    """
    Retrieves details for a specific payment.
    """
    return service.get_payment(payment_id, current_user.company_id)

@router.patch(
    "/{payment_id:uuid}/status",
    response_model=PaymentResponse,
    summary="Update payment status",
)
def update_payment_status(
    payment_id: uuid.UUID,
    payload: PaymentUpdateStatus,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service)
):
    """
    Manually updates the status of a payment (e.g., via webhook callbacks).
    """
    return service.update_payment_status(payment_id, payload, current_user.company_id)

@router.post(
    "/{payment_id:uuid}/refund",
    response_model=PaymentResponse,
    summary="Refund a payment",
)
def refund_payment(
    payment_id: uuid.UUID,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service)
):
    """
    Initiates a refund for a successful payment via the original gateway.
    """
    return service.refund_payment(payment_id, current_user.company_id)

@router.delete(
    "/{payment_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a payment",
)
def delete_payment(
    payment_id: uuid.UUID,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service)
):
    """
    Soft-deletes a payment record.
    """
    service.soft_delete_payment(payment_id, current_user.company_id)
