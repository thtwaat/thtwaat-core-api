from fastapi import APIRouter

# Production-ready router with appropriate tags and prefix
api_router = APIRouter(prefix="/api/v1", tags=["System Status"])

@api_router.get("/status", summary="Get API Status")
async def get_status():
    """
    Retrieve the current status of the API and company information.
    """
    return {
        "status": "running",
        "company": "THTWAAT Technology Solutions"
    }
