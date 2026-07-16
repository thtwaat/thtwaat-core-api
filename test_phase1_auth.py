"""
Phase 1: Complete Authentication Flow Verification
Tests: Login, JWT, Refresh, Logout, Protected Routes, /me endpoint
"""
import warnings; warnings.filterwarnings('ignore')
import json
import sys
import urllib.request
import urllib.error

# Fix Windows encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_URL = "http://127.0.0.1:8000"

def api_call(method, path, body=None, token=None):
    url = BASE_URL + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            content = json.loads(resp.read().decode())
            return status, content
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            content = json.loads(e.read().decode())
        except:
            content = {"error": str(e)}
        return status, content

PASS = "PASS"
FAIL = "FAIL"

print("=" * 60)
print("PHASE 1: AUTHENTICATION FLOW VERIFICATION")
print("=" * 60)

results = []

# Test 1: Admin Login
print("\n[TEST 1] Admin Login (email/password)")
status, resp = api_call("POST", "/api/v1/auth/login", {"email": "admin@thtwaat.com", "password": "Admin123!"})
if status == 200 and "access_token" in resp:
    access_token = resp["access_token"]
    refresh_token = resp["refresh_token"]
    print(f"  [{PASS}] Status: {status} | Token type: {resp.get('token_type')} | Expires: {resp.get('expires_in')}s")
    results.append(("Admin Login", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("Admin Login", False))
    print("Cannot continue without valid token!")
    exit(1)

# Test 2: Wrong password
print("\n[TEST 2] Login with wrong password (expect 401)")
status, resp = api_call("POST", "/api/v1/auth/login", {"email": "admin@thtwaat.com", "password": "wrongpassword"})
if status == 401:
    print(f"  [{PASS}] Correctly rejected wrong password (401)")
    results.append(("Wrong password rejection", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("Wrong password rejection", False))

# Test 3: Non-existent user
print("\n[TEST 3] Login with non-existent user (expect 401)")
status, resp = api_call("POST", "/api/v1/auth/login", {"email": "nonexistent@test.com", "password": "Admin123!"})
if status == 401:
    print(f"  [{PASS}] Correctly rejected non-existent user (401)")
    results.append(("Non-existent user rejection", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("Non-existent user rejection", False))

# Test 4: JWT Verification - /me endpoint
print("\n[TEST 4] Get current user profile (/me)")
status, resp = api_call("GET", "/api/v1/auth/me", token=access_token)
if status == 200 and resp.get("email") == "admin@thtwaat.com":
    print(f"  [{PASS}] Got user profile | email: {resp['email']} | role: {resp['role']}")
    results.append(("GET /me with valid token", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("GET /me with valid token", False))

# Test 5: Protected route with invalid token
print("\n[TEST 5] Access protected route with invalid token (expect 401/403)")
status, resp = api_call("GET", "/api/v1/auth/me", token="invalidtoken123")
if status in [401, 403]:
    print(f"  [{PASS}] Correctly rejected invalid token ({status})")
    results.append(("Invalid token rejection", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("Invalid token rejection", False))

# Test 6: Refresh token
print("\n[TEST 6] Refresh access token")
status, resp = api_call("POST", "/api/v1/auth/refresh", {"refresh_token": refresh_token})
if status == 200 and "access_token" in resp:
    new_access_token = resp["access_token"]
    print(f"  [{PASS}] Got new access token")
    results.append(("Token refresh", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("Token refresh", False))
    new_access_token = access_token

# Test 7: Verify new token works
print("\n[TEST 7] Verify new access token works")
status, resp = api_call("GET", "/api/v1/auth/me", token=new_access_token)
if status == 200 and resp.get("email") == "admin@thtwaat.com":
    print(f"  [{PASS}] New token works | email: {resp['email']}")
    results.append(("New token validity", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("New token validity", False))

# Test 8: Logout
print("\n[TEST 8] Logout (revoke refresh token)")
status, resp = api_call("POST", "/api/v1/auth/logout", {"refresh_token": refresh_token})
if status == 200:
    print(f"  [{PASS}] Logged out | detail: {resp.get('detail')}")
    results.append(("Logout", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("Logout", False))

# Test 9: Use revoked refresh token (expect 401)
print("\n[TEST 9] Use revoked refresh token (expect 401)")
status, resp = api_call("POST", "/api/v1/auth/refresh", {"refresh_token": refresh_token})
if status == 401:
    print(f"  [{PASS}] Revoked token rejected (401)")
    results.append(("Revoked token rejection", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("Revoked token rejection", False))

print("\n" + "=" * 60)
print("PHASE 1 SUMMARY")
print("=" * 60)
passed = sum(1 for _, ok in results if ok)
total = len(results)
for name, ok in results:
    status_str = PASS if ok else FAIL
    print(f"  [{status_str}] {name}")
print(f"\nResult: {passed}/{total} tests passed")
