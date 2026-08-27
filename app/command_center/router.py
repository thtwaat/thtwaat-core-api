from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.router import get_current_user
from app.auth.schema import UserProfileResponse
from app.command_center.schemas import CeoAnalysisResponse, DashboardResponse
from app.command_center.services import CommandCenterService
from app.database.database import get_db
from app.rbac.dependencies import RequirePermission
from app.rbac.enums import Permission

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
    summary="Get Command Center Dashboard Metrics (Super Admin Only)",
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


@router.post(
    "/ceo-analysis",
    response_model=CeoAnalysisResponse,
    summary="AI CEO read-only analysis (Super Admin Only)",
)
async def post_ceo_analysis(
    user: UserProfileResponse = Depends(require_platform_admin),
    service: CommandCenterService = Depends(get_command_center_service),
):
    """
    Generate a read-only AI CEO advisory from live dashboard metrics.
    No tools, persistence, emails, payments, or automation.
    """
    try:
        return await service.analyze_ceo()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI CEO analysis failed: {exc}",
        ) from exc
