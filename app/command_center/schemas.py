from pydantic import BaseModel
from typing import Optional

class DashboardResponse(BaseModel):
    """
    Response schema for the Command Center Dashboard.
    Fields are Optional to allow returning null/0 for metrics that are not yet available.
    """
    revenue: Optional[float] = None
    mrr: Optional[float] = None
    customers: Optional[int] = None
    active_projects: Optional[int] = None
    leads: Optional[int] = None
    conversion: Optional[float] = None
    ai_tasks: Optional[int] = None
    human_escalations: Optional[int] = None
    ai_cost: Optional[float] = None
