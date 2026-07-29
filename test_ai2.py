import requests

login_res = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"email": "admin@thtwaat.com", "password": "Admin123!"}
)
token = login_res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

chat_res = requests.post(
    "http://localhost:8000/api/v1/ai/chat",
    headers=headers,
    json={
        "messages": [{"role": "user", "content": "hello"}],
        "model": "gemini-1.5-flash",
        "provider": "gemini"
    }
)
print("Chat status:", chat_res.status_code)
print("Chat body:", chat_res.text)
