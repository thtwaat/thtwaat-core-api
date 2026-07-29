import warnings; warnings.filterwarnings('ignore')
import json
import urllib.request
import urllib.error

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
    except Exception as e:
        return 500, {"error": str(e)}

print("Login as admin")
status, resp = api_call("POST", "/api/v1/auth/login", {"email": "admin@thtwaat.com", "password": "Admin123!"})
if status != 200:
    print("Login Failed", resp)
    exit(1)
token = resp["access_token"]
print("Logged in!")

print("\n1. Get Agents to find an agent_id")
status, resp = api_call("GET", "/v2/agents", token=token)
if status != 200 or not resp:
    print("Failed to get agents", resp)
    exit(1)
agent_id = resp[0]["id"]
print(f"Using Agent: {agent_id}")

print("\n2. Create Conversation")
status, resp = api_call("POST", "/v2/conversations", {"agent_id": agent_id, "title": "Test Chat"}, token=token)
if status != 201:
    print("Failed to create conv", status, resp)
    exit(1)
conv_id = resp["id"]
print(f"Created Conversation: {conv_id}")

print("\n3. List Conversations")
status, resp = api_call("GET", "/v2/conversations", token=token)
if status != 200:
    print("Failed to list convs", status, resp)
    exit(1)
print(f"Listed {len(resp)} conversations. Found newly created: {any(c['id'] == conv_id for c in resp)}")

print("\n4. Send Message")
status, resp = api_call("POST", f"/v2/conversations/{conv_id}/messages", {"content": "Hello! What can you do?"}, token=token)
if status != 200:
    print("Failed to send message", status, resp)
    exit(1)
print(f"Sent message. AI Response: {resp.get('assistant_message', {}).get('content')}")

print("\n5. Get Conversation Detail")
status, resp = api_call("GET", f"/v2/conversations/{conv_id}", token=token)
if status != 200:
    print("Failed to get conv detail", status, resp)
    exit(1)
print(f"Conversation detail retrieved. Messages count: {len(resp.get('messages', []))}")

print("\n6. Delete Conversation")
status, resp = api_call("DELETE", f"/v2/conversations/{conv_id}", token=token)
if status != 204:
    print("Failed to delete conv", status, resp)
    exit(1)
print("Deleted successfully!")
