import logging
from typing import Optional
from datetime import datetime, timezone
import uuid

# Configure a specific logger for audit
audit_logger = logging.getLogger("audit.auth")

def log_otp_event(
    event: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    company_id: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """
    Log an OTP event with required audit fields.
    """
    masked_email = mask_email(email) if email else None
    masked_phone = mask_phone(phone) if phone else None
    
    audit_data = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": str(user_id) if user_id else None,
        "company_id": str(company_id) if company_id else None,
        "contact": masked_email or masked_phone,
        "ip_address": ip_address,
        "user_agent": user_agent
    }
    
    audit_logger.info(f"AUDIT_OTP: {audit_data}")

def mask_email(email: str) -> str:
    """Mask email for audit logs (e.g. j***@example.com)"""
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) > 1:
        local = f"{local[0]}***{local[-1]}"
    else:
        local = "***"
    return f"{local}@{domain}"

def mask_phone(phone: str) -> str:
    """Mask phone for audit logs (e.g. ******1234)"""
    if not phone or len(phone) < 4:
        return "***"
    return f"******{phone[-4:]}"
