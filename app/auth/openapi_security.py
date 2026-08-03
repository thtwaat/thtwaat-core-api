"""OpenAPI security helpers — JWT Bearer + Agent API key documentation."""
from __future__ import annotations

from typing import Any, Dict

from fastapi.openapi.utils import get_openapi

from app.auth.public_endpoints import INTENTIONAL_PUBLIC_OPERATIONS, operation_key

AGENT_API_KEY_SCHEME = "AgentAPIKey"
HTTP_BEARER_SCHEME = "HTTPBearer"

# Public agent endpoints authenticate via API key / embed token (not JWT session).
_AGENT_API_KEY_PATHS = frozenset(
    {
        ("POST", "/public/v1/chat"),
        ("POST", "/public/v1/chat/stream"),
        ("POST", "/public/v1/chat/legacy"),
        ("POST", "/v1/chat/completions"),
        ("GET", "/v1/models"),
        ("GET", "/v1/models/{model_id}"),
        ("GET", "/v1/usage"),
    }
)


def apply_openapi_security(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize OpenAPI security:
    - Ensure HTTPBearer scheme exists for JWT routes.
    - Document AgentAPIKey on public chat endpoints.
    - Explicitly mark intentional JWT-public ops with security: [] when they
      have no scheme (so public intent is visible in the schema).
    """
    components = schema.setdefault("components", {})
    schemes = components.setdefault("securitySchemes", {})

    schemes.setdefault(
        HTTP_BEARER_SCHEME,
        {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT access token from /api/v1/auth/login",
        },
    )
    schemes[AGENT_API_KEY_SCHEME] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "AgentAPIKey",
        "description": (
            "Agent live API key (tht_live_*) or short-lived embed credential "
            "(tht_embed_*). May also be sent in the JSON body as api_key."
        ),
    }

    for path, path_item in (schema.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in list(path_item.items()):
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if not isinstance(operation, dict):
                continue
            key = operation_key(method, path)
            if key in _AGENT_API_KEY_PATHS:
                operation["security"] = [{AGENT_API_KEY_SCHEME: []}]
                continue
            if key in INTENTIONAL_PUBLIC_OPERATIONS and "security" not in operation:
                # Explicit empty security = intentionally unauthenticated (JWT).
                operation["security"] = []

    return schema


def build_custom_openapi(app) -> Dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    app.openapi_schema = apply_openapi_security(schema)
    return app.openapi_schema
