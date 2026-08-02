"""Shared HTTP Bearer scheme for JWT-protected routes (401 when missing)."""
from fastapi.security import HTTPBearer

# FastAPI HTTPBearer returns 401 + WWW-Authenticate when credentials are absent.
bearer_scheme = HTTPBearer(auto_error=True)
