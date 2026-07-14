import pytest
from unittest import mock
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
import uuid

from fastapi.testclient import TestClient
from main import app
from app.auth.service import AuthService
from app.database.database import get_db

client = TestClient(app)

@pytest.fixture
def test_user():
    # Setup test company and user for verification
    uid = uuid.uuid4().hex[:6]
    email = f"identity_{uid}@example.com"
    
    resp = client.post("/api/v1/companies/", json={
        "name": f"Test Company {uid}",
        "slug": f"test-company-{uid}",
        "domain": f"test{uid}.com"
    })
    company_id = resp.json()["id"]
    
    resp = client.post("/api/v1/users/", json={
        "email": email,
        "password": "securepassword123",
        "company_id": company_id,
        "first_name": "Test",
        "last_name": "User",
        "role": "employee"
    })
    return email

# ── Email Verification ────────────────────────────────────────────────────────

def test_email_verification_flow(test_user):
    with mock.patch.object(AuthService, 'generate_otp', return_value="123456"):
        # 1. Send verification
        resp = client.post("/api/v1/auth/send-email-verification", json={"email": test_user})
        assert resp.status_code == 200
        
        # 2. Invalid OTP
        resp = client.post("/api/v1/auth/verify-email", json={"email": test_user, "code": "654321"})
        assert resp.status_code == 400
        assert "Invalid OTP" in resp.json()["error"]
        
        # 3. Verify success
        resp = client.post("/api/v1/auth/verify-email", json={"email": test_user, "code": "123456"})
        assert resp.status_code == 200
        assert "Email verified successfully" in resp.json()["detail"]
        
        # 4. Already verified
        resp = client.post("/api/v1/auth/send-email-verification", json={"email": test_user})
        assert resp.status_code == 400
        assert "already verified" in resp.json()["error"]
        
        resp = client.post("/api/v1/auth/verify-email", json={"email": test_user, "code": "123456"})
        assert resp.status_code == 400
        assert "already verified" in resp.json()["error"]

def test_email_verification_expired(test_user):
    # Setup a new user for expired test to avoid already verified error
    uid = uuid.uuid4().hex[:6]
    email = f"expired_{uid}@example.com"
    resp = client.post("/api/v1/users/", json={
        "email": email,
        "password": "securepassword123",
        "company_id": client.post("/api/v1/companies/", json={"name": f"C {uid}", "slug": f"c-{uid}", "domain": f"d{uid}.com"}).json()["id"],
        "first_name": "Test",
        "last_name": "User",
        "role": "employee"
    })

    with mock.patch.object(AuthService, 'generate_otp', return_value="123456"):
        client.post("/api/v1/auth/send-email-verification", json={"email": email})
        
        db = next(get_db())
        db.execute(text(f"UPDATE otp_codes SET expires_at = '{datetime.now(timezone.utc) - timedelta(minutes=1)}' WHERE email = '{email}' AND purpose = 'EMAIL_VERIFY'"))
        db.commit()
        
        resp = client.post("/api/v1/auth/verify-email", json={"email": email, "code": "123456"})
        assert resp.status_code == 400
        assert "expired" in resp.json()["error"]

# ── Phone Verification ────────────────────────────────────────────────────────

def test_phone_verification_flow():
    phone = f"+1800555{uuid.uuid4().hex[:4]}"
    with mock.patch.object(AuthService, 'generate_otp', return_value="123456"):
        # 1. Send verification
        resp = client.post("/api/v1/auth/send-phone-verification", json={"phone": phone})
        assert resp.status_code == 200
        
        # 2. Invalid OTP
        resp = client.post("/api/v1/auth/verify-phone", json={"phone": phone, "code": "000000"})
        assert resp.status_code == 400
        assert "Invalid OTP" in resp.json()["error"]
        
        # 3. Verify success
        resp = client.post("/api/v1/auth/verify-phone", json={"phone": phone, "code": "123456"})
        assert resp.status_code == 200

# ── Password Reset ────────────────────────────────────────────────────────────

def test_password_reset_flow(test_user):
    with mock.patch.object(AuthService, 'generate_otp', return_value="123456"):
        # Initial login to get a refresh token
        resp = client.post("/api/v1/auth/login", json={"email": test_user, "password": "securepassword123"})
        assert resp.status_code == 200
        refresh_token = resp.json()["refresh_token"]
        
        # 1. Invalid email
        resp = client.post("/api/v1/auth/forgot-password", json={"email": "nonexistent@example.com"})
        assert resp.status_code == 404
        
        # 2. Forgot password
        resp = client.post("/api/v1/auth/forgot-password", json={"email": test_user})
        assert resp.status_code == 200
        
        # 3. Weak password
        resp = client.post("/api/v1/auth/reset-password", json={
            "email": test_user,
            "code": "123456",
            "new_password": "short"
        })
        assert resp.status_code == 422 # Pydantic validation fails for min_length=8
        
        # 4. Reset success
        resp = client.post("/api/v1/auth/reset-password", json={
            "email": test_user,
            "code": "123456",
            "new_password": "newsecurepassword456"
        })
        assert resp.status_code == 200
        
        # 5. Reused OTP
        resp = client.post("/api/v1/auth/reset-password", json={
            "email": test_user,
            "code": "123456",
            "new_password": "newsecurepassword789"
        })
        assert resp.status_code == 400
        assert "already been used" in resp.json()["error"]
        
        # 6. Login with new password works
        resp = client.post("/api/v1/auth/login", json={"email": test_user, "password": "newsecurepassword456"})
        assert resp.status_code == 200
        
        # 7. Old refresh token is revoked
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 401

def test_password_reset_expired(test_user):
    with mock.patch.object(AuthService, 'generate_otp', return_value="123456"):
        client.post("/api/v1/auth/forgot-password", json={"email": test_user})
        
        db = next(get_db())
        db.execute(text(f"UPDATE otp_codes SET expires_at = '{datetime.now(timezone.utc) - timedelta(minutes=1)}' WHERE email = '{test_user}' AND purpose = 'PASSWORD_RESET'"))
        db.commit()
        
        resp = client.post("/api/v1/auth/reset-password", json={
            "email": test_user,
            "code": "123456",
            "new_password": "newsecurepassword456"
        })
        assert resp.status_code == 400
        assert "expired" in resp.json()["error"]
