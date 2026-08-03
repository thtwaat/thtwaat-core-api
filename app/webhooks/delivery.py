"""Webhook HTTP delivery with explicit success/failure (Week 3 Day 2)."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class WebhookDeliveryError(Exception):
    """Raised when a customer webhook HTTP POST fails or returns non-2xx."""

    def __init__(self, message: str, *, status_code: Optional[int] = None, retryable: bool = True):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


def sign_payload(payload_str: str, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        payload_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def deliver_webhook(
    url: str,
    payload: Dict[str, Any],
    secret: str,
    *,
    timeout: float = 5.0,
) -> Tuple[int, str]:
    """
    POST signed JSON to the customer URL.
    Returns (status_code, body_snippet). Raises WebhookDeliveryError on failure.
    """
    payload_str = json.dumps(payload, separators=(",", ":"), default=str)
    headers = {
        "Content-Type": "application/json",
        "X-THTWAAT-Signature": sign_payload(payload_str, secret),
        "User-Agent": "THTWAAT-Webhook/1.0",
    }
    try:
        resp = requests.post(url, data=payload_str, headers=headers, timeout=timeout)
    except requests.Timeout as exc:
        raise WebhookDeliveryError(f"timeout contacting {url}", retryable=True) from exc
    except requests.RequestException as exc:
        raise WebhookDeliveryError(f"network error: {exc}", retryable=True) from exc

    snippet = (resp.text or "")[:200]
    if 200 <= resp.status_code < 300:
        return resp.status_code, snippet

    # 4xx (except 408/429) usually means bad URL/config — still retry a few times
    # then dead-letter; treat 5xx / 408 / 429 as clearly retryable.
    retryable = resp.status_code >= 500 or resp.status_code in (408, 429)
    raise WebhookDeliveryError(
        f"HTTP {resp.status_code} from {url}: {snippet}",
        status_code=resp.status_code,
        retryable=retryable,
    )


def backoff_seconds(attempt: int, *, base: float = 2.0, cap: float = 300.0) -> float:
    """Exponential backoff: base^attempt, capped. attempt is 1-based after failure."""
    n = max(1, int(attempt))
    delay = float(base) ** n
    return min(delay, float(cap))
