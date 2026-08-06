"""Repository for studio projects and blueprints."""
from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.studio.models import (
    StudioProject,
    StudioProjectBlueprint,
    StudioProjectBuildPlan,
    StudioProjectFrontend,
    StudioProjectBackend,
    StudioProjectAi,
    StudioProjectInfrastructure,
    StudioProjectApproval,
    StudioProjectBuild,
)


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

    def next_build_plan_version(self, project_id: UUID) -> int:
        current = (
            self.db.query(StudioProjectBuildPlan.version)
            .filter(StudioProjectBuildPlan.project_id == project_id)
            .order_by(StudioProjectBuildPlan.version.desc())
            .first()
        )
        return int(current[0]) + 1 if current else 1

    def clear_current_build_plans(self, project_id: UUID) -> None:
        (
            self.db.query(StudioProjectBuildPlan)
            .filter(
                StudioProjectBuildPlan.project_id == project_id,
                StudioProjectBuildPlan.is_current.is_(True),
            )
            .update({"is_current": False}, synchronize_session=False)
        )

    def create_build_plan(self, row: StudioProjectBuildPlan) -> StudioProjectBuildPlan:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_current_build_plan(
        self, project_id: UUID, workspace_id: UUID
    ) -> Optional[StudioProjectBuildPlan]:
        return (
            self.db.query(StudioProjectBuildPlan)
            .filter(
                StudioProjectBuildPlan.project_id == project_id,
                StudioProjectBuildPlan.workspace_id == workspace_id,
                StudioProjectBuildPlan.is_current.is_(True),
            )
            .order_by(StudioProjectBuildPlan.version.desc())
            .first()
        )

    def next_frontend_version(self, project_id: UUID) -> int:
        current = (
            self.db.query(StudioProjectFrontend.version)
            .filter(StudioProjectFrontend.project_id == project_id)
            .order_by(StudioProjectFrontend.version.desc())
            .first()
        )
        return int(current[0]) + 1 if current else 1

    def clear_current_frontends(self, project_id: UUID) -> None:
        (
            self.db.query(StudioProjectFrontend)
            .filter(
                StudioProjectFrontend.project_id == project_id,
                StudioProjectFrontend.is_current.is_(True),
            )
            .update({"is_current": False}, synchronize_session=False)
        )

    def create_frontend(self, row: StudioProjectFrontend) -> StudioProjectFrontend:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_current_frontend(
        self, project_id: UUID, workspace_id: UUID
    ) -> Optional[StudioProjectFrontend]:
        return (
            self.db.query(StudioProjectFrontend)
            .filter(
                StudioProjectFrontend.project_id == project_id,
                StudioProjectFrontend.workspace_id == workspace_id,
                StudioProjectFrontend.is_current.is_(True),
            )
            .order_by(StudioProjectFrontend.version.desc())
            .first()
        )

    def next_backend_version(self, project_id: UUID) -> int:
        current = (
            self.db.query(StudioProjectBackend.version)
            .filter(StudioProjectBackend.project_id == project_id)
            .order_by(StudioProjectBackend.version.desc())
            .first()
        )
        return int(current[0]) + 1 if current else 1

    def clear_current_backends(self, project_id: UUID) -> None:
        (
            self.db.query(StudioProjectBackend)
            .filter(
                StudioProjectBackend.project_id == project_id,
                StudioProjectBackend.is_current.is_(True),
            )
            .update({"is_current": False}, synchronize_session=False)
        )

    def create_backend(self, row: StudioProjectBackend) -> StudioProjectBackend:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_current_backend(
        self, project_id: UUID, workspace_id: UUID
    ) -> Optional[StudioProjectBackend]:
        return (
            self.db.query(StudioProjectBackend)
            .filter(
                StudioProjectBackend.project_id == project_id,
                StudioProjectBackend.workspace_id == workspace_id,
                StudioProjectBackend.is_current.is_(True),
            )
            .order_by(StudioProjectBackend.version.desc())
            .first()
        )

    def next_ai_version(self, project_id: UUID) -> int:
        current = (
            self.db.query(StudioProjectAi.version)
            .filter(StudioProjectAi.project_id == project_id)
            .order_by(StudioProjectAi.version.desc())
            .first()
        )
        return int(current[0]) + 1 if current else 1

    def clear_current_ai(self, project_id: UUID) -> None:
        (
            self.db.query(StudioProjectAi)
            .filter(
                StudioProjectAi.project_id == project_id,
                StudioProjectAi.is_current.is_(True),
            )
            .update({"is_current": False}, synchronize_session=False)
        )

    def create_ai(self, row: StudioProjectAi) -> StudioProjectAi:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_current_ai(
        self, project_id: UUID, workspace_id: UUID
    ) -> Optional[StudioProjectAi]:
        return (
            self.db.query(StudioProjectAi)
            .filter(
                StudioProjectAi.project_id == project_id,
                StudioProjectAi.workspace_id == workspace_id,
                StudioProjectAi.is_current.is_(True),
            )
            .order_by(StudioProjectAi.version.desc())
            .first()
        )

    def next_infrastructure_version(self, project_id: UUID) -> int:
        current = (
            self.db.query(StudioProjectInfrastructure.version)
            .filter(StudioProjectInfrastructure.project_id == project_id)
            .order_by(StudioProjectInfrastructure.version.desc())
            .first()
        )
        return int(current[0]) + 1 if current else 1

    def clear_current_infrastructure(self, project_id: UUID) -> None:
        (
            self.db.query(StudioProjectInfrastructure)
            .filter(
                StudioProjectInfrastructure.project_id == project_id,
                StudioProjectInfrastructure.is_current.is_(True),
            )
            .update({"is_current": False}, synchronize_session=False)
        )

    def create_infrastructure(
        self, row: StudioProjectInfrastructure
    ) -> StudioProjectInfrastructure:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_current_infrastructure(
        self, project_id: UUID, workspace_id: UUID
    ) -> Optional[StudioProjectInfrastructure]:
        return (
            self.db.query(StudioProjectInfrastructure)
            .filter(
                StudioProjectInfrastructure.project_id == project_id,
                StudioProjectInfrastructure.workspace_id == workspace_id,
                StudioProjectInfrastructure.is_current.is_(True),
            )
            .order_by(StudioProjectInfrastructure.version.desc())
            .first()
        )

    def create_approval(self, row: StudioProjectApproval) -> StudioProjectApproval:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_latest_approval(
        self, project_id: UUID, workspace_id: UUID
    ) -> Optional[StudioProjectApproval]:
        return (
            self.db.query(StudioProjectApproval)
            .filter(
                StudioProjectApproval.project_id == project_id,
                StudioProjectApproval.workspace_id == workspace_id,
            )
            .order_by(StudioProjectApproval.created_at.desc())
            .first()
        )

    def next_build_version(self, project_id: UUID) -> int:
        current = (
            self.db.query(StudioProjectBuild.version)
            .filter(StudioProjectBuild.project_id == project_id)
            .order_by(StudioProjectBuild.version.desc())
            .first()
        )
        return int(current[0]) + 1 if current else 1

    def clear_current_builds(self, project_id: UUID) -> None:
        (
            self.db.query(StudioProjectBuild)
            .filter(
                StudioProjectBuild.project_id == project_id,
                StudioProjectBuild.is_current.is_(True),
            )
            .update({"is_current": False}, synchronize_session=False)
        )

    def create_build(self, row: StudioProjectBuild) -> StudioProjectBuild:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_build(self, row: StudioProjectBuild) -> StudioProjectBuild:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_build(self, build_id: UUID) -> Optional[StudioProjectBuild]:
        return self.db.query(StudioProjectBuild).filter(StudioProjectBuild.id == build_id).first()

    def get_current_build(
        self, project_id: UUID, workspace_id: UUID
    ) -> Optional[StudioProjectBuild]:
        return (
            self.db.query(StudioProjectBuild)
            .filter(
                StudioProjectBuild.project_id == project_id,
                StudioProjectBuild.workspace_id == workspace_id,
                StudioProjectBuild.is_current.is_(True),
            )
            .order_by(StudioProjectBuild.version.desc())
            .first()
        )
