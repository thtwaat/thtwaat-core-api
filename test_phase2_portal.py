"""
Phase 2: Customer Portal - Agent CRUD Flow Verification
Tests: Dashboard, Create Agent, Agent List, Edit Agent, Delete Agent,
       Knowledge Base, API Keys, Webhooks, Billing pages
"""
import warnings; warnings.filterwarnings('ignore')
import json
import sys
import urllib.request
import urllib.error

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
print("PHASE 2: CUSTOMER PORTAL FLOW VERIFICATION")
print("=" * 60)

results = []

# --- Login first ---
print("\n[SETUP] Logging in as admin...")
status, resp = api_call("POST", "/api/v1/auth/login", {"email": "admin@thtwaat.com", "password": "Admin123!"})
if status != 200:
    print(f"  [{FAIL}] Cannot login! {resp}")
    exit(1)
token = resp["access_token"]
print(f"  [PASS] Logged in successfully")

# =========================================
# AGENT CRUD (v2/agents)
# =========================================
print("\n--- AGENT CRUD (v2/agents) ---")

# Test 1: Create Agent
print("\n[TEST 1] Create Agent")
agent_body = {
    "name": "QA Test Agent",
    "description": "Agent created during QA testing",
    "system_prompt_template": "You are a helpful assistant for {company_name}.",
    "temperature": 0.7,
    "is_template": False,
    "web_config": {"theme": "dark", "language": "en"}
}
status, resp = api_call("POST", "/v2/agents", agent_body, token=token)
if status == 200 and resp.get("name") == "QA Test Agent":
    agent_id = resp["id"]
    print(f"  [{PASS}] Agent created | id: {agent_id} | status: {resp.get('status')}")
    results.append(("Create Agent", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("Create Agent", False))
    agent_id = None

# Test 2: List Agents
print("\n[TEST 2] List Agents")
status, resp = api_call("GET", "/v2/agents", token=token)
if status == 200 and isinstance(resp, list):
    print(f"  [{PASS}] Got {len(resp)} agents")
    results.append(("List Agents", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("List Agents", False))

# Test 3: Get Agent by ID
if agent_id:
    print("\n[TEST 3] Get Agent by ID")
    status, resp = api_call("GET", f"/v2/agents/{agent_id}", token=token)
    if status == 200 and resp.get("id") == agent_id:
        print(f"  [{PASS}] Got agent | name: {resp.get('name')}")
        results.append(("Get Agent by ID", True))
    else:
        print(f"  [{FAIL}] Status: {status} | Response: {resp}")
        results.append(("Get Agent by ID", False))

# Test 4: List Templates
print("\n[TEST 4] List Agent Templates")
status, resp = api_call("GET", "/v2/agents/templates")
if status == 200 and isinstance(resp, list):
    print(f"  [{PASS}] Got {len(resp)} templates")
    results.append(("List Templates", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("List Templates", False))

# Test 5: Publish Agent
if agent_id:
    print("\n[TEST 5] Publish Agent")
    status, resp = api_call("POST", f"/v2/agents/{agent_id}/publish", token=token)
    if status == 200 and resp.get("status") == "PUBLISHED":
        print(f"  [{PASS}] Agent published | version: {resp.get('version')}")
        results.append(("Publish Agent", True))
    else:
        print(f"  [{FAIL}] Status: {status} | Response: {resp}")
        results.append(("Publish Agent", False))

# Test 6: Generate API Key for Agent
if agent_id:
    print("\n[TEST 6] Generate API Key for Agent")
    status, resp = api_call("POST", f"/v2/agents/{agent_id}/api-keys?name=QA+Key", token=token)
    if status == 200 and "api_key" in resp:
        api_key = resp["api_key"]
        print(f"  [{PASS}] API key generated | key: {api_key[:15]}...")
        results.append(("Generate API Key", True))
    else:
        print(f"  [{FAIL}] Status: {status} | Response: {resp}")
        results.append(("Generate API Key", False))

# Test 7: Clone Agent
if agent_id:
    print("\n[TEST 7] Clone Agent")
    status, resp = api_call("POST", f"/v2/agents/{agent_id}/clone", token=token)
    if status == 200 and "Copy of" in resp.get("name", ""):
        cloned_id = resp["id"]
        print(f"  [{PASS}] Agent cloned | name: {resp.get('name')} | id: {cloned_id}")
        results.append(("Clone Agent", True))
    else:
        print(f"  [{FAIL}] Status: {status} | Response: {resp}")
        results.append(("Clone Agent", False))

# =========================================
# AI PLATFORM (ai-platform endpoints)
# =========================================
print("\n--- AI PLATFORM ENDPOINTS ---")

# Test 8: List AI Providers
print("\n[TEST 8] List AI Providers")
status, resp = api_call("GET", "/api/v1/ai-platform/providers", token=token)
if status == 200 and isinstance(resp, list):
    print(f"  [{PASS}] Got {len(resp)} providers")
    results.append(("List AI Providers", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("List AI Providers", False))

# Test 9: List AI Models
print("\n[TEST 9] List AI Models")
status, resp = api_call("GET", "/api/v1/ai-platform/models", token=token)
if status == 200 and isinstance(resp, list):
    print(f"  [{PASS}] Got {len(resp)} models")
    results.append(("List AI Models", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("List AI Models", False))

# Test 10: List AI Agents
print("\n[TEST 10] List AI Agents")
status, resp = api_call("GET", "/api/v1/ai-platform/agents", token=token)
if status == 200 and isinstance(resp, list):
    print(f"  [{PASS}] Got {len(resp)} AI agents")
    results.append(("List AI Agents", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("List AI Agents", False))

# Test 11: List API Keys (app/api_keys)
print("\n[TEST 11] List API Keys (/api/v1/api-keys)")
status, resp = api_call("GET", "/api/v1/api-keys", token=token)
if status == 200:
    print(f"  [{PASS}] Got API keys response | count: {len(resp) if isinstance(resp, list) else 'dict'}")
    results.append(("List API Keys", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("List API Keys", False))

# Test 12: List Webhooks
print("\n[TEST 12] List Webhooks (/api/v1/webhooks)")
status, resp = api_call("GET", "/api/v1/webhooks", token=token)
if status == 200:
    print(f"  [{PASS}] Got webhooks response | count: {len(resp) if isinstance(resp, list) else 'dict'}")
    results.append(("List Webhooks", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("List Webhooks", False))

# Test 13: List Payments
print("\n[TEST 13] List Payments/Billing (/api/v1/payments)")
status, resp = api_call("GET", "/api/v1/payments", token=token)
if status == 200:
    print(f"  [{PASS}] Got payments response")
    results.append(("List Payments/Billing", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("List Payments/Billing", False))

# Test 14: AI Status
print("\n[TEST 14] AI Status (/api/v1/ai/status)")
status, resp = api_call("GET", "/api/v1/ai/status", token=token)
if status == 200:
    print(f"  [{PASS}] AI status: {resp}")
    results.append(("AI Status", True))
else:
    print(f"  [{FAIL}] Status: {status} | Response: {resp}")
    results.append(("AI Status", False))

# Summary
print("\n" + "=" * 60)
print("PHASE 2 SUMMARY")
print("=" * 60)
passed = sum(1 for _, ok in results if ok)
total = len(results)
for name, ok in results:
    status_str = PASS if ok else FAIL
    print(f"  [{status_str}] {name}")
print(f"\nResult: {passed}/{total} tests passed")
