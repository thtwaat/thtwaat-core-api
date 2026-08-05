"""Studio service — Phase 1 saves prompts only (no code generation)."""
from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.schema import UserProfileResponse
from app.auth.tenant import can_manage_company_users
from app.studio.models import StudioProject, StudioProjectStatus
from app.studio.repository import StudioRepository
from app.studio.schemas import StudioProjectCreate


def derive_title(prompt: str, explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit[:255]
    line = prompt.strip().splitlines()[0].strip()
    if len(line) > 80:
        return line[:77] + "..."
    return line or "Untitled product"


class StudioService:
    def __init__(self, db: Session):
        self.repo = StudioRepository(db)

    def create(self, user: UserProfileResponse, payload: StudioProjectCreate) -> StudioProject:
        workspace_id = UUID(str(user.company_id))
        user_id = None
        if getattr(user, "id", None):
            user_id = UUID(str(user.id))
        project = StudioProject(
            workspace_id=workspace_id,
            user_id=user_id,
            title=derive_title(payload.prompt, payload.title),
            prompt=payload.prompt,
            status=StudioProjectStatus.DRAFT,
        )
        return self.repo.create(project)

    def list(
        self, user: UserProfileResponse, *, limit: int = 50, offset: int = 0
    ) -> Tuple[List[StudioProject], int]:
        workspace_id = UUID(str(user.company_id))
        return self.repo.list_for_workspace(workspace_id, limit=limit, offset=offset)

    def get(self, user: UserProfileResponse, project_id: UUID) -> StudioProject:
        workspace_id = UUID(str(user.company_id))
        project = self.repo.get(project_id, workspace_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Studio project not found"
            )
        return project

    def delete(self, user: UserProfileResponse, project_id: UUID) -> None:
        if not can_manage_company_users(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace owners and admins can delete Studio projects",
            )
        project = self.get(user, project_id)
        self.repo.delete(project)
