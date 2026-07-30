"""End-to-end fixtures — hit a deployed API via E2E_BASE_URL."""
from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx
import pytest

from tests.support import tcp_open


def _base_url() -> str:
    return os.getenv("E2E_BASE_URL", "http://localhost:8000").rstrip("/")


@pytest.fixture(scope="session")
def e2e_base_url() -> str:
    return _base_url()


@pytest.fixture(scope="session")
def e2e_client(e2e_base_url):
    parsed = urlparse(e2e_base_url)
    host = parsed.hostname or "localhost"
    if parsed.port:
        port = parsed.port
    elif host in {"localhost", "127.0.0.1"}:
        port = 8000
    else:
        port = 443 if parsed.scheme == "https" else 80

    if not tcp_open(host, port):
        pytest.skip(
            f"E2E API not reachable at {e2e_base_url} ({host}:{port}). "
            "Deploy the stack or set E2E_BASE_URL."
        )

    with httpx.Client(base_url=e2e_base_url, timeout=30.0) as client:
        yield client
