from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


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


class CeoAnalysisResponse(BaseModel):
    """Read-only AI CEO advisory output. Advisory only — no actions executed."""

    generated_at: datetime
    metrics_snapshot: DashboardResponse
    business_status: str
    problems: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    you_must_decide: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    provider: Optional[str] = None
    model_used: Optional[str] = None
