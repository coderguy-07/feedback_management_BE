from datetime import datetime
from typing import Optional
from pydantic import BaseModel

# --- Dashboard Schemas ---
class DashboardStats(BaseModel):
    totalFeedbacks: int
    verifiedFeedbacks: int
    notVerifiedFeedbacks: int
    pendingFeedbacks: int
    reviewedFeedbacks: int
    lastUpdated: datetime

class ChartData(BaseModel):
    date: str
    count: int

class PieChartData(BaseModel):
    name: str # e.g. "Poor"
    rating: int # e.g. 1
    count: int
    value: float # Percentage

# --- Workflow Schemas ---
class WorkflowUpdate(BaseModel):
    status: str
    assignedTo: Optional[str] = None
    comments: Optional[str] = None
