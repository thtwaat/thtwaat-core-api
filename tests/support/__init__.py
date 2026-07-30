"""Shared test support — DB/Redis helpers and external service mocks.

Does not alter application runtime behavior.
"""
from __future__ import annotations

import os
import socket
import time
from contextlib import contextmanager
from typing import Iterator, Optional
from unittest.mock import MagicMock


def ensure_test_env() -> None:
    """Safe defaults so Settings() can load during unit collection."""
    os.environ.setdefault("JWT_SECRET_KEY", "unit-test-jwt-secret-key-32chars!!")
    os.environ.setdefault("JWT_REFRESH_SECRET_KEY", "unit-test-refresh-secret-key-32!")
    os.environ.setdefault("APP_ENV", "test")
    os.environ.setdefault("STORAGE_PROVIDER", "local")
    os.environ.setdefault("SSL_MODE", "simulate")


def tcp_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_tcp(host: str, port: int, timeout: float = 30.0, interval: float = 0.5) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if tcp_open(host, port):
            return True
        time.sleep(interval)
    return False


def postgres_dsn_from_env() -> str:
    return os.getenv(
        "DATABASE_URL",
        os.getenv(
            "TEST_DATABASE_URL",
            "postgresql://thtwaat:thtwaat@localhost:5433/thtwaat_test",
        ),
    )


def redis_host_port() -> tuple[str, int]:
    host = os.getenv("REDIS_HOST", os.getenv("TEST_REDIS_HOST", "localhost"))
    port = int(os.getenv("REDIS_PORT", os.getenv("TEST_REDIS_PORT", "6380")))
    return host, port


def parse_host_port_from_database_url(url: str) -> tuple[str, int]:
    # postgresql://user:pass@host:port/db
    try:
        after_at = url.split("@", 1)[1]
        host_port = after_at.split("/", 1)[0]
        if ":" in host_port:
            host, port_s = host_port.rsplit(":", 1)
            return host, int(port_s)
        return host_port, 5432
    except (IndexError, ValueError):
        return "localhost", 5432


@contextmanager
def temporary_env(**kwargs: str) -> Iterator[None]:
    previous: dict[str, Optional[str]] = {}
    for key, value in kwargs.items():
        previous[key] = os.environ.get(key)
        os.environ[key] = value
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def mock_payment_provider() -> MagicMock:
    provider = MagicMock()
    result = MagicMock()
    result.success = True
    result.transaction_id = "txn_test_001"
    result.provider_data = {"stub": True}
    result.error_message = None
    provider.process_payment.return_value = result
    provider.refund_payment.return_value = result
    return provider


def mock_ai_provider() -> MagicMock:
    provider = MagicMock()
    provider.generate.return_value = {"text": "mock-ai-response", "tokens": 1}
    return provider
