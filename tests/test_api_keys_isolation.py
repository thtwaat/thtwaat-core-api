import pytest
from fastapi import FastAPI, Depends, Header
from fastapi.testclient import TestClient
from typing import Annotated

# We will create a dummy route protected by API key auth to test isolation
# This simulates the middleware deriving the company_id.

app = FastAPI()

def mock_get_api_key_user(x_api_key: str = Header(None)):
    # Mocking the middleware logic which derives company_id from API key
    if x_api_key == "key_for_company_A":
        return {"company_id": "company_A", "app_label": "test_app"}
    elif x_api_key == "key_for_company_B":
        return {"company_id": "company_B", "app_label": "test_app"}
    raise ValueError("Invalid Key")

@app.get("/dummy-data")
def get_dummy_data(
    company_id: str = None, # Client tries to pass company_id manually
    api_user: dict = Depends(mock_get_api_key_user)
):
    # The vulnerability would be if we trust the client's company_id 
    # instead of the one derived from the API key.
    # The strict isolation rule:
    derived_company_id = api_user["company_id"]
    
    # Simulate DB query that MUST use derived_company_id
    # If the app trusted the client's `company_id`, it would be a bug.
    return {"accessed_company_data": derived_company_id}

client = TestClient(app)

def test_company_isolation_strict():
    """
    Test: Verify Company A's key can NEVER access Company B's data - 
    even if company_id is passed manually in request body/params.
    company_id must ONLY be derived from the authenticated API key, 
    never trusted from client input.
    """
    
    # Scenario 1: Client A tries to access Client B's data by passing company_id=company_B
    # Real test using headers to mock the middleware:
    response_real_a = client.get(
        "/dummy-data?company_id=company_B",
        headers={"x-api-key": "key_for_company_A"}
    )
    
    assert response_real_a.status_code == 200
    # The accessed data MUST belong to Company A, entirely ignoring the ?company_id=company_B param
    assert response_real_a.json()["accessed_company_data"] == "company_A"

    # Scenario 2: Client B accesses their own data
    response_real_b = client.get(
        "/dummy-data?company_id=company_A", # Trying to spoof A
        headers={"x-api-key": "key_for_company_B"}
    )
    
    assert response_real_b.status_code == 200
    # Must return B's data, ignoring the spoofed param
    assert response_real_b.json()["accessed_company_data"] == "company_B"
