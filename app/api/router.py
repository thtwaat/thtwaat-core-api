from fastapi import APIRouter
from app.companies.router import router as companies_router
from app.users.router import router as users_router
from app.auth.router import router as auth_router
from app.apps.router import router as apps_router
from app.storage.router import router as storage_router
from app.notifications.router import router as notifications_router

# Central versioned router — all module routers are registered here
api_router = APIRouter(prefix="/api/v1")

# ── Module Routers ────────────────────────────────────────────────────────────
api_router.include_router(companies_router)
api_router.include_router(users_router)
api_router.include_router(auth_router)
api_router.include_router(apps_router)
api_router.include_router(storage_router)
api_router.include_router(notifications_router)

# ── System Endpoints ──────────────────────────────────────────────────────────

@api_router.get("/status", summary="Get API Status", tags=["System"])
async def get_status():
    """
    Retrieve the current status of the API and company information.
    """
    return {
        "status": "running",
        "company": "THTWAAT Technology Solutions"
    }
