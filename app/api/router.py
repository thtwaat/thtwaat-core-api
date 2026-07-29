from fastapi import APIRouter
from app.companies.router import router as companies_router
from app.users.router import router as users_router
from app.auth.router import router as auth_router
from app.apps.router import router as apps_router
from app.storage.router import router as storage_router
from app.notifications.router import router as notifications_router
from app.payments.router import router as payments_router
from app.ai.router import router as ai_router
from app.products.router import router as products_router
from app.api_keys.router import router as api_keys_router
from app.webhooks.router import router as webhooks_router
from app.features.ai_platform.routers.ai_routers import router as ai_platform_router
# Payment billing routers
from app.payments.plans.router import router as plans_router
from app.payments.subscriptions.router import router as subscriptions_router
from app.payments.invoices.router import router as invoices_router
from app.payments.webhooks.router import router as payment_webhooks_router
from app.agent_platform.publish.router import router as agent_publish_router
from app.usage.router import router as usage_router
from app.domains.router import router as domains_router
from app.deploy.router import router as deploy_router

# Central versioned router — all module routers are registered here
api_router = APIRouter(prefix="/api/v1")

# ── Module Routers ────────────────────────────────────────────────────────────
api_router.include_router(companies_router)
api_router.include_router(users_router)
api_router.include_router(auth_router)
api_router.include_router(apps_router)
api_router.include_router(storage_router)
api_router.include_router(notifications_router)
api_router.include_router(payments_router)
api_router.include_router(ai_router)
api_router.include_router(products_router)
api_router.include_router(api_keys_router)
api_router.include_router(webhooks_router)
api_router.include_router(ai_platform_router)
# Payment billing routers
api_router.include_router(plans_router)
api_router.include_router(subscriptions_router)
api_router.include_router(invoices_router)
api_router.include_router(payment_webhooks_router)
api_router.include_router(agent_publish_router)
api_router.include_router(usage_router)
api_router.include_router(domains_router)
api_router.include_router(deploy_router)

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
