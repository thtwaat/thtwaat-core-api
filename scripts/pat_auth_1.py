import os
import uuid
import base64
import httpx
import json

API_URL = "http://localhost:8000/api/v1"

def run():
    uid = uuid.uuid4().hex[:6]
    email = f"pat_{uid}@test.com"
    password = "SecurePassword123!"
    phone = f"+1{uuid.uuid4().int % 10000000000:010d}"

    print(f"Creating account for {email} / {phone} ...")
    
    # Create company
    resp = httpx.post(f"{API_URL}/companies/", json={
        "name": f"PAT Company {uid}",
        "slug": f"pat-company-{uid}",
        "domain": f"pat{uid}.com"
    })
    if resp.status_code != 201:
        print("Company creation failed:", resp.text)
        return
    company_id = resp.json()["id"]
    
    # Create User
    resp = httpx.post(f"{API_URL}/users/", json={
        "email": email,
        "password": password,
        "company_id": company_id,
        "first_name": "PAT",
        "last_name": "Tester",
        "role": "admin"
    })
    if resp.status_code != 201:
        print("User creation failed:", resp.text)
        return
    
    # Normally we would verify email/phone but the endpoint might just work or the script can bypass if it's not strictly enforced for login.
    # Actually wait, login might require email_verified. Let's try login directly first.
    
    # 1. Login
    resp = httpx.post(f"{API_URL}/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        print("Login failed:", resp.text)
        return
    
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Setup MFA
    resp = httpx.post(f"{API_URL}/auth/mfa/setup", headers=headers)
    if resp.status_code != 200:
        print("MFA setup failed:", resp.text)
        return
    
    data = resp.json()
    b64 = data["qr_code_base64"]
    if b64.startswith("data:image/png;base64,"):
        b64 = b64.replace("data:image/png;base64,", "")
        
    img_data = base64.b64decode(b64)
    # Save to artifacts
    artifact_dir = r"C:\Users\HP\.gemini\antigravity\brain\babac127-5d29-4fa5-9e58-0a38cc137ec2"
    with open(os.path.join(artifact_dir, "qr_code.png"), "wb") as f:
        f.write(img_data)
        
    print("\n--- ACTION REQUIRED ---")
    print("A QR code has been saved to artifacts: qr_code.png")
    print(f"User Email: {email}")
    print(f"Password: {password}")
    print(f"Access Token: {token}")
    print("Please scan the QR code with Google Authenticator and provide the 6-digit code to enable MFA.")

if __name__ == "__main__":
    run()
