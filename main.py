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
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Instrument Prometheus metrics
Instrumentator().instrument(app).expose(app)

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

@app.get("/", summary="Root Endpoint", tags=["General"])
async def root():
    """
    Root endpoint to verify the API is running.
    """
    return {"message": f"Welcome to {settings.app_name}"}

@app.get("/health", summary="Health Check", tags=["General"])
async def health_check():
    """
    Health check endpoint for load balancers and container orchestration.
    """
    return JSONResponse(
        content={
            "status": "healthy",
            "environment": settings.app_env,
            "version": app.version
        },
        status_code=200
    )

@app.get("/liveness", summary="Liveness Probe", tags=["General"])
async def liveness_probe():
    return {"status": "alive"}

@app.get("/readiness", summary="Readiness Probe", tags=["General"])
async def readiness_probe():
    from sqlalchemy import text
    import redis.asyncio as redis
    try:
        # Check Database
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        # Check Redis
        r = redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}", encoding="utf-8", decode_responses=True)
        await r.ping()
        return {"status": "ready"}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "not ready", "details": str(e)})
