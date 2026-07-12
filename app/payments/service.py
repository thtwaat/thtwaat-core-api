"""
app/payments/service.py

Business logic for the Payments module.
"""
import uuid
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.payments.schema import PaymentCreate, PaymentUpdateStatus
from app.payments.model import Payment, PaymentStatus, Gateway
from app.payments.repository import PaymentRepository
from app.payments.providers.factory import get_payment_provider

logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self, db: Session):
        self.repo = PaymentRepository(db)

    def create_payment(self, payload: PaymentCreate, company_id: uuid.UUID, user_id: uuid.UUID) -> Payment:
        # 1. Resolve Provider
        provider = get_payment_provider(payload.gateway)
        
        # 2. Save Initial Record (PENDING)
        db_payment = self.repo.create({
            "company_id": company_id,
            "user_id": user_id,
            "app_id": payload.app_id,
            "amount": payload.amount,
            "currency": payload.currency,
            "payment_method": payload.payment_method,
            "gateway": payload.gateway,
            "invoice_number": payload.invoice_number,
            "status": PaymentStatus.PENDING,
            "payment_metadata": payload.payment_metadata
        })

        # 3. Process with Gateway Stub
        try:
            result = provider.process_payment(
                amount=float(payload.amount),
                currency=payload.currency,
                method=payload.payment_method.value,
                metadata=payload.payment_metadata
            )
            
            final_status = PaymentStatus.SUCCESS if result.success else PaymentStatus.FAILED
            
            # Combine incoming metadata with provider returned data
            merged_metadata = dict(payload.payment_metadata or {})
            if result.provider_data:
                merged_metadata.update(result.provider_data)
            if result.error_message:
                merged_metadata["error"] = result.error_message

            self.repo.update_status(
                payment_id=db_payment.id, 
                status=final_status, 
                transaction_id=result.transaction_id,
                payment_metadata=merged_metadata
            )
            
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            self.repo.update_status(
                payment_id=db_payment.id, 
                status=PaymentStatus.FAILED,
                payment_metadata={"error": str(e)}
            )
            
        # Refresh and return
        self.repo.db.refresh(db_payment)
        return db_payment

    def get_payment(self, payment_id: uuid.UUID, company_id: uuid.UUID) -> Payment:
        db_payment = self.repo.get_by_id(payment_id)
        if not db_payment or db_payment.company_id != company_id:
            raise HTTPException(status_code=404, detail="Payment not found")
        return db_payment

    def list_payments(
        self, 
        company_id: uuid.UUID, 
        skip: int = 0, 
        limit: int = 100, 
        status_filter: Optional[PaymentStatus] = None,
        gateway_filter: Optional[Gateway] = None
    ) -> List[Payment]:
        return self.repo.get_payments(company_id, skip, limit, status_filter, gateway_filter)

    def refund_payment(self, payment_id: uuid.UUID, company_id: uuid.UUID) -> Payment:
        db_payment = self.get_payment(payment_id, company_id)
        
        if db_payment.status != PaymentStatus.SUCCESS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only successful payments can be refunded."
            )
            
        if not db_payment.gateway_transaction_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot refund a payment without a gateway transaction ID."
            )
            
        provider = get_payment_provider(db_payment.gateway)
        
        try:
            result = provider.refund_payment(db_payment.gateway_transaction_id, float(db_payment.amount))
            
            if result.success:
                merged_metadata = dict(db_payment.payment_metadata or {})
                if result.provider_data:
                    merged_metadata.update(result.provider_data)
                
                self.repo.update_status(
                    payment_id=db_payment.id,
                    status=PaymentStatus.REFUNDED,
                    payment_metadata=merged_metadata
                )
            else:
                raise HTTPException(status_code=400, detail=f"Refund failed: {result.error_message}")
                
        except Exception as e:
            logger.error(f"Refund failed: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
            
        self.repo.db.refresh(db_payment)
        return db_payment

    def update_payment_status(self, payment_id: uuid.UUID, payload: PaymentUpdateStatus, company_id: uuid.UUID) -> Payment:
        db_payment = self.get_payment(payment_id, company_id)
        
        self.repo.update_status(
            payment_id=db_payment.id,
            status=payload.status,
            transaction_id=payload.gateway_transaction_id,
            payment_metadata=payload.payment_metadata
        )
        self.repo.db.refresh(db_payment)
        return db_payment

    def soft_delete_payment(self, payment_id: uuid.UUID, company_id: uuid.UUID) -> None:
        # Ensures ownership check happens first
        self.get_payment(payment_id, company_id)
        self.repo.soft_delete(payment_id)
