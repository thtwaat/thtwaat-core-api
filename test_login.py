import requests

try:
    response = requests.post(
        "http://localhost:8000/api/v1/auth/login",
        json={"email": "test@example.com", "password": "password123"}
    )
    print("Status:", response.status_code)
    print("Headers:", response.headers)
    print("Body:", response.text)
except Exception as e:
    print("Error:", e)
