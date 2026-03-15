"""
CampaignX — Pydantic schemas for request/response validation.
Response schemas match the CampaignX API /api/v1/get_report structure.
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ─── Request Schemas ──────────────────────────────────────────────────────────


class CampaignBriefRequest(BaseModel):
    """Payload to submit a new campaign brief."""
    brief: str = Field(..., min_length=5, description="Natural language campaign brief")
    target_segment: Optional[str] = Field(None, description="E.g. 'female_seniors', 'young_professionals'")
    product_name: Optional[str] = Field(None, description="Product to promote, e.g. 'XDeposit'")


class SimulatorRunRequest(BaseModel):
    """Trigger a local simulation run for a campaign."""
    campaign_id: str
    recipient_count: int = Field(default=200, ge=10, le=5000, description="Number of mock recipients")
    seed: Optional[int] = Field(None, description="Random seed for deterministic runs")


# ─── CampaignX API Mirror — /api/v1/get_report ───────────────────────────────


class ReportEntry(BaseModel):
    """
    Single entry in the /api/v1/get_report array.
    Each entry represents one email event (delivery, open, or click).
    """
    campaign_id: str
    email_id: str
    recipient: str
    event_type: Literal["EO", "EC"]  # EO = Email Open, EC = Email Click
    status: Literal["delivered", "opened", "clicked", "bounced"]
    timestamp: datetime


class ReportSummary(BaseModel):
    """Aggregated metrics computed from the raw report entries."""
    total_sent: int
    total_opened: int
    total_clicked: int
    total_bounced: int
    open_rate: float = Field(..., ge=0.0, le=1.0)
    click_rate: float = Field(..., ge=0.0, le=1.0)
    weighted_score: float = Field(..., ge=0.0, le=1.0, description="0.30 * open_rate + 0.70 * click_rate")
    recommendation: Literal["OPTIMIZE", "COMPLETE"]


class SimulationResponse(BaseModel):
    """Full simulator output — raw report + aggregated summary."""
    campaign_id: str
    iteration: int
    report: List[ReportEntry]
    summary: ReportSummary


# ─── Campaign Status ─────────────────────────────────────────────────────────


class CampaignStatusResponse(BaseModel):
    """Current campaign state returned from /api/campaign/{id}/status."""
    campaign_id: str
    brief: str
    status: str
    created_at: datetime
    updated_at: datetime
    latest_score: Optional[float] = None
    iterations_run: int = 0


class CampaignCreateResponse(BaseModel):
    """Response after submitting a new campaign brief."""
    campaign_id: str
    status: str
    message: str


# ─── Agent Log ────────────────────────────────────────────────────────────────


class AgentLogEntry(BaseModel):
    """Single agent log entry for display."""
    agent_name: str
    action: str
    reasoning: Optional[str] = None
    input_data: Optional[str] = None
    output_data: Optional[str] = None
    timestamp: datetime


class AgentLogsResponse(BaseModel):
    """All logs for a campaign."""
    campaign_id: str
    logs: List[AgentLogEntry]
