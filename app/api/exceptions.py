"""
app/api/exceptions.py

Global exception handlers for the FastAPI application.
Ensures uniform JSON structure for all errors.
"""
import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    # Allow structured API errors: {"error": "...", "code": "STRING_CODE"}
    if isinstance(detail, dict) and "error" in detail:
        content = dict(detail)
        content.setdefault("code", exc.status_code)
        return JSONResponse(status_code=exc.status_code, content=content)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": detail, "code": exc.status_code},
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [{"loc": err["loc"], "msg": err["msg"], "type": err["type"]} for err in exc.errors()]
    msg = errors[0]["msg"] if errors else "Validation Error"
    if msg.startswith("value is not a valid email address"):
        msg = "Invalid email address"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": msg, "details": errors, "code": 422}
    )

async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    root = getattr(exc, "orig", None) or exc
    detail = str(root).split("\n")[0][:400]
    logger.error("Database error path=%s: %s", request.url.path, detail)
    # Include a short detail so ops can see enum/column mismatches without docker log diving.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "A database error occurred.",
            "code": 500,
            "detail": detail,
            "path": request.url.path,
        },
    )

async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error.", "code": 500}
    )
