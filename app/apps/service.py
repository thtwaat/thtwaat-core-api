"""
app/apps/service.py

Business logic for the Apps module.
"""

import uuid
import secrets
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.apps.model import App, AppStatus
from app.apps.schema import AppCreate, AppUpdate, AppResponse, AppListResponse
from app.apps.repository import AppRepository
from app.companies.repository import CompanyRepository


class AppService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AppRepository(db)
        self.company_repo = CompanyRepository(db)

    def _generate_api_key(self) -> str:
        """Generates a secure, random API key."""
        return f"thtwaat_live_{secrets.token_urlsafe(32)}"

    def _assert_app_exists(self, app_id: uuid.UUID) -> App:
        app = self.repo.get_by_id(app_id)
        if not app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"App with id '{app_id}' not found.",
            )
        return app

    def create_app(self, data: AppCreate) -> AppResponse:
        # Validate company
        company = self.company_repo.get_by_id(data.company_id)
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company '{data.company_id}' not found.",
            )
        if not company.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot add apps to an inactive company.",
            )

        # Validate slug uniqueness
        if self.repo.slug_exists_in_company(data.slug, data.company_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Slug '{data.slug}' is already used by another app in this company.",
            )

        app_data = data.model_dump()
        app_data["api_key"] = self._generate_api_key()

        app = self.repo.create_from_dict(app_data)
        return AppResponse.model_validate(app)

    def get_app(self, app_id: uuid.UUID) -> AppResponse:
        app = self._assert_app_exists(app_id)
        return AppResponse.model_validate(app)

    def list_apps(
        self,
        company_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[AppStatus] = None,
    ) -> AppListResponse:
        if page_size > 100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="page_size cannot exceed 100.",
            )
        
        rows, total = self.repo.list_all(
            company_id=company_id,
            page=page,
            page_size=page_size,
            status=status_filter,
        )
        return AppListResponse(
            total=total,
            page=page,
            page_size=page_size,
            results=[AppResponse.model_validate(a) for a in rows],
        )

    def update_app(self, app_id: uuid.UUID, data: AppUpdate) -> AppResponse:
        app = self._assert_app_exists(app_id)
        
        update_data = data.model_dump(exclude_unset=True)
        
        if "slug" in update_data and update_data["slug"] != app.slug:
            if self.repo.slug_exists_in_company(update_data["slug"], app.company_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Slug '{update_data['slug']}' is already in use.",
                )

        app = self.repo.update_from_dict(app, update_data)
        return AppResponse.model_validate(app)

    def delete_app(self, app_id: uuid.UUID) -> dict:
        app = self._assert_app_exists(app_id)
        self.repo.delete(app)
        return {"detail": f"App '{app_id}' deactivated."}
