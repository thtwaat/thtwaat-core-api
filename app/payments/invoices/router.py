"""
app/payments/invoices/router.py
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.payments.invoices.schema import InvoiceResponse
from app.payments.invoices.service import InvoiceService

router = APIRouter(prefix="/payments/invoices", tags=["Invoices"])


def get_invoice_service(db: Session = Depends(get_db)) -> InvoiceService:
    return InvoiceService(db)


@router.get(
    "/",
    response_model=List[InvoiceResponse],
    summary="List invoices for the current company",
)
def list_invoices(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserProfileResponse = Depends(get_current_user),
    service: InvoiceService = Depends(get_invoice_service)
):
    """Returns paginated invoice history for the authenticated user's company."""
    return service.list_invoices(current_user.company_id, skip=skip, limit=limit)


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get a specific invoice",
)
def get_invoice(
    invoice_id: uuid.UUID,
    current_user: UserProfileResponse = Depends(get_current_user),
    service: InvoiceService = Depends(get_invoice_service)
):
    return service.get_invoice(invoice_id, current_user.company_id)
