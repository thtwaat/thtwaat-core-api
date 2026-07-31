from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config.settings import settings
from app.config.logging import configure_logging
from app.api.router import api_router
from app.database.database import engine
from app.models.base import Base
from app.api.exceptions import (
    http_exception_handler, 
    validation_exception_handler, 
    sqlalchemy_exception_handler, 
    global_exception_handler
)
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError
from prometheus_fastapi_instrumentator import Instrumentator

# Ensure all models are imported before Base.metadata.create_all
import app.companies.model
import app.users.model
import app.auth.model
import app.apps.model
import app.storage.model
import app.notifications.model
import app.payments.model
import app.ai.model
import app.products.model  # noqa
import app.api_keys.model
import app.webhooks.model
import app.features.ai_platform.database.models
import app.agent_platform.models  # noqa — registers agent_configs, agent_api_keys, agent_company_quotas, etc.
import app.agent_platform.knowledge.models  # noqa — registers knowledge_bases, documents, chunks, embeddings_meta
import app.usage.models  # noqa — registers usage_events, company_usage_meters, usage_daily_aggregates
import app.domains.models  # noqa — company_domains
import app.marketplace.models  # noqa
import app.product_generator.models  # noqa
import app.branding.models  # noqa — company_branding, branding_assets
import app.enterprise.models  # noqa — enterprise administration and governance
import app.onboarding.models  # noqa — customer onboarding wizard
import app.monitoring.models  # noqa — monitoring & admin operations
import app.copilot.models  # noqa — AI Copilot orchestration
import app.agent_store.models  # noqa — AI Agent Marketplace & Store
import app.payments.plans.model  # noqa — plans + usage limit columns
import app.payments.subscriptions.model  # noqa
import app.payments.invoices.model  # noqa
# Payment billing models
import app.payments.plans.model      # noqa — registers plans table
import app.payments.invoices.model   # noqa — registers invoices table (must come before subscriptions)
import app.payments.subscriptions.model  # noqa — registers subscriptions table

# Import all LLM provider modules to trigger ProviderRegistry self-registration
import app.agent_platform.providers.gemini      # noqa
import app.agent_platform.providers.openai      # noqa
import app.agent_platform.providers.anthropic   # noqa
import app.agent_platform.providers.ollama      # noqa
import app.agent_platform.providers.openrouter  # noqa
# Use lifespan events for startup and shutdown instead of deprecated @app.on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup event: Initialize connections, load models, etc.
    print(f"Starting up {settings.app_name}...")
    
    # Database tables are managed by Alembic migrations in production
    import redis.asyncio as redis
    from fastapi_limiter import FastAPILimiter
    
    redis_connection = redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}", encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(redis_connection)
    
    yield
    # Shutdown event: Close connections, clean up resources, etc.
    print(f"Shutting down {settings.app_name}...")

app = FastAPI(
    title="THTWAAT Core API",
    version="1.0.0",
    description="Core API for THTWAAT Technology Solutions",
    lifespan=lifespan,
    docs_url=None if settings.app_env == "production" else "/docs",
    redoc_url=None if settings.app_env == "production" else "/redoc",
    openapi_url=None if settings.app_env == "production" else "/openapi.json",
)

from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = settings.CSP_POLICY
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response

app.add_middleware(SecurityHeadersMiddleware)

from app.deploy.middleware import RequestContextMiddleware
app.add_middleware(RequestContextMiddleware)

from app.enterprise.middleware import EnterpriseAuditMiddleware, EnterpriseSecurityMiddleware
app.add_middleware(EnterpriseSecurityMiddleware)
app.add_middleware(EnterpriseAuditMiddleware)

# Instrument Prometheus metrics. The /metrics route itself is gated by
# MetricsAccessMiddleware, which restricts it to internal scrapers or callers
# presenting METRICS_TOKEN whenever APP_ENV is production/staging.
from app.deploy.metrics_guard import MetricsAccessMiddleware

