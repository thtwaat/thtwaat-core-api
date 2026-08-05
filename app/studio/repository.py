"""Repository for studio projects and blueprints."""
from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.studio.models import StudioProject, StudioProjectBlueprint


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

    def save_project(self, project: StudioProject) -> StudioProject:
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def next_blueprint_version(self, project_id: UUID) -> int:
        current = (
            self.db.query(StudioProjectBlueprint.version)
            .filter(StudioProjectBlueprint.project_id == project_id)
            .order_by(StudioProjectBlueprint.version.desc())
            .first()
        )
        return int(current[0]) + 1 if current else 1

    def clear_current_blueprints(self, project_id: UUID) -> None:
        (
            self.db.query(StudioProjectBlueprint)
            .filter(
                StudioProjectBlueprint.project_id == project_id,
                StudioProjectBlueprint.is_current.is_(True),
            )
            .update({"is_current": False}, synchronize_session=False)
        )

    def create_blueprint(self, row: StudioProjectBlueprint) -> StudioProjectBlueprint:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_current_blueprint(
        self, project_id: UUID, workspace_id: UUID
    ) -> Optional[StudioProjectBlueprint]:
        return (
            self.db.query(StudioProjectBlueprint)
            .filter(
                StudioProjectBlueprint.project_id == project_id,
                StudioProjectBlueprint.workspace_id == workspace_id,
                StudioProjectBlueprint.is_current.is_(True),
            )
            .order_by(StudioProjectBlueprint.version.desc())
            .first()
        )

    def get_blueprint_version(
        self, project_id: UUID, workspace_id: UUID, version: int
    ) -> Optional[StudioProjectBlueprint]:
        return (
            self.db.query(StudioProjectBlueprint)
            .filter(
                StudioProjectBlueprint.project_id == project_id,
                StudioProjectBlueprint.workspace_id == workspace_id,
                StudioProjectBlueprint.version == version,
            )
            .first()
        )

    def list_blueprint_versions(
        self, project_id: UUID, workspace_id: UUID
    ) -> List[StudioProjectBlueprint]:
        return (
            self.db.query(StudioProjectBlueprint)
            .filter(
                StudioProjectBlueprint.project_id == project_id,
                StudioProjectBlueprint.workspace_id == workspace_id,
            )
            .order_by(StudioProjectBlueprint.version.desc())
            .all()
        )
