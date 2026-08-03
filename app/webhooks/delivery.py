"""Webhook HTTP delivery + HMAC verification (Week 3 Day 2 + Day 5)."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from typing import Any, Dict, Optional, Tuple

import requests

from app.config.settings import settings

logger = logging.getLogger(__name__)


class WebhookDeliveryError(Exception):
    """Raised when a customer webhook HTTP POST fails or returns non-2xx."""

    def __init__(self, message: str, *, status_code: Optional[int] = None, retryable: bool = True):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class WebhookSignatureError(Exception):
    """Raised when a signature cannot be verified (receiver-side helper)."""


def signature_tolerance_seconds() -> int:
    return int(getattr(settings, "WEBHOOK_SIGNATURE_TOLERANCE_SECONDS", 300) or 300)


def signed_payload(timestamp: int, payload_str: str) -> str:
    """Canonical string HMAC'd for v1 signatures: `{unix_ts}.{raw_body}`."""
    return f"{int(timestamp)}.{payload_str}"


def sign_payload(payload_str: str, secret: str) -> str:
    """Legacy body-only signature (`sha256=...`). Prefer sign_v1 for new deliveries."""
    digest = hmac.new(
        secret.encode("utf-8"),
        payload_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def sign_v1(
    payload_str: str,
    secret: str,
    *,
    timestamp: Optional[int] = None,
) -> Tuple[int, str]:
    """
    Timestamped HMAC (Week 3 Day 5).
    Returns (timestamp, header_value) where header_value is `v1=<hex>`.
    """
    ts = int(timestamp if timestamp is not None else time.time())
    digest = hmac.new(
        secret.encode("utf-8"),
        signed_payload(ts, payload_str).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return ts, f"v1={digest}"


def _parse_signature_header(header: str) -> Dict[str, str]:
    """
    Parse `t=1712,v1=abc` or `v1=abc` or legacy `sha256=abc`.
    """
    out: Dict[str, str] = {}
    for part in (header or "").split(","):
        part = part.strip()
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def verify_webhook_signature(
    payload_str: str,
    secret: str,
    *,
    signature_header: str,
    timestamp_header: Optional[str] = None,
    tolerance_seconds: Optional[int] = None,
    now: Optional[int] = None,
) -> bool:
    """
    Receiver-side verification helper (customers + our tests).

    Accepts:
      - Day 5: `X-THTWAAT-Signature: v1=...` + `X-THTWAAT-Timestamp: <unix>`
        or combined `t=<unix>,v1=...`
      - Legacy: `sha256=...` over raw body (no replay protection)
    """
    parts = _parse_signature_header(signature_header)
    tolerance = (
        tolerance_seconds
        if tolerance_seconds is not None
        else signature_tolerance_seconds()
    )
    now_ts = int(now if now is not None else time.time())

    if "v1" in parts:
        ts_raw = parts.get("t") or timestamp_header
        if ts_raw is None:
            raise WebhookSignatureError("missing timestamp for v1 signature")
        try:
            ts = int(ts_raw)
        except ValueError as exc:
            raise WebhookSignatureError("invalid timestamp") from exc
        if abs(now_ts - ts) > int(tolerance):
            raise WebhookSignatureError(
                f"timestamp outside tolerance ({tolerance}s) — possible replay"
            )
        expected = hmac.new(
            secret.encode("utf-8"),
            signed_payload(ts, payload_str).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, parts["v1"]):
            raise WebhookSignatureError("v1 signature mismatch")
        return True

    if "sha256" in parts:
        expected = hmac.new(
            secret.encode("utf-8"),
            payload_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, parts["sha256"]):
            raise WebhookSignatureError("legacy sha256 signature mismatch")
        return True

    raise WebhookSignatureError("unrecognized signature header format")


def new_delivery_id() -> str:
    return f"whdel_{uuid.uuid4().hex}"


def deliver_webhook(
    url: str,
    payload: Dict[str, Any],
    secret: str,
    *,
    timeout: float = 5.0,
    timestamp: Optional[int] = None,
) -> Tuple[int, str]:
    """
    POST signed JSON to the customer URL.
    Returns (status_code, body_snippet). Raises WebhookDeliveryError on failure.
    """
    # Ensure delivery id for customer-side idempotency
    if "delivery_id" not in payload:
        payload = {**payload, "delivery_id": new_delivery_id()}

    payload_str = json.dumps(payload, separators=(",", ":"), default=str)
    ts, sig = sign_v1(payload_str, secret, timestamp=timestamp)
    headers = {
        "Content-Type": "application/json",
        "X-THTWAAT-Timestamp": str(ts),
        "X-THTWAAT-Signature": sig,
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
