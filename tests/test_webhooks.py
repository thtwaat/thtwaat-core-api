import pytest
from app.webhooks.service import WebhookService
import hmac
import hashlib

def test_webhook_hmac_signing():
    """
    Test: Verify that the webhook service correctly signs the payload using HMAC SHA256.
    The receiver app must be able to verify authenticity.
    """
    service = WebhookService(db=None) # We don't need DB for signing test
    
    secret = "whsec_testsecret1234567890"
    payload_str = '{"event": "ping", "data": {"message": "hello"}}'
    
    signature_header = service._sign_payload(payload_str, secret)
    
    assert signature_header.startswith("sha256=")
    
    # Verify manually
    hash_value = signature_header.split("=")[1]
    expected_hash = hmac.new(
        secret.encode('utf-8'), 
        payload_str.encode('utf-8'), 
        hashlib.sha256
    ).hexdigest()
    
    assert hash_value == expected_hash
