from fastapi import APIRouter
from app.companies.router import router as companies_router

# Central versioned router — all module routers are registered here
api_router = APIRouter(prefix="/api/v1")

# ── Module Routers ────────────────────────────────────────────────────────────
api_router.include_router(companies_router)

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
