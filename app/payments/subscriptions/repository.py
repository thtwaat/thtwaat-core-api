"""
app/payments/subscriptions/repository.py
"""
import uuid
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from app.payments.subscriptions.model import Subscription, SubscriptionStatus, SubscriptionProvider

# PG enum labels are lowercase values (active), not names (ACTIVE).
_ACTIVE_STATUSES = (
    SubscriptionStatus.ACTIVE.value,
    SubscriptionStatus.TRIALING.value,
    SubscriptionStatus.PAST_DUE.value,
)


class SubscriptionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> Subscription:
        sub = Subscription(**data)
        self.db.add(sub)
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def get_by_id(self, sub_id: uuid.UUID) -> Optional[Subscription]:
        return self.db.execute(
            select(Subscription).where(Subscription.id == sub_id)
        ).scalar_one_or_none()

    def get_active_by_company(self, company_id: uuid.UUID) -> Optional[Subscription]:
        """Returns the newest active/trialing/past_due subscription for a company.

        Uses ``.first()`` (not ``scalar_one_or_none``) so duplicate active rows
        never raise MultipleResultsFound → HTTP 500 on GET /subscriptions/me.
        """
        return (
            self.db.execute(
                select(Subscription)
                .where(
                    Subscription.company_id == company_id,
                    Subscription.status.in_(_ACTIVE_STATUSES),
                )
                .order_by(Subscription.created_at.desc())
            )
            .scalars()
            .first()
        )

    def get_by_provider_subscription_id(self, provider_sub_id: str) -> Optional[Subscription]:
        return self.db.execute(
            select(Subscription).where(Subscription.provider_subscription_id == provider_sub_id)
        ).scalar_one_or_none()

    def get_by_provider_customer_id(self, customer_id: str) -> Optional[Subscription]:
        return self.db.execute(
            select(Subscription).where(Subscription.provider_customer_id == customer_id)
        ).scalar_one_or_none()

    def get_by_payment_id(self, payment_id: str) -> Optional[Subscription]:
        """Lookup by Razorpay order id (stored on create) or payment id (after verify)."""
        return self.db.execute(
            select(Subscription).where(Subscription.payment_id == payment_id)
        ).scalar_one_or_none()

    def get_incomplete_by_company(
        self,
        company_id: uuid.UUID,
        provider: Optional[SubscriptionProvider] = None,
    ) -> Optional[Subscription]:
        stmt = select(Subscription).where(
            Subscription.company_id == company_id,
            Subscription.status == SubscriptionStatus.INCOMPLETE.value,
        )
        if provider is not None:
            stmt = stmt.where(Subscription.provider == provider)
        stmt = stmt.order_by(Subscription.created_at.desc())
        return self.db.execute(stmt).scalars().first()

    def list_by_company(self, company_id: uuid.UUID) -> List[Subscription]:
        return list(self.db.execute(
            select(Subscription)
            .where(Subscription.company_id == company_id)
            .order_by(Subscription.created_at.desc())
        ).scalars().all())

    def update_status(
        self,
        sub_id: uuid.UUID,
        status: SubscriptionStatus,
        **kwargs
    ) -> None:
        status_value = status.value if isinstance(status, SubscriptionStatus) else status
        values = {"status": status_value, **kwargs}
        if status_value == SubscriptionStatus.CANCELLED.value and "cancelled_at" not in values:
            values["cancelled_at"] = datetime.now(timezone.utc)
        self.db.execute(
            update(Subscription).where(Subscription.id == sub_id).values(**values)
        )
        self.db.commit()

    def update(self, sub: Subscription, data: dict) -> Subscription:
        for key, value in data.items():
            setattr(sub, key, value)
        self.db.commit()
        self.db.refresh(sub)
        return sub
