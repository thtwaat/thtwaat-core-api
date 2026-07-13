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

# Use lifespan events for startup and shutdown instead of deprecated @app.on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup event: Initialize connections, load models, etc.
    print(f"Starting up {settings.app_name}...")
    
    # Create all database tables (useful for development)
    # Note: In a pure production environment, Alembic migrations are preferred
    Base.metadata.create_all(bind=engine)
    
    yield
    # Shutdown event: Close connections, clean up resources, etc.
    print(f"Shutting down {settings.app_name}...")

app = FastAPI(
    title="THTWAAT Core API",
    version="1.0.0",
    description="Core API for THTWAAT Technology Solutions",
    lifespan=lifespan,
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
