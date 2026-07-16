import pytest
import pyotp
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
import uuid

from main import app
from app.auth.model import MFASettings
from app.users.model import User

client = TestClient(app)

def test_mfa_flow(db_session: Session):
    # Setup company
    from app.companies.model import Company
    comp = Company(name="Test Company", slug=f"test-co-{uuid.uuid4().hex[:6]}")
    db_session.add(comp)
    db_session.commit()
    db_session.refresh(comp)
    comp_id = comp.id
    uid = uuid.uuid4().hex[:6]
    email = f"mfa{uid}@test.com"
    password = "SecurePassword123"
    
    # Register user (dummy registration flow)
    # Using existing test methods or direct DB insert
    # Actually, we can just insert a user manually for testing MFA
    from app.auth.service import AuthService
    hashed = AuthService.get_password_hash(password)
    user = User(
        company_id=comp_id,
        email=email,
        hashed_password=hashed,
        first_name="Test",
        last_name="MFA",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # 1. Login normally (MFA not enabled)
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    access_token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 2. Setup MFA
    resp = client.post("/api/v1/auth/mfa/setup", headers=headers)
    assert resp.status_code == 200
    setup_data = resp.json()
    assert "secret" in setup_data
    assert "qr_code_uri" in setup_data
    assert "qr_code_base64" in setup_data
    
    secret = setup_data["secret"]
    
    # 3. Enable MFA (with valid code)
    totp = pyotp.TOTP(secret)
    valid_code = totp.now()
    
    resp = client.post("/api/v1/auth/mfa/enable", headers=headers, json={"code": valid_code})
    assert resp.status_code == 200
    enable_data = resp.json()
    assert "backup_codes" in enable_data
    backup_codes = enable_data["backup_codes"]
    assert len(backup_codes) == 10
    
    # 4. Attempt login with MFA enabled
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    # Our implementation uses the same 200 with MFARequiredResponse
    assert resp.status_code == 200
    login_data = resp.json()
    assert login_data["mfa_required"] == True
    mfa_token = login_data["mfa_token"]
    
    # 5. Verify MFA with invalid code
    resp = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_token, "totp": "000000"})
    assert resp.status_code == 400
    
    # 6. Verify MFA with valid code
    valid_code = totp.now()
    resp = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_token, "totp": valid_code})
    assert resp.status_code == 200
    verify_data = resp.json()
    assert "access_token" in verify_data
    
    # 7. Verify with backup code
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    mfa_token = resp.json()["mfa_token"]
    
    valid_backup = backup_codes[0]
    resp = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_token, "totp": valid_backup})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    
    # 8. Re-use same backup code (should fail)
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    mfa_token = resp.json()["mfa_token"]
    
    resp = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_token, "totp": valid_backup})
    assert resp.status_code == 400 # invalid MFA code
    
    # 9. Get recovery codes count
    new_access_token = verify_data["access_token"]
    new_headers = {"Authorization": f"Bearer {new_access_token}"}
    resp = client.get("/api/v1/auth/mfa/recovery-codes", headers=new_headers)
    assert resp.status_code == 200
    assert resp.json()["remaining_codes"] == 9
    
    # 10. Disable MFA
    resp = client.post("/api/v1/auth/mfa/disable", headers=new_headers)
    assert resp.status_code == 200
    
    # 11. Login after disable (should get normal tokens)
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert "mfa_required" not in resp.json()

def test_mfa_expired_token(db_session: Session):
    from app.companies.model import Company
    comp = Company(name="Test Company 2", slug=f"test-co-{uuid.uuid4().hex[:6]}")
    db_session.add(comp)
    db_session.commit()
    db_session.refresh(comp)
    comp_id = comp.id
    uid = uuid.uuid4().hex[:6]
    email = f"mfa_exp_{uid}@test.com"
    password = "SecurePassword123"
    
    from app.auth.service import AuthService
    hashed = AuthService.get_password_hash(password)
    user = User(company_id=comp_id, email=email, hashed_password=hashed, first_name="Test", last_name="MFA", is_active=True)
    db_session.add(user)
    db_session.commit()
    
    # Use service to create an expired token
    service = AuthService(db_session)
    # mock create_mfa_token to be expired
    import jose.jwt as jwt
    from app.auth.service import JWT_SECRET_KEY, ALGORITHM
    
    expires_delta = timedelta(minutes=-5)
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"exp": expire, "sub": str(user.id), "type": "mfa_verify"}
    expired_token = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
    
    resp = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": expired_token, "totp": "123456"})
    assert resp.status_code == 401
