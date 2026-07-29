import requests
print(requests.post("http://localhost:8000/api/v1/auth/login", json={"email": "not_an_email", "password": "password123"}).text)
