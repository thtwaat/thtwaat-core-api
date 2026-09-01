"""AI Calling — inbound telephony webhooks (Twilio today; any future
provider self-registers into ``TelephonyProviderRegistry`` and gets its own
thin route here — routing/agent-resolution/AI logic never branches on
provider name, see ``call_runtime.py``).

Every route here is unauthenticated by API key (Twilio can't send one) and
instead relies entirely on webhook signature verification — no request body
is trusted before that check passes. See ``twilio_provider.verify_webhook``.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.database.database import get_db
from app.agent_platform.telephony.call_runtime import CallRuntime
from app.agent_platform.telephony.base import TelephonyProviderRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public/v1/telephony", tags=["Telephony (AI Calling)"])

_TWIML_MEDIA_TYPE = "application/xml"


def _public_url_for_request(request: Request) -> str:
    """Reconstruct the URL exactly as configured/dialed on Twilio's side.

    We deliberately do NOT trust ``request.url`` verbatim — this process may
    sit behind a reverse proxy that doesn't forward scheme/host, and Twilio
    signs the URL IT called (``PUBLIC_API_BASE_URL`` + path + query, which is
    exactly what ``call_runtime._action_url`` generates), not whatever host
    header this process happens to see.
    """
    base = (settings.PUBLIC_API_BASE_URL or "").rstrip("/")
    path = request.url.path
    query = f"?{request.url.query}" if request.url.query else ""
    return f"{base}{path}{query}"


async def _verify_twilio_request(request: Request) -> dict:
    """Verify the X-Twilio-Signature header and return the parsed form params.

    Returns an empty dict (never raises) on a failed check — every caller
    treats an empty/invalid result as "reject", uniformly.
    """
    form = await request.form()
    params = {k: str(v) for k, v in form.multi_items()}
    signature = request.headers.get("X-Twilio-Signature")
    url = _public_url_for_request(request)

    provider = TelephonyProviderRegistry.get_provider("twilio")
    if not provider.verify_webhook(url=url, form_params=params, signature_header=signature):
        logger.warning("telephony: invalid Twilio signature for %s", request.url.path)
        return {}
    return params


def _reject_response() -> Response:
    provider = TelephonyProviderRegistry.get_provider("twilio")
    return Response(content=provider.build_reject(), media_type=_TWIML_MEDIA_TYPE, status_code=200)


@router.post("/twilio/voice", summary="Twilio inbound call webhook")
async def twilio_voice(request: Request, db: Session = Depends(get_db)):
    params = await _verify_twilio_request(request)
    if not params:
        return _reject_response()

    twiml = await CallRuntime.handle_incoming_call(
        db,
        provider_name="twilio",
        to_number=params.get("To", ""),
        from_number=params.get("From", ""),
        call_sid=params.get("CallSid", ""),
    )
    return Response(content=twiml, media_type=_TWIML_MEDIA_TYPE)


@router.post("/twilio/gather", summary="Twilio Gather (speech turn) callback")
async def twilio_gather(request: Request, db: Session = Depends(get_db)):
    params = await _verify_twilio_request(request)
    if not params:
        return _reject_response()

    agent_id = request.query_params.get("agent_id", "")
    conversation_id = request.query_params.get("conversation_id", "")
    if not agent_id or not conversation_id:
        return _reject_response()

    twiml = await CallRuntime.handle_gather(
        db,
        provider_name="twilio",
        agent_id=agent_id,
        conversation_id=conversation_id,
        call_sid=params.get("CallSid", ""),
        speech_result=params.get("SpeechResult", ""),
    )
    return Response(content=twiml, media_type=_TWIML_MEDIA_TYPE)


@router.post("/twilio/status", summary="Twilio call status changes webhook")
async def twilio_status(request: Request, db: Session = Depends(get_db)):
    params = await _verify_twilio_request(request)
    if not params:
        return Response(status_code=204)

    await CallRuntime.handle_status_callback(
        db,
        call_sid=params.get("CallSid", ""),
        call_status=params.get("CallStatus", ""),
        call_duration=params.get("CallDuration"),
    )
    return Response(status_code=204)
