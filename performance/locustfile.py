import uuid
from locust import HttpUser, task, between

class EnterpriseLoadTest(HttpUser):
    wait_time = between(1, 3)
    
    # We use a fallback if TARGET_URL isn't used automatically
    host = "http://localhost:8000"

    def on_start(self):
        # 1. Company CRUD - Create
        uid = uuid.uuid4().hex[:6]
        company_resp = self.client.post("/api/v1/companies/", json={
            "name": f"Locust Company {uid}",
            "slug": f"locust-company-{uid}",
            "domain": f"locust{uid}.com"
        })
        if company_resp.status_code == 201:
            self.company_id = company_resp.json()["id"]
        else:
            self.company_id = None

        # 2. User CRUD - Create
        if self.company_id:
            self.email = f"locust{uid}@test.com"
            self.password = "securepassword"
            user_resp = self.client.post("/api/v1/users/", json={
                "email": self.email,
                "password": self.password,
                "company_id": self.company_id,
                "first_name": "Locust",
                "last_name": "User",
                "role": "admin"
            })
            if user_resp.status_code == 201:
                self.user_id = user_resp.json()["id"]
            else:
                self.user_id = None
        else:
            self.user_id = None

        # 3. Login
        self.access_token = None
        if self.user_id:
            login_resp = self.client.post("/api/v1/auth/login", json={
                "email": self.email,
                "password": self.password
            })
            if login_resp.status_code == 200:
                self.access_token = login_resp.json()["access_token"]

        self.headers = {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}

    @task(1)
    def company_crud(self):
        if self.company_id:
            self.client.get(f"/api/v1/companies/{self.company_id}")

    @task(1)
    def user_crud(self):
        if self.user_id:
            self.client.get(f"/api/v1/users/{self.user_id}")

    @task(3)
    def products_crud(self):
        if not self.access_token:
            return
        
        # Create
        uid = uuid.uuid4().hex[:6]
        resp = self.client.post("/api/v1/products/", headers=self.headers, json={
            "name": f"Locust Product {uid}",
            "category": "Website",
            "description": "Load test product",
            "ai_enabled": False
        })
        if resp.status_code == 201:
            product_id = resp.json()["id"]
            
            # Read
            self.client.get(f"/api/v1/products/{product_id}", headers=self.headers)
            
            # Update
            self.client.patch(f"/api/v1/products/{product_id}", headers=self.headers, json={
                "name": f"Updated Product {uid}"
            })
            
            # List
            self.client.get("/api/v1/products/", headers=self.headers)
            
            # Delete
            self.client.delete(f"/api/v1/products/{product_id}", headers=self.headers)
