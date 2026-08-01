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
from app.auth.schema import UserProfileResponse
from app.auth.tenant import assert_same_company, is_platform_admin


def mask_api_key(raw: str) -> str:
    """Return a non-secret preview suitable for list responses."""
    if not raw:
        return "***"
    if len(raw) <= 12:
        return "***"
    return f"{raw[:8]}…{raw[-4:]}"


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

    def create_app(
        self,
        data: AppCreate,
        actor: Optional[UserProfileResponse] = None,
    ) -> AppResponse:
        # Tenant binding: non–platform-admin callers always create in their company.
        # Platform admins may set company_id via payload. Client company_id is ignored otherwise.
        if actor is not None and not is_platform_admin(actor):
            company_id = actor.company_id
        else:
            company_id = data.company_id

        # Validate company
        company = self.company_repo.get_by_id(company_id)
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company '{company_id}' not found.",
            )
        if not company.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot add apps to an inactive company.",
            )

        # Validate slug uniqueness
        if self.repo.slug_exists_in_company(data.slug, company_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Slug '{data.slug}' is already used by another app in this company.",
            )

        app_data = data.model_dump()
        app_data["company_id"] = company_id
        app_data["api_key"] = self._generate_api_key()

        app = self.repo.create_from_dict(app_data)
        return AppResponse.model_validate(app)

    def get_app(
        self,
        app_id: uuid.UUID,
        actor: Optional[UserProfileResponse] = None,
    ) -> AppResponse:
        app = self._assert_app_exists(app_id)
        if actor is not None:
            assert_same_company(actor, app.company_id, not_found_detail="App not found.")
        return AppResponse.model_validate(app)

    def list_apps(
        self,
        company_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[AppStatus] = None,
        actor: Optional[UserProfileResponse] = None,
    ) -> AppListResponse:
        if page_size > 100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="page_size cannot exceed 100.",
            )

        scoped_company_id = company_id
        if actor is not None and not is_platform_admin(actor):
            if company_id is not None and company_id != actor.company_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="App not found.",
                )
            scoped_company_id = actor.company_id
        
        rows, total = self.repo.list_all(
            company_id=scoped_company_id,
            page=page,
            page_size=page_size,
            status=status_filter,
        )
        masked = []
        for app in rows:
            item = AppResponse.model_validate(app)
            item.api_key = mask_api_key(item.api_key)
            masked.append(item)
        return AppListResponse(
            total=total,
            page=page,
            page_size=page_size,
            results=masked,
        )

    def update_app(
        self,
        app_id: uuid.UUID,
        data: AppUpdate,
        actor: Optional[UserProfileResponse] = None,
    ) -> AppResponse:
        app = self._assert_app_exists(app_id)
        if actor is not None:
            assert_same_company(actor, app.company_id, not_found_detail="App not found.")
        
        update_data = data.model_dump(exclude_unset=True)
        
        if "slug" in update_data and update_data["slug"] != app.slug:
            if self.repo.slug_exists_in_company(update_data["slug"], app.company_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Slug '{update_data['slug']}' is already in use.",
                )

        app = self.repo.update_from_dict(app, update_data)
        return AppResponse.model_validate(app)

    def delete_app(
        self,
        app_id: uuid.UUID,
        actor: Optional[UserProfileResponse] = None,
    ) -> dict:
        app = self._assert_app_exists(app_id)
        if actor is not None:
            assert_same_company(actor, app.company_id, not_found_detail="App not found.")
        self.repo.delete(app)
        return {"detail": f"App '{app_id}' deactivated."}
