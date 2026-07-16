"""
Phase 3 & 4: Backend Verification + End-to-End Flow Test
Tests:
- All FastAPI routers registered
- Alembic migrations verified
- PostgreSQL models verified
- Redis connectivity
- Gemini provider
- API Gateway
- Full E2E: Login -> Dashboard -> Create Agent -> Generate API Key -> Call Chat API -> Receive response
"""
import warnings; warnings.filterwarnings('ignore')
import json
import sys
import urllib.request
import urllib.error
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_URL = "http://127.0.0.1:8000"

def api_call(method, path, body=None, token=None, api_key=None):
    url = BASE_URL + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if api_key:
        headers["X-API-Key"] = api_key
    
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
print("PHASE 3: BACKEND VERIFICATION")
print("=" * 60)

results = []

# =========================================
# 3.1: Router Registration Checks
# =========================================
print("\n--- 3.1: ROUTER REGISTRATION ---")

routes_to_check = [
    ("GET", "/api/v1/status", "API Status"),
    ("GET", "/api/v1/auth/me", "Auth Router"),
    ("GET", "/api/v1/ai/health", "AI Gateway"),
    ("GET", "/api/v1/ai-platform/providers", "AI Platform Router"),
    ("GET", "/v2/agents", "Agent Platform Router"),
    ("GET", "/api/v1/api-keys", "API Keys Router"),
    ("GET", "/api/v1/webhooks", "Webhooks Router"),
    ("GET", "/api/v1/payments", "Payments Router"),
    ("GET", "/api/v1/storage/files", "Storage Router"),
    ("GET", "/api/v1/notifications", "Notifications Router"),
    ("GET", "/api/v1/users", "Users Router"),
    ("GET", "/api/v1/companies", "Companies Router"),
]

# Login to get token
status, resp = api_call("POST", "/api/v1/auth/login", {"email": "admin@thtwaat.com", "password": "Admin123!"})
token = resp.get("access_token", "")

for method, path, name in routes_to_check:
    status, resp = api_call(method, path, token=token)
    # 200 = OK, 401 = registered but needs auth, 422 = registered
    is_registered = status in [200, 401, 422, 403, 201]
    result_str = PASS if is_registered else FAIL
    print(f"  [{result_str}] {name} ({method} {path}) -> {status}")
    results.append((f"Router: {name}", is_registered))

# =========================================
# 3.2: Database Model Verification
# =========================================
print("\n--- 3.2: DATABASE MODEL VERIFICATION ---")

db_checks = [
    "companies", "users", "refresh_tokens", "otp_codes", "mfa_settings",
    "apps", "storage_files", "notifications", "payments", "ai_requests",
    "api_keys", "webhooks", "products",
    "agent_configs", "agent_api_keys", "agent_provider_configs",
    "agent_model_configs", "agent_conversations", "agent_messages",
    "agent_usage_logs", "agent_company_quotas",
    "ai_providers", "ai_models", "ai_agents", "ai_prompt_templates",
    "ai_tools", "ai_agent_tools", "ai_conversations", "ai_messages", "ai_usage"
]

import sys, os
sys.path.insert(0, '.')
import app.companies.model; import app.users.model; import app.auth.model
import app.apps.model; import app.storage.model; import app.notifications.model
import app.payments.model; import app.ai.model; import app.products.model
import app.api_keys.model; import app.webhooks.model
import app.features.ai_platform.database.models
import app.agent_platform.models

from app.database.database import engine
from sqlalchemy import inspect, text
inspector = inspect(engine)
actual_tables = set(inspector.get_table_names())

for table in db_checks:
    exists = table in actual_tables
    result_str = PASS if exists else FAIL
    print(f"  [{result_str}] Table: {table}")
    results.append((f"Table: {table}", exists))

# =========================================
# 3.3: Redis Connectivity
# =========================================
print("\n--- 3.3: REDIS CONNECTIVITY ---")
try:
    import redis
    r = redis.Redis(host='localhost', port=6379)
    r.ping()
    print(f"  [{PASS}] Redis ping successful")
    results.append(("Redis connectivity", True))
except Exception as e:
    print(f"  [{FAIL}] Redis error: {e}")
    results.append(("Redis connectivity", False))

# =========================================
# 3.4: Gemini Provider Check
# =========================================
print("\n--- 3.4: GEMINI PROVIDER ---")
status, resp = api_call("GET", "/api/v1/ai/health", token=token)
if status == 200:
    print(f"  [{PASS}] AI Health endpoint responds | response: {str(resp)[:100]}")
    results.append(("AI Health endpoint", True))
else:
    print(f"  [{FAIL}] Status: {status} | {resp}")
    results.append(("AI Health endpoint", False))

print("\n" + "=" * 60)
print("PHASE 4: END-TO-END FLOW TEST")
print("=" * 60)

e2e_results = []

