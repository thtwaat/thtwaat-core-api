"""
app/apps/repository.py

Repository Pattern for Apps.
"""

import uuid
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.apps.model import App, AppStatus


class AppRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, app_id: uuid.UUID) -> Optional[App]:
        return self.db.get(App, app_id)

    def slug_exists_in_company(self, slug: str, company_id: uuid.UUID) -> bool:
        stmt = select(func.count()).select_from(App).where(
            App.slug == slug, App.company_id == company_id
        )
        return self.db.scalar(stmt) > 0

    def list_all(
        self,
        company_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 20,
        status: Optional[AppStatus] = None,
    ) -> tuple[list[App], int]:
        stmt = select(App)

        if company_id:
            stmt = stmt.where(App.company_id == company_id)
        if status:
            stmt = stmt.where(App.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt)

        offset = (page - 1) * page_size
        stmt = stmt.order_by(App.created_at.desc()).offset(offset).limit(page_size)
        rows = list(self.db.scalars(stmt).all())

        return rows, total

    def create_from_dict(self, data: dict) -> App:
        app = App(**data)
        self.db.add(app)
        self.db.commit()
        self.db.refresh(app)
        return app

    def update_from_dict(self, app: App, update_data: dict) -> App:
        for field, value in update_data.items():
            setattr(app, field, value)
        self.db.commit()
        self.db.refresh(app)
        return app

    def delete(self, app: App) -> None:
        app.status = AppStatus.INACTIVE
        self.db.commit()
