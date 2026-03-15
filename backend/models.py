"""
CampaignX — SQLAlchemy ORM models.
Logs all agent interactions, decisions, and reasoning data
for hackathon bonus‑point requirements.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    hex_str: str = uuid.uuid4().hex
    return hex_str[:12]


# ─── Campaign ────────────────────────────────────────────────────────────────


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(String, primary_key=True, default=_new_id)
    brief = Column(Text, nullable=False)
    target_segment = Column(String, nullable=True)
    product_name = Column(String, nullable=True)
    status = Column(String, default="submitted")  # submitted | simulating | analysed | optimising | completed
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    logs = relationship("AgentLog", back_populates="campaign", cascade="all, delete-orphan")
    simulations = relationship("SimulationResult", back_populates="campaign", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Campaign {self.id} [{self.status}]>"


# ─── Agent Log ────────────────────────────────────────────────────────────────


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    agent_name = Column(String, nullable=False)       # planner | creative | executor | analyst | simulator
    action = Column(String, nullable=False)            # e.g. "generate_plan", "evaluate_score"
    reasoning = Column(Text, nullable=True)            # LLM reasoning / decision rationale
    input_data = Column(Text, nullable=True)           # JSON string of input context
    output_data = Column(Text, nullable=True)          # JSON string of output / result
    timestamp = Column(DateTime, default=_utcnow)

    campaign = relationship("Campaign", back_populates="logs")

    def __repr__(self) -> str:
        return f"<AgentLog {self.agent_name}:{self.action}>"


# ─── Simulation Result ───────────────────────────────────────────────────────


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    iteration = Column(Integer, default=1)
    total_sent = Column(Integer, default=0)
    total_opened = Column(Integer, default=0)
    total_clicked = Column(Integer, default=0)
    open_rate = Column(Float, default=0.0)
    click_rate = Column(Float, default=0.0)
    weighted_score = Column(Float, default=0.0)
    raw_report = Column(Text, nullable=True)           # Full JSON array matching /api/v1/get_report
    recommendation = Column(String, nullable=True)     # OPTIMIZE | COMPLETE
    timestamp = Column(DateTime, default=_utcnow)

    campaign = relationship("Campaign", back_populates="simulations")

    def __repr__(self) -> str:
        return f"<SimulationResult campaign={self.campaign_id} iter={self.iteration} score={self.weighted_score:.3f}>"
