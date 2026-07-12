from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config.settings import settings
from app.api.router import api_router

# Use lifespan events for startup and shutdown instead of deprecated @app.on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup event: Initialize connections, load models, etc.
    print(f"Starting up {settings.app_name}...")
    yield
    # Shutdown event: Close connections, clean up resources, etc.
    print(f"Shutting down {settings.app_name}...")

app = FastAPI(
    title="THTWAAT Core API",
    version="1.0.0",
    description="Core API for THTWAAT Technology Solutions",
    lifespan=lifespan,
)

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
