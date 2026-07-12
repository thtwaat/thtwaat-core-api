"""
app/payments/repository.py

Database operations for Payments.
"""
import uuid
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, update, func

from app.payments.model import Payment, PaymentStatus, Gateway


class PaymentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> Payment:
        db_payment = Payment(**data)
        self.db.add(db_payment)
        self.db.commit()
        self.db.refresh(db_payment)
        return db_payment

    def get_by_id(self, payment_id: uuid.UUID) -> Optional[Payment]:
        stmt = select(Payment).where(
            Payment.id == payment_id,
            Payment.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_payments(
        self, 
        company_id: uuid.UUID,
        skip: int = 0, 
        limit: int = 100, 
        status: Optional[PaymentStatus] = None,
        gateway: Optional[Gateway] = None
    ) -> List[Payment]:
        stmt = select(Payment).where(
            Payment.company_id == company_id,
            Payment.deleted_at.is_(None)
        )
        
        if status:
            stmt = stmt.where(Payment.status == status)
        if gateway:
            stmt = stmt.where(Payment.gateway == gateway)
            
        stmt = stmt.order_by(Payment.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def update_status(self, payment_id: uuid.UUID, status: PaymentStatus, transaction_id: Optional[str] = None, payment_metadata: Optional[dict] = None) -> None:
        update_data = {"status": status}
        if status == PaymentStatus.SUCCESS:
            update_data["paid_at"] = datetime.now(timezone.utc)
        if transaction_id:
            update_data["gateway_transaction_id"] = transaction_id
        if payment_metadata is not None:
            # We merge new metadata with existing if desired, but for simplicity we'll overwrite or just set it
            update_data["payment_metadata"] = payment_metadata
            
        stmt = update(Payment).where(Payment.id == payment_id).values(**update_data)
        self.db.execute(stmt)
        self.db.commit()

    def soft_delete(self, payment_id: uuid.UUID) -> bool:
        db_payment = self.get_by_id(payment_id)
        if db_payment:
            db_payment.deleted_at = datetime.now(timezone.utc)
            self.db.commit()
            return True
        return False
