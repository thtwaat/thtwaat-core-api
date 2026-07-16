from fastapi import Depends

def get_current_user_and_company():
    """Mock dependency to fix broken backend startup."""
    return {"company_id": "mock_company_id", "user_id": "mock_user_id"}
