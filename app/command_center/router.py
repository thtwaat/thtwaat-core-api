from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission
from app.command_center.schemas import DashboardResponse
from app.command_center.services import CommandCenterService

router = APIRouter(prefix="/command-center", tags=["Command Center"])

def require_platform_admin(user: UserProfileResponse = Depends(get_current_user)):
    """Ensure the user has Super Admin (PLATFORM_ADMIN) permissions."""
    RequirePermission(Permission.PLATFORM_ADMIN)(user.role)
    return user

def get_command_center_service(db: Session = Depends(get_db)) -> CommandCenterService:
    return CommandCenterService(db)

@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Get Command Center Dashboard Metrics (Super Admin Only)"
)
def get_dashboard(
    user: UserProfileResponse = Depends(require_platform_admin),
    service: CommandCenterService = Depends(get_command_center_service),
):
    """
    Retrieve aggregated metrics for the Command Center dashboard.
    Only accessible by Super Admins.
    """
    return service.get_dashboard_metrics()