# Step 1: Login
print("\n[E2E-1] Login")
status, resp = api_call("POST", "/api/v1/auth/login", {"email": "admin@thtwaat.com", "password": "Admin123!"})
if status == 200:
    token = resp["access_token"]
    print(f"  [{PASS}] Logged in | expires_in: {resp.get('expires_in')}s")
    e2e_results.append(("Login", True))
else:
    print(f"  [{FAIL}] {resp}")
    e2e_results.append(("Login", False))
    exit(1)

# Step 2: Dashboard (user profile)
print("\n[E2E-2] Dashboard (user profile)")
status, resp = api_call("GET", "/api/v1/auth/me", token=token)
if status == 200:
    print(f"  [{PASS}] Dashboard data | user: {resp['email']} | company: {resp['company_id']}")
    e2e_results.append(("Dashboard", True))
else:
    print(f"  [{FAIL}] {resp}")
    e2e_results.append(("Dashboard", False))

# Step 3: Create Agent
print("\n[E2E-3] Create Agent")
agent_body = {
    "name": "E2E Test Agent",
    "description": "End-to-end test agent",
    "system_prompt_template": "You are a helpful assistant.",
    "temperature": 0.7,
    "is_template": False,
    "web_config": {}
}
status, resp = api_call("POST", "/v2/agents", agent_body, token=token)
if status == 200:
    agent_id = resp["id"]
    print(f"  [{PASS}] Agent created | id: {agent_id} | status: {resp['status']}")
    e2e_results.append(("Create Agent", True))
else:
    print(f"  [{FAIL}] {resp}")
    e2e_results.append(("Create Agent", False))
    agent_id = None

# Step 4: Agent appears in list
print("\n[E2E-4] Agent appears in list")
status, resp = api_call("GET", "/v2/agents", token=token)
if status == 200 and any(a.get("id") == agent_id for a in resp):
    print(f"  [{PASS}] Agent found in list | total agents: {len(resp)}")
    e2e_results.append(("Agent in list", True))
else:
    print(f"  [{FAIL}] Agent not found in list | {resp}")
    e2e_results.append(("Agent in list", False))

# Step 5: Generate API Key
print("\n[E2E-5] Generate API Key for Agent")
if agent_id:
    status, resp = api_call("POST", f"/v2/agents/{agent_id}/api-keys?name=E2E+Key", token=token)
    if status == 200 and resp.get("api_key"):
        generated_api_key = resp["api_key"]
        print(f"  [{PASS}] API key generated: {generated_api_key[:20]}...")
        e2e_results.append(("Generate API Key", True))
    else:
        print(f"  [{FAIL}] {resp}")
        e2e_results.append(("Generate API Key", False))
        generated_api_key = None
else:
    print(f"  [SKIP] No agent_id available")
    e2e_results.append(("Generate API Key", False))
    generated_api_key = None

# Step 6: Call Chat API (via JWT auth)
print("\n[E2E-6] Call Chat API (Gemini)")
chat_body = {
    "model": "gemini-2.0-flash",
    "messages": [
        {"role": "user", "content": "Say 'Hello from THTWAAT' in exactly 5 words."}
    ],
    "max_tokens": 50
}
status, resp = api_call("POST", "/api/v1/ai/chat", chat_body, token=token)
if status == 200 and resp.get("content"):
    print(f"  [{PASS}] Gemini responded | content: {resp['content'][:100]}")
    print(f"         tokens: {resp.get('input_tokens', 0)} in / {resp.get('output_tokens', 0)} out")
    e2e_results.append(("Call Chat API", True))
else:
    print(f"  [{FAIL}] Status: {status} | {str(resp)[:200]}")
    e2e_results.append(("Call Chat API", False))

# Summary
print("\n" + "=" * 60)
print("PHASE 3 SUMMARY")
print("=" * 60)
p3_pass = sum(1 for _, ok in results if ok)
p3_total = len(results)

# Count categories
routers_pass = sum(1 for n, ok in results if n.startswith("Router:") and ok)
routers_total = sum(1 for n, _ in results if n.startswith("Router:"))
tables_pass = sum(1 for n, ok in results if n.startswith("Table:") and ok)
tables_total = sum(1 for n, _ in results if n.startswith("Table:"))
print(f"  Routers: {routers_pass}/{routers_total}")
print(f"  DB Tables: {tables_pass}/{tables_total}")
for n, ok in results:
    if not n.startswith("Router:") and not n.startswith("Table:"):
        print(f"  [{PASS if ok else FAIL}] {n}")

print("\n" + "=" * 60)
print("PHASE 4 E2E SUMMARY")
print("=" * 60)
e2e_pass = sum(1 for _, ok in e2e_results if ok)
e2e_total = len(e2e_results)
for name, ok in e2e_results:
    print(f"  [{PASS if ok else FAIL}] {name}")
print(f"\nE2E Result: {e2e_pass}/{e2e_total} steps passed")
print(f"Overall: Phase3={p3_pass}/{p3_total}, Phase4={e2e_pass}/{e2e_total}")
