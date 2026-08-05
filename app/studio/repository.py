"""Repository for studio projects."""
from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.studio.models import StudioProject


class StudioRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, project: StudioProject) -> StudioProject:
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def get(self, project_id: UUID, workspace_id: UUID) -> Optional[StudioProject]:
        return (
            self.db.query(StudioProject)
            .filter(
                StudioProject.id == project_id,
                StudioProject.workspace_id == workspace_id,
            )
            .first()
        )

    def list_for_workspace(
        self, workspace_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> Tuple[List[StudioProject], int]:
        q = (
            self.db.query(StudioProject)
            .filter(StudioProject.workspace_id == workspace_id)
            .order_by(StudioProject.created_at.desc())
        )
        total = q.count()
        items = q.offset(offset).limit(limit).all()
        return items, total

    def delete(self, project: StudioProject) -> None:
        self.db.delete(project)
        self.db.commit()
