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
from app.payments.admin_router import router as billing_admin_router
from app.payments.coupons_router import router as coupons_router
from app.agent_platform.publish.router import router as agent_publish_router
from app.usage.router import router as usage_router
from app.domains.router import router as domains_router
from app.deploy.router import router as deploy_router
from app.marketplace.router import router as marketplace_router
from app.product_generator.router import router as product_generator_router
from app.branding.router import router as branding_router
from app.enterprise.router import router as enterprise_router
from app.onboarding.router import router as onboarding_router
from app.monitoring.router import (
    admin_router,
    operations_router,
    monitoring_router,
)
from app.copilot.router import router as copilot_router
from app.agent_store.router import router as agent_store_router
from app.command_center.router import router as command_center_router

# Central versioned router — all module routers are registered here
api_router = APIRouter(prefix="/api/v1")

# ── Module Routers ────────────────────────────────────────────────────────────
api_router.include_router(companies_router)
api_router.include_router(users_router)
api_router.include_router(auth_router)
api_router.include_router(apps_router)
api_router.include_router(storage_router)
api_router.include_router(notifications_router)
# Static /payments/* billing paths MUST be registered before payments_router
# so they are not shadowed by GET/PATCH/DELETE /payments/{payment_id}.
api_router.include_router(plans_router)
api_router.include_router(subscriptions_router)
api_router.include_router(invoices_router)
api_router.include_router(payment_webhooks_router)
api_router.include_router(billing_admin_router)
api_router.include_router(coupons_router)
api_router.include_router(payments_router)
api_router.include_router(ai_router)
api_router.include_router(products_router)
api_router.include_router(api_keys_router)
api_router.include_router(webhooks_router)
api_router.include_router(ai_platform_router)
api_router.include_router(agent_publish_router)
api_router.include_router(usage_router)
api_router.include_router(domains_router)
api_router.include_router(deploy_router)
api_router.include_router(marketplace_router)
api_router.include_router(product_generator_router)
api_router.include_router(branding_router)
api_router.include_router(enterprise_router)
api_router.include_router(onboarding_router)
api_router.include_router(admin_router)
api_router.include_router(operations_router)
api_router.include_router(monitoring_router)
api_router.include_router(copilot_router)
api_router.include_router(agent_store_router)
api_router.include_router(command_center_router)

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
