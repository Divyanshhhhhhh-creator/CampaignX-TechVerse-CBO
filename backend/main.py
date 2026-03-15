"""
CampaignX — FastAPI Application.

Provides async routes for:
  • Campaign brief submission and status tracking
  • Local Gamification Engine (simulator) execution
  • Agent interaction log retrieval
  • Health check
"""

import json
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, init_db
from models import AgentLog, Campaign, SimulationResult
from schemas import (
    AgentLogEntry,
    AgentLogsResponse,
    CampaignBriefRequest,
    CampaignCreateResponse,
    CampaignStatusResponse,
    ReportEntry,
    ReportSummary,
    SimulationResponse,
    SimulatorRunRequest,
)
from simulator import evaluate_campaign, run_full_simulation, simulate_optimization, generate_mock_recipients


# ─── Lifespan ─────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup."""
    await init_db()
    yield


# ─── App ──────────────────────────────────────────────────────────────────────


app = FastAPI(
    title="CampaignX Backend",
    description="Multi-agent email campaign backend with Local Gamification Engine",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health ───────────────────────────────────────────────────────────────────


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "campaignx-backend"}


# ─── Campaign CRUD ───────────────────────────────────────────────────────────


@app.post("/api/campaign/submit", response_model=CampaignCreateResponse)
async def submit_campaign(req: CampaignBriefRequest, db: AsyncSession = Depends(get_db)):
    """Submit a new campaign brief and create a DB record."""
    hex_str: str = uuid.uuid4().hex
    campaign_id = hex_str[:12]

    campaign = Campaign(
        id=campaign_id,
        brief=req.brief,
        target_segment=req.target_segment,
        product_name=req.product_name,
        status="submitted",
    )
    db.add(campaign)

    # Log the submission as an agent interaction
    log_entry = AgentLog(
        campaign_id=campaign_id,
        agent_name="system",
        action="campaign_submitted",
        reasoning="User submitted a new campaign brief for processing.",
        input_data=json.dumps(req.model_dump()),
        output_data=json.dumps({"campaign_id": campaign_id}),
    )
    db.add(log_entry)
    await db.commit()

    return CampaignCreateResponse(
        campaign_id=campaign_id,
        status="submitted",
        message="Campaign brief received. Use /api/simulator/run to test locally.",
    )