Instrumentator().instrument(app).expose(app, include_in_schema=False)
app.add_middleware(MetricsAccessMiddleware)

# Static CORS (when CORS_ORIGINS includes "*") + dynamic verified domain origins
from app.domains.cors import DynamicCORSMiddleware

if "*" in (settings.CORS_ORIGINS or []):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(DynamicCORSMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

configure_logging()

# Register Exception Handlers
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# Include the main API router
app.include_router(api_router)

# Include the Agent Platform v2 routers (used by platform web)
from app.agent_platform.routers.agent_router import router as agent_router
from app.agent_platform.routers.public_router import router as public_router
from app.agent_platform.knowledge.routers import router as knowledge_router
from app.agent_platform.routers.conversation_router import router as conversation_router

app.include_router(agent_router)
app.include_router(public_router)
app.include_router(knowledge_router)
app.include_router(conversation_router)

from app.branding.public_router import router as branding_public_router
app.include_router(branding_public_router)

from pathlib import Path
from fastapi.responses import FileResponse, PlainTextResponse

_WIDGET_DIST = Path(__file__).resolve().parent / "app" / "agent_platform" / "static" / "widget"
_WIDGET_JS_FILE = _WIDGET_DIST / "widget.js"
_WIDGET_CSS_FILE = _WIDGET_DIST / "widget.css"

# Legacy inline fallback if SDK dist not built yet
_WIDGET_JS_FALLBACK = """\
(function(){console.error("THTWAAT widget: dist not built. Run: cd sdk/widget && npm i && npm run build");})();
"""


@app.get("/widget.js", include_in_schema=False)
async def widget_js():
    if _WIDGET_JS_FILE.exists():
        return FileResponse(
            _WIDGET_JS_FILE,
            media_type="application/javascript",
            headers={"Cache-Control": "public, max-age=300"},
        )
    return PlainTextResponse(_WIDGET_JS_FALLBACK, media_type="application/javascript")


@app.get("/widget.css", include_in_schema=False)
async def widget_css():
    if _WIDGET_CSS_FILE.exists():
        return FileResponse(
            _WIDGET_CSS_FILE,
            media_type="text/css",
            headers={"Cache-Control": "public, max-age=300"},
        )
    return PlainTextResponse("/* widget.css missing — rebuild sdk/widget */", media_type="text/css")

@app.get("/", summary="Root Endpoint", tags=["General"])
async def root():
    """
    Root endpoint to verify the API is running.
    """
    return {"message": f"Welcome to {settings.app_name}"}

@app.get("/health", summary="Health Check", tags=["General"])
async def health_check():
    """
    Comprehensive health for load balancers and orchestration.
    """
    from app.database.database import SessionLocal
    from app.deploy.health import full_health

    db = SessionLocal()
    try:
        payload = await full_health(db)
        code = 200 if payload.get("status") == "healthy" else 503
        return JSONResponse(content=payload, status_code=code)
    finally:
        db.close()


@app.get("/live", summary="Liveness Probe", tags=["General"])
@app.get("/liveness", summary="Liveness Probe (alias)", tags=["General"], include_in_schema=False)
async def liveness_probe():
    return {"status": "alive"}


@app.get("/ready", summary="Readiness Probe", tags=["General"])
@app.get("/readiness", summary="Readiness Probe (alias)", tags=["General"], include_in_schema=False)
async def readiness_probe():
    from app.database.database import SessionLocal
    from app.deploy.health import check_database, check_redis, check_storage

    db = SessionLocal()
    try:
        checks = {
            "database": check_database(db),
            "redis": await check_redis(),
            "storage": check_storage(),
        }
        ok = all(c.get("ok") for c in checks.values())
        return JSONResponse(
            status_code=200 if ok else 503,
            content={"status": "ready" if ok else "not ready", "checks": checks},
        )
    finally:
        db.close()
