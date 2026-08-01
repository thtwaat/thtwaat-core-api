"""
app/users/service.py

Business logic for the Users module.
Enforces rules, validation, and coordinates with other repositories if needed.
"""

import uuid
from typing import Optional
from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.users.model import User, UserStatus
from app.users.schema import UserCreate, UserUpdate, UserResponse, UserListResponse
from app.users.repository import UserRepository
from app.users.signup_roles import assert_create_role_allowed
from app.companies.repository import CompanyRepository
from app.auth.schema import UserProfileResponse
from app.auth.tenant import (
    assert_same_company,
    can_manage_company_users,
    is_platform_admin,
)


class UserService:
    """
    Service layer containing all business rules for Users.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = UserRepository(db)
        self.company_repo = CompanyRepository(db)

    # ── Helper Methods ────────────────────────────────────────────────────────

    def _assert_user_exists(self, user_id: uuid.UUID) -> User:
        """Fetch user or raise 404."""
        user = self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"User with id '{user_id}' not found.",
            )
        return user

    def _assert_active(self, user: User) -> None:
        """Raise 403 if the user account is not active."""
        if not user.is_active:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="This user account is inactive or has been deactivated.",
            )

    def _hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        import bcrypt
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def _actor_is_platform_admin(actor: Optional[UserProfileResponse]) -> bool:
        return is_platform_admin(actor)

    # ── Core Operations ───────────────────────────────────────────────────────

    def create_user(
        self,
        data: UserCreate,
        actor: Optional[UserProfileResponse] = None,
    ) -> UserResponse:
        """
        Register a new user in a specific company.
        - Validates company exists
        - Validates email is unique within the company
        - Hashes password
        - Public signup: only company_owner / employee roles
        - Platform admin (authenticated): any role
        - Authenticated non–platform-admin: must create inside own company
        """
        assert_create_role_allowed(
            data.role,
            allow_privileged=self._actor_is_platform_admin(actor),
        )

        if actor is not None and not self._actor_is_platform_admin(actor):
            if data.company_id != actor.company_id:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="Company not found.",
                )

        # Validate company exists
        company = self.company_repo.get_by_id(data.company_id)
        if not company:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Company with id '{data.company_id}' not found.",
            )
        
        # Check if company is active
        if not company.is_active:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Cannot add users to an inactive company.",
            )

        # Validate email uniqueness within company
        if self.repo.email_exists_in_company(data.email, data.company_id):
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f"Email '{data.email}' is already registered in this company.",
            )

        user_data = data.model_dump()
        raw_password = user_data.pop("password")
        user_data["hashed_password"] = self._hash_password(raw_password)

        user = self.repo.create_from_dict(user_data)

        # ── Dispatch in-app notification event ───────────────────────────────
        try:
            from app.notifications.events import NotificationEventBus
            NotificationEventBus.dispatch(
                event_type="user.registered",
                db=self.db,
                company_id=user.company_id,
                user_id=user.id,
                data={},
            )
        except Exception:
            pass  # Never break user creation due to notification failure

        return UserResponse.model_validate(user)

    def get_user(
        self,
        user_id: uuid.UUID,
        actor: Optional[UserProfileResponse] = None,
    ) -> UserResponse:
        """Fetch a single user (self, same company, or platform admin)."""
        user = self._assert_user_exists(user_id)
        if actor is not None:
            if str(actor.id) != str(user.id):
                assert_same_company(actor, user.company_id, not_found_detail="User not found.")
        return UserResponse.model_validate(user)

    def list_users(
        self,
        company_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[UserStatus] = None,
        actor: Optional[UserProfileResponse] = None,
    ) -> UserListResponse:
        """Fetch paginated users scoped to the actor's company (unless platform admin)."""
        if page_size > 100:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="page_size cannot exceed 100.",
            )

        scoped_company_id = company_id
        if actor is not None and not self._actor_is_platform_admin(actor):
            if company_id is not None and company_id != actor.company_id:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="User not found.",
                )
            scoped_company_id = actor.company_id
        
        rows, total = self.repo.list_all(
            company_id=scoped_company_id,
            page=page,
            page_size=page_size,
            status=status_filter,
            is_active=True,
        )
        return UserListResponse(
            total=total,
            page=page,
            page_size=page_size,
            results=[UserResponse.model_validate(u) for u in rows],
        )

    def update_user(
        self,
        user_id: uuid.UUID,
        data: UserUpdate,
        actor: Optional[UserProfileResponse] = None,
    ) -> UserResponse:
        """Partially update user information (tenant-scoped)."""
        user = self._assert_user_exists(user_id)

        if actor is not None:
            is_self = str(actor.id) == str(user.id)
            if not is_self:
                if not can_manage_company_users(actor):
                    raise HTTPException(
                        status_code=http_status.HTTP_404_NOT_FOUND,
                        detail="User not found.",
                    )
                assert_same_company(actor, user.company_id, not_found_detail="User not found.")
        
        update_data = data.model_dump(exclude_unset=True)
        
        # If updating email, check for uniqueness in the same company
        if "email" in update_data and update_data["email"] != user.email:
            if self.repo.email_exists_in_company(update_data["email"], user.company_id):
                raise HTTPException(
                    status_code=http_status.HTTP_409_CONFLICT,
                    detail=f"Email '{update_data['email']}' is already taken in this company.",
                )
                
        # If updating password, hash it
        if "password" in update_data:
            raw_password = update_data.pop("password")
            update_data["hashed_password"] = self._hash_password(raw_password)
            
        user = self.repo.update_from_dict(user, update_data)
        return UserResponse.model_validate(user)

    def deactivate_user(
        self,
        user_id: uuid.UUID,
        actor: Optional[UserProfileResponse] = None,
    ) -> dict:
        """Soft-delete a user (company managers / platform admin)."""
        user = self._assert_user_exists(user_id)
        if actor is not None:
            if not can_manage_company_users(actor):
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="User not found.",
                )
            assert_same_company(actor, user.company_id, not_found_detail="User not found.")
        self.repo.delete(user)
        return {"detail": f"User '{user_id}' has been deactivated."}