@app.get("/api/campaign/{campaign_id}/status", response_model=CampaignStatusResponse)
async def get_campaign_status(campaign_id: str, db: AsyncSession = Depends(get_db)):
    """Get the current status of a campaign."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")

    # Get latest score and iteration count
    sim_result = await db.execute(
        select(SimulationResult)
        .where(SimulationResult.campaign_id == campaign_id)
        .order_by(SimulationResult.iteration.desc())
        .limit(1)
    )
    latest_sim = sim_result.scalar_one_or_none()

    count_result = await db.execute(
        select(func.count())
        .select_from(SimulationResult)
        .where(SimulationResult.campaign_id == campaign_id)
    )
    iterations_run = count_result.scalar() or 0

    return CampaignStatusResponse(
        campaign_id=campaign.id,
        brief=campaign.brief,
        status=campaign.status,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        latest_score=latest_sim.weighted_score if latest_sim else None,
        iterations_run=iterations_run,
    )


@app.get("/api/campaign/{campaign_id}/logs", response_model=AgentLogsResponse)
async def get_campaign_logs(campaign_id: str, db: AsyncSession = Depends(get_db)):
    """Get all agent interaction logs for a campaign."""
    # Verify campaign exists
    campaign_check = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    if not campaign_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")

    result = await db.execute(
        select(AgentLog)
        .where(AgentLog.campaign_id == campaign_id)
        .order_by(AgentLog.timestamp.asc())
    )
    logs = result.scalars().all()

    return AgentLogsResponse(
        campaign_id=campaign_id,
        logs=[
            AgentLogEntry(
                agent_name=log.agent_name,
                action=log.action,
                reasoning=log.reasoning,
                input_data=log.input_data,
                output_data=log.output_data,
                timestamp=log.timestamp,
            )
            for log in logs
        ],
    )


# ─── Simulator ────────────────────────────────────────────────────────────────


@app.post("/api/simulator/run", response_model=SimulationResponse)
async def run_simulation(req: SimulatorRunRequest, db: AsyncSession = Depends(get_db)):
    """
    Run the Local Gamification Engine for a campaign.
    Returns mock EO/EC data matching the /api/v1/get_report schema,
    with a performance summary using 70 % click / 30 % open weighting.
    """
    # Verify campaign exists
    result = await db.execute(select(Campaign).where(Campaign.id == req.campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{req.campaign_id}' not found")

    # Check if there's a previous iteration to build upon
    prev_result = await db.execute(
        select(SimulationResult)
        .where(SimulationResult.campaign_id == req.campaign_id)
        .order_by(SimulationResult.iteration.desc())
        .limit(1)
    )
    prev_sim = prev_result.scalar_one_or_none()

    if prev_sim:
        # Optimization iteration
        iteration = prev_sim.iteration + 1
        # Regenerate recipients (in prod these would persist)
        recipients = generate_mock_recipients(
            req.recipient_count,
            campaign.target_segment,
        )
        report_entries, summary = simulate_optimization(
            campaign_id=req.campaign_id,
            recipients=recipients,
            previous_open_rate=prev_sim.open_rate,
            previous_click_rate=prev_sim.click_rate,
            iteration=iteration,
            seed=req.seed,
        )
    else:
        # First iteration
        sim_result = run_full_simulation(
            campaign_id=req.campaign_id,
            recipient_count=req.recipient_count,
            segment=campaign.target_segment,
            seed=req.seed,
        )
        iteration = 1
        report_entries = sim_result["report"]
        summary = sim_result["summary"]

    # Persist simulation result
    sim_record = SimulationResult(
        campaign_id=req.campaign_id,
        iteration=iteration,
        total_sent=summary["total_sent"],
        total_opened=summary["total_opened"],
        total_clicked=summary["total_clicked"],
        open_rate=summary["open_rate"],
        click_rate=summary["click_rate"],
        weighted_score=summary["weighted_score"],
        raw_report=json.dumps(report_entries),
        recommendation=summary["recommendation"],
    )
    db.add(sim_record)

    # Log simulator action
    log_entry = AgentLog(
        campaign_id=req.campaign_id,
        agent_name="simulator",
        action=f"simulation_iteration_{iteration}",
        reasoning=(
            f"Local Gamification Engine ran iteration {iteration}. "
            f"Open rate: {summary['open_rate']:.2%}, Click rate: {summary['click_rate']:.2%}, "
            f"Weighted score: {summary['weighted_score']:.4f}. "
            f"Recommendation: {summary['recommendation']}."
        ),
        input_data=json.dumps({
            "campaign_id": req.campaign_id,
            "recipient_count": req.recipient_count,
            "seed": req.seed,
            "iteration": iteration,
        }),
        output_data=json.dumps(summary),
    )
    db.add(log_entry)

    # Update campaign status
    campaign.status = "simulated" if summary["recommendation"] == "COMPLETE" else "optimizing"
    await db.commit()

    # Build response
    parsed_entries = [ReportEntry(**entry) for entry in report_entries]

    return SimulationResponse(
        campaign_id=req.campaign_id,
        iteration=iteration,
        report=parsed_entries,
        summary=ReportSummary(**summary),
    )


@app.get("/api/simulator/report/{campaign_id}", response_model=SimulationResponse)
async def get_simulation_report(campaign_id: str, iteration: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    """
    Retrieve a stored simulation report.
    Defaults to the latest iteration if not specified.
    """
    query = select(SimulationResult).where(SimulationResult.campaign_id == campaign_id)

    if iteration is not None:
        query = query.where(SimulationResult.iteration == iteration)
    else:
        query = query.order_by(SimulationResult.iteration.desc()).limit(1)

    result = await db.execute(query)
    sim = result.scalar_one_or_none()

    if not sim:
        raise HTTPException(
            status_code=404,
            detail=f"No simulation found for campaign '{campaign_id}'"
            + (f" iteration {iteration}" if iteration else ""),
        )

    report_entries = json.loads(sim.raw_report) if sim.raw_report else []
    parsed_entries = [ReportEntry(**entry) for entry in report_entries]

    # Compute total_bounced from the raw report data
    bounced_ids = {e["email_id"] for e in report_entries if e.get("status") == "bounced"}
    total_bounced = len(bounced_ids)

    return SimulationResponse(
        campaign_id=campaign_id,
        iteration=sim.iteration,
        report=parsed_entries,
        summary=ReportSummary(
            total_sent=sim.total_sent,
            total_opened=sim.total_opened,
            total_clicked=sim.total_clicked,
            total_bounced=total_bounced,
            open_rate=sim.open_rate,
            click_rate=sim.click_rate,
            weighted_score=sim.weighted_score,
            recommendation=sim.recommendation or "COMPLETE",
        ),
    )



# ─── List All Campaigns ──────────────────────────────────────────────────────


@app.get("/api/campaigns")
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    """List all campaigns with basic info."""
    result = await db.execute(select(Campaign).order_by(Campaign.created_at.desc()))
    campaigns = result.scalars().all()
    return [
        {
            "campaign_id": c.id,
            "brief": c.brief[:100],
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in campaigns
    ]
