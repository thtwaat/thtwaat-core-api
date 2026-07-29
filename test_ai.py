import requests

# 1. Login
login_res = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"email": "admin@thtwaat.com", "password": "Admin123!"}
)
if login_res.status_code != 200:
    print("Login failed", login_res.text)
    exit(1)

token = login_res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 2. Chat
chat_res = requests.post(
    "http://localhost:8000/ai/chat",
    headers=headers,
    json={
        "messages": [{"role": "user", "content": "hello"}],
        "model": "gemini-1.5-pro"
    }
)
print("Chat status:", chat_res.status_code)
print("Chat body:", chat_res.text)
