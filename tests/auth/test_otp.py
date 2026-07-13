import pytest
import uuid
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
import unittest.mock as mock

from main import app
from app.auth.model import OTPCode
from app.auth.service import AuthService
from app.database.database import get_db

client = TestClient(app)

@pytest.fixture
def test_email():
    return f"otp_test_{uuid.uuid4().hex[:6]}@example.com"

def test_send_otp(test_email):
    with mock.patch.object(AuthService, 'generate_otp', return_value="123456"):
        resp = client.post("/api/v1/auth/send-otp", json={
            "purpose": "REGISTER",
            "email": test_email
        })
        assert resp.status_code == 200
        assert resp.json()["detail"] == "OTP sent successfully"

def test_verify_otp_success(test_email):
    with mock.patch.object(AuthService, 'generate_otp', return_value="123456"):
        # Send
        client.post("/api/v1/auth/send-otp", json={"purpose": "REGISTER", "email": test_email})
        
        # Verify
        resp = client.post("/api/v1/auth/verify-otp", json={
            "purpose": "REGISTER",
            "email": test_email,
            "code": "123456"
        })
        assert resp.status_code == 200
        assert resp.json()["detail"] == "OTP verified successfully"

def test_invalid_otp(test_email):
    with mock.patch.object(AuthService, 'generate_otp', return_value="123456"):
        client.post("/api/v1/auth/send-otp", json={"purpose": "REGISTER", "email": test_email})
        
        resp = client.post("/api/v1/auth/verify-otp", json={
            "purpose": "REGISTER",
            "email": test_email,
            "code": "654321"
        })
        assert resp.status_code == 400
        assert resp.json()["error"] == "Invalid OTP"

def test_reused_otp(test_email):
    with mock.patch.object(AuthService, 'generate_otp', return_value="123456"):
        client.post("/api/v1/auth/send-otp", json={"purpose": "REGISTER", "email": test_email})
        
        # First verification succeeds
        client.post("/api/v1/auth/verify-otp", json={"purpose": "REGISTER", "email": test_email, "code": "123456"})
        
        # Second verification fails
        resp = client.post("/api/v1/auth/verify-otp", json={
            "purpose": "REGISTER",
            "email": test_email,
            "code": "123456"
        })
        assert resp.status_code == 400
        assert "already been used" in resp.json()["error"]

def test_max_attempts(test_email):
    with mock.patch.object(AuthService, 'generate_otp', return_value="123456"):
        client.post("/api/v1/auth/send-otp", json={"purpose": "REGISTER", "email": test_email})
        
        for _ in range(5):
            resp = client.post("/api/v1/auth/verify-otp", json={
                "purpose": "REGISTER",
                "email": test_email,
                "code": "000000"
            })
            if resp.status_code == 400 and "Maximum OTP attempts" in resp.json()["error"]:
                break
        
        # The 6th attempt should return max attempts reached even if correct
        resp = client.post("/api/v1/auth/verify-otp", json={
            "purpose": "REGISTER",
            "email": test_email,
            "code": "123456"
        })
        assert resp.status_code == 400
        assert "Maximum OTP attempts reached" in resp.json()["error"]

def test_resend_cooldown(test_email):
    with mock.patch.object(AuthService, 'generate_otp', return_value="123456"):
        client.post("/api/v1/auth/send-otp", json={"purpose": "REGISTER", "email": test_email})
        
        resp = client.post("/api/v1/auth/resend-otp", json={"purpose": "REGISTER", "email": test_email})
        assert resp.status_code == 429
        assert "wait 60 seconds" in resp.json()["error"]

from sqlalchemy import text

def test_rate_limit():
    email = f"rate_limit_{uuid.uuid4().hex[:6]}@example.com"
    with mock.patch.object(AuthService, 'generate_otp', return_value="123456"):
        # We need to bypass cooldown to test rate limit. So we mock datetime or DB.
        # Alternatively, since we can't easily bypass cooldown in functional tests without a DB mock,
        # let's just make 5 requests by overriding created_at directly in DB.
        
        db = next(get_db())
        for _ in range(5):
            # Send OTP
            client.post("/api/v1/auth/send-otp", json={"purpose": "REGISTER", "email": email})
            # Manually update created_at to bypass cooldown
            db.execute(text(f"UPDATE otp_codes SET created_at = '{datetime.now(timezone.utc) - timedelta(minutes=2)}' WHERE email = '{email}'"))
            db.commit()
            
        # 6th should fail with rate limit
        resp = client.post("/api/v1/auth/send-otp", json={"purpose": "REGISTER", "email": email})
        assert resp.status_code == 429
        assert "Too many OTP requests" in resp.json()["error"]

def test_expired_otp(test_email):
    with mock.patch.object(AuthService, 'generate_otp', return_value="123456"):
        client.post("/api/v1/auth/send-otp", json={"purpose": "REGISTER", "email": test_email})
        
        # Manually expire
        db = next(get_db())
        db.execute(text(f"UPDATE otp_codes SET expires_at = '{datetime.now(timezone.utc) - timedelta(minutes=1)}' WHERE email = '{test_email}'"))
        db.commit()
        
        resp = client.post("/api/v1/auth/verify-otp", json={
            "purpose": "REGISTER",
            "email": test_email,
            "code": "123456"
        })
        assert resp.status_code == 400
        assert "expired" in resp.json()["error"]

