"""Usage metering repository."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.usage.models import UsageEvent, CompanyUsageMeter, UsageDailyAggregate
from app.usage.dimensions import UsageDimension


class UsageRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_meter(
        self,
        company_id: UUID,
        period_start: datetime,
        period_type: str = "monthly",
    ) -> Optional[CompanyUsageMeter]:
        return (
            self.db.query(CompanyUsageMeter)
            .filter(
                CompanyUsageMeter.company_id == company_id,
                CompanyUsageMeter.period_start == period_start,
                CompanyUsageMeter.period_type == period_type,
            )
            .first()
        )

    def create_meter(self, data: Dict[str, Any]) -> CompanyUsageMeter:
        meter = CompanyUsageMeter(**data)
        self.db.add(meter)
        self.db.commit()
        self.db.refresh(meter)
        return meter

    def save_meter(self, meter: CompanyUsageMeter) -> CompanyUsageMeter:
        self.db.add(meter)
        self.db.commit()
        self.db.refresh(meter)
        return meter

    def add_event(self, event: UsageEvent) -> UsageEvent:
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def list_events(
        self,
        company_id: UUID,
        *,
        limit: int = 50,
        dimension: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> List[UsageEvent]:
        q = self.db.query(UsageEvent).filter(UsageEvent.company_id == company_id)
        if dimension:
            q = q.filter(UsageEvent.dimension == dimension)
        if since:
            q = q.filter(UsageEvent.occurred_at >= since)
        return q.order_by(desc(UsageEvent.occurred_at)).limit(limit).all()

    def upsert_daily(self, company_id: UUID, day: datetime, dimension: str, quantity: int) -> None:
        row = (
            self.db.query(UsageDailyAggregate)
            .filter(
                UsageDailyAggregate.company_id == company_id,
                UsageDailyAggregate.day == day,
                UsageDailyAggregate.dimension == dimension,
            )
            .first()
        )
        if row:
            row.quantity = int(row.quantity or 0) + quantity
        else:
            self.db.add(
                UsageDailyAggregate(
                    company_id=company_id,
                    day=day,
                    dimension=dimension,
                    quantity=quantity,
                )
            )
        self.db.commit()

    def history(
        self,
        company_id: UUID,
        *,
        since: datetime,
        dimension: Optional[str] = None,
    ) -> List[UsageDailyAggregate]:
        q = self.db.query(UsageDailyAggregate).filter(
            UsageDailyAggregate.company_id == company_id,
            UsageDailyAggregate.day >= since,
        )
        if dimension:
            q = q.filter(UsageDailyAggregate.dimension == dimension)
        return q.order_by(UsageDailyAggregate.day.asc()).all()

    def top_by_metadata(
        self,
        company_id: UUID,
        field: str,
        *,
        since: datetime,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        col = getattr(UsageEvent, field, None)
        if col is None:
            return []
        rows = (
            self.db.query(col.label("key"), func.sum(UsageEvent.quantity).label("total"))
            .filter(
                UsageEvent.company_id == company_id,
                UsageEvent.occurred_at >= since,
                col.isnot(None),
            )
            .group_by(col)
            .order_by(desc("total"))
            .limit(limit)
            .all()
        )
        return [{"key": str(r.key), "total": int(r.total or 0)} for r in rows]
