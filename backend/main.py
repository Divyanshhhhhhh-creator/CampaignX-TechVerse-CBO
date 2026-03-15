"""
CampaignX — FastAPI Application.

Provides async routes for:
  • Campaign brief submission and status tracking
  • Local Gamification Engine (simulator) execution
  • Agent interaction log retrieval
  • Pipeline control with Human-in-the-Loop (HIL) approval
  • Health check
"""

import asyncio
import json
import uuid
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
from agents.graph import get_pipeline_nodes
from agents.optimizer import identify_micro_segments, generate_optimization_directives, _generate_sub_segments


# ─── Lifespan ─────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load env vars and create DB tables on startup."""
    from dotenv import load_dotenv
    load_dotenv()
    
    # Verify required env vars are loaded
    if not os.getenv("CAMPAIGNX_API_KEY"):
        print("WARNING: CAMPAIGNX_API_KEY not found in environment.")
    if not os.getenv("GEMINI_API_KEY"):
        print("WARNING: GEMINI_API_KEY not found in environment.")
        
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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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


# ─── Pipeline Control (Human-in-the-Loop) ────────────────────────────────────

# In-memory pipeline state store
# In production, use Redis or a DB table
_pipeline_states: Dict[str, Dict[str, Any]] = {}


class PipelineRunRequest(BaseModel):
    campaign_id: str


class PipelineApproveRequest(BaseModel):
    scheduled_send_time: Optional[str] = None


def _simulate_agent_execution(campaign_id: str, brief: str, target_segment: str, product_name: str):
    """
    Simulates the LangGraph pipeline execution node-by-node.
    Stores state snapshots in _pipeline_states so the frontend can poll.
    """
    import time
    from agents.graph import PIPELINE_NODES

    state = _pipeline_states.get(campaign_id, {})
    state["status"] = "running"
    state["campaign_id"] = campaign_id
    state["brief"] = brief
    state["target_segment"] = target_segment
    state["product_name"] = product_name
    state["logs"] = []
    state["errors"] = []
    state["started_at"] = datetime.now(timezone.utc).isoformat()

    nodes_to_run = ["coordinator", "strategist", "creative", "compliance"]

    for node_id in nodes_to_run:
        if state.get("status") == "cancelled":
            break

        state["active_node"] = node_id
        node_info = next((n for n in PIPELINE_NODES if n["id"] == node_id), {})
        state["logs"].append({
            "agent": node_id,
            "action": f"{node_id}_started",
            "detail": f"{node_info.get('label', node_id)} is processing...",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_data": json.dumps({
                "brief": brief,
                "target_segment": target_segment,
                "product_name": product_name,
                "node": node_id,
            }),
            "output_data": None,
        })
        _pipeline_states[campaign_id] = state

        # Simulate processing time
        time.sleep(1.5)

        # Simulate node output
        if node_id == "coordinator":
            state["plan"] = {
                "product": product_name or "XDeposit",
                "segment": target_segment or "all",
                "tone": "professional",
                "value_props": ["High interest rates", "Secure deposits", "Flexible tenure"],
                "channel": "email",
                "objective": brief[:200],
                "interest_rate_bonus": "+1.25%",
            }
            output = state["plan"]
        elif node_id == "strategist":
            state["recipient_emails"] = [
                f"customer_{i}@example.com" for i in range(1, 151)
            ]
            state["cohort_id"] = f"cohort_{campaign_id[:6]}"
            output = {
                "cohort_id": state["cohort_id"],
                "recipient_count": len(state["recipient_emails"]),
                "segment": target_segment or "all",
            }
        elif node_id == "creative":
            state["email_subject"] = f"Unlock Premium Returns with {product_name or 'XDeposit'} — Exclusive Offer Inside"
            state["email_body"] = (
                f"<p>Dear Valued Customer,</p>"
                f"<p>We're thrilled to introduce <b>{product_name or 'XDeposit'}</b> — "
                f"your pathway to <i>smarter financial growth</i>. 💰</p>"
                f"<p><b>Key Benefits:</b></p>"
                f"<ul>"
                f"<li>📈 <b>High interest rates</b> with +1.25% bonus</li>"
                f"<li>🔒 <b>Secure deposits</b> backed by RBI guarantee</li>"
                f"<li>⏰ <b>Flexible tenure</b> from 1 to 5 years</li>"
                f"</ul>"
                f"<p>🎯 <i>Limited time offer for our valued {target_segment or 'customers'}!</i></p>"
                f'<p><u><a href="https://superbfsi.com/xdeposit/explore/">✨ Explore {product_name or "XDeposit"} Now →</a></u></p>'
                f"<p>Warm regards,<br><i>SuperBFSI Team</i> 🏦</p>"
            )
            state["content_variants"] = [
                {"subject": f"Don't Miss Out — {product_name or 'XDeposit'} Premium Returns", "body": state["email_body"]},
            ]
            output = {
                "subject": state["email_subject"],
                "body_length": len(state["email_body"]),
                "variants_count": len(state["content_variants"]),
            }
        elif node_id == "compliance":
            state["compliance_approved"] = True
            state["compliance_issues"] = []
            output = {
                "approved": True,
                "issues": [],
                "checks_passed": ["english_only", "url_validation", "prohibited_language", "html_formatting"],
            }

        state["logs"][-1]["output_data"] = json.dumps(output)
        state["logs"][-1]["action"] = f"{node_id}_completed"
        state["logs"][-1]["detail"] = f"{node_info.get('label', node_id)} completed successfully. ✅"
        _pipeline_states[campaign_id] = state

    # After all agents, pause at HIL gate
    if state.get("status") != "cancelled":
        state["active_node"] = "hil_gate"
        state["status"] = "awaiting_approval"
        state["iteration"] = state.get("iteration", 1)
        state["logs"].append({
            "agent": "hil_gate",
            "action": "awaiting_human_approval",
            "detail": f"Pipeline paused. Awaiting human approval before execution (iteration {state.get('iteration', 1)}). 👤",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_data": json.dumps({
                "email_subject": state.get("email_subject", ""),
                "recipients_count": len(state.get("recipient_emails", [])),
                "compliance_approved": state.get("compliance_approved", False),
                "iteration": state.get("iteration", 1),
            }),
            "output_data": None,
        })
        _pipeline_states[campaign_id] = state


@app.post("/api/pipeline/run")
async def run_pipeline(req: PipelineRunRequest, db: AsyncSession = Depends(get_db)):
    """
    Start the agentic pipeline for a campaign.
    Runs agents sequentially, pausing at the HIL gate before execution.
    """
    # Verify campaign exists
    result = await db.execute(select(Campaign).where(Campaign.id == req.campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{req.campaign_id}' not found")

    # Initialize pipeline state
    _pipeline_states[req.campaign_id] = {
        "status": "starting",
        "active_node": None,
        "campaign_id": req.campaign_id,
        "logs": [],
    }

    # Update campaign status
    campaign.status = "pipeline_running"
    await db.commit()

    # Run in background thread (simulated sequential execution)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        None,
        _simulate_agent_execution,
        req.campaign_id,
        campaign.brief,
        campaign.target_segment or "",
        campaign.product_name or "",
    )

    return {
        "campaign_id": req.campaign_id,
        "status": "pipeline_started",
        "message": "Pipeline started. Poll /api/pipeline/state/{id} for updates.",
    }


@app.get("/api/pipeline/state/{campaign_id}")
async def get_pipeline_state(campaign_id: str):
    """Get current pipeline state including active node, logs, and generated content."""
    state = _pipeline_states.get(campaign_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"No pipeline state for campaign '{campaign_id}'")

    return {
        "campaign_id": campaign_id,
        "status": state.get("status", "unknown"),
        "active_node": state.get("active_node"),
        "logs": state.get("logs", []),
        "email_subject": state.get("email_subject"),
        "email_body": state.get("email_body"),
        "recipient_emails": state.get("recipient_emails", []),
        "plan": state.get("plan"),
        "compliance_approved": state.get("compliance_approved"),
        "compliance_issues": state.get("compliance_issues", []),
        "content_variants": state.get("content_variants", []),
        "send_result": state.get("send_result"),
        "scheduled_send_time": state.get("scheduled_send_time"),
        "errors": state.get("errors", []),
        # Optimizer fields
        "iteration": state.get("iteration", 1),
        "optimization_action": state.get("optimization_action"),
        "optimization_history": state.get("optimization_history", []),
        "micro_segments": state.get("micro_segments", []),
        "optimization_directives": state.get("optimization_directives", ""),
    }


@app.post("/api/pipeline/approve/{campaign_id}")
async def approve_pipeline(campaign_id: str, req: PipelineApproveRequest = None, db: AsyncSession = Depends(get_db)):
    """Approve and resume the pipeline for execution, then auto-trigger optimization."""
    state = _pipeline_states.get(campaign_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"No pipeline state for campaign '{campaign_id}'")

    if state.get("status") != "awaiting_approval":
        raise HTTPException(status_code=400, detail=f"Pipeline is not awaiting approval (current: {state.get('status')})")

    send_time = (req.scheduled_send_time if req and req.scheduled_send_time
                 else datetime.now(timezone.utc).isoformat())

    state["human_approved"] = True
    state["scheduled_send_time"] = send_time
    state["active_node"] = "execution"
    state["status"] = "executing"
    state["logs"].append({
        "agent": "hil_gate",
        "action": "human_approved",
        "detail": f"Human approved campaign execution (iteration {state.get('iteration', 1)}). Scheduled for {send_time}. ✅",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_data": json.dumps({"scheduled_send_time": send_time, "iteration": state.get("iteration", 1)}),
        "output_data": json.dumps({"approved": True}),
    })

    # Simulate execution
    recipients = state.get("recipient_emails", [])
    state["send_result"] = {
        "status": "sent",
        "recipients_count": len(recipients),
        "subject": state.get("email_subject", ""),
        "scheduled_send_time": send_time,
        "message": f"Campaign sent to {len(recipients)} recipients.",
    }
    state["logs"].append({
        "agent": "execution",
        "action": "campaign_sent",
        "detail": f"Campaign sent to {len(recipients)} recipients. 🚀",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_data": json.dumps({"recipients_count": len(recipients)}),
        "output_data": json.dumps(state["send_result"]),
    })
    _pipeline_states[campaign_id] = state

    # ── Auto-trigger Optimizer Agent ──────────────────────────────────────
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _run_optimizer_loop, campaign_id)

    # Update campaign DB status
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if campaign:
        campaign.status = "optimizing"
        await db.commit()

    return {"status": "approved", "send_result": state["send_result"]}


@app.post("/api/pipeline/reject/{campaign_id}")
async def reject_pipeline(campaign_id: str, db: AsyncSession = Depends(get_db)):
    """Reject and abort the pipeline."""
    state = _pipeline_states.get(campaign_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"No pipeline state for campaign '{campaign_id}'")

    if state.get("status") != "awaiting_approval":
        raise HTTPException(status_code=400, detail=f"Pipeline is not awaiting approval (current: {state.get('status')})")

    state["human_approved"] = False
    state["status"] = "rejected"
    state["active_node"] = None
    state["logs"].append({
        "agent": "hil_gate",
        "action": "human_rejected",
        "detail": "Human rejected the campaign. Pipeline aborted. ❌",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_data": None,
        "output_data": json.dumps({"approved": False}),
    })
    _pipeline_states[campaign_id] = state

    # Update campaign DB status
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if campaign:
        campaign.status = "rejected"
        await db.commit()

    return {"status": "rejected", "message": "Campaign rejected and pipeline aborted."}


@app.get("/api/pipeline/nodes")
async def get_nodes():
    """Return the ordered list of pipeline agent nodes for frontend visualization."""
    return get_pipeline_nodes()


# ─── Autonomous Optimizer Loop ────────────────────────────────────────────────


def _run_optimizer_loop(campaign_id: str):
    """
    Background function: Runs the autonomous optimization loop.

    After campaign execution, this:
      1. Runs the simulator to generate performance data
      2. Evaluates metrics against the 70/30 heuristic
      3. Identifies underperforming micro-segments
      4. If below threshold → re-generates creative content and pauses at HIL
      5. If meets threshold or max iterations → marks as complete

    This runs in a thread via loop.run_in_executor().
    """
    import time
    from simulator import (
        simulate_campaign,
        evaluate_campaign as eval_campaign,
        generate_mock_recipients as gen_recipients,
        OPTIMIZATION_THRESHOLD as OPT_THRESHOLD,
        MAX_ITERATIONS as MAX_ITER,
    )

    state = _pipeline_states.get(campaign_id)
    if not state:
        return

    iteration = state.get("iteration", 1)
    target_segment = state.get("plan", {}).get("segment", "general")
    product_name = state.get("product_name", state.get("plan", {}).get("product", "XDeposit"))
    opt_history = list(state.get("optimization_history", []))

    # Set optimizer as active
    state["active_node"] = "optimizer"
    state["status"] = "optimizing"
    state["logs"].append({
        "agent": "optimizer",
        "action": "optimization_started",
        "detail": f"🔄 Optimizer Agent activated. Starting performance analysis (iteration {iteration})...",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_data": json.dumps({"iteration": iteration, "target_segment": target_segment}),
        "output_data": None,
    })
    _pipeline_states[campaign_id] = state

    # Simulate processing time
    time.sleep(2)

    # ── Step 1: Run simulation to get performance data ────────────────
    recipient_emails = state.get("recipient_emails", [])
    recipient_count = len(recipient_emails) if recipient_emails else 200

    recipients = gen_recipients(count=recipient_count, segment=target_segment)

    # Add sub-segment variety for micro-segment analysis
    sub_segments = _generate_sub_segments(target_segment, recipients)

    prev_open = opt_history[-1]["open_rate"] if opt_history else None
    prev_click = opt_history[-1]["click_rate"] if opt_history else None

    report_entries = simulate_campaign(
        campaign_id=campaign_id,
        recipients=sub_segments,
        iteration=iteration,
        previous_open_rate=prev_open,
        previous_click_rate=prev_click,
    )

    metrics = eval_campaign(report_entries)

    state["logs"].append({
        "agent": "optimizer",
        "action": "metrics_evaluated",
        "detail": (
            f"📊 Metrics: Open={metrics['open_rate']:.2%}, "
            f"Click={metrics['click_rate']:.2%}, "
            f"Score={metrics['weighted_score']:.4f} (threshold={OPT_THRESHOLD})"
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_data": json.dumps({"total_sent": metrics["total_sent"]}),
        "output_data": json.dumps(metrics),
    })
    _pipeline_states[campaign_id] = state

    time.sleep(1)

    # ── Step 2: Identify micro-segments ───────────────────────────────
    micro_segments = identify_micro_segments(report_entries, sub_segments)
    underperforming = [s for s in micro_segments if s["status"] == "underperforming"]

    state["micro_segments"] = micro_segments
    state["logs"].append({
        "agent": "optimizer",
        "action": "micro_segments_analyzed",
        "detail": (
            f"🔬 Identified {len(micro_segments)} micro-segment(s): "
            f"{len(underperforming)} underperforming, "
            f"{len(micro_segments) - len(underperforming)} optimized."
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_data": None,
        "output_data": json.dumps(micro_segments),
    })

    # Record history
    history_entry = {
        "iteration": iteration,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "open_rate": metrics["open_rate"],
        "click_rate": metrics["click_rate"],
        "weighted_score": metrics["weighted_score"],
        "total_sent": metrics["total_sent"],
        "total_opened": metrics["total_opened"],
        "total_clicked": metrics["total_clicked"],
        "micro_segments_count": len(micro_segments),
        "underperforming_count": len(underperforming),
        "recommendation": metrics["recommendation"],
    }
    opt_history.append(history_entry)
    state["optimization_history"] = opt_history

    _pipeline_states[campaign_id] = state
    time.sleep(1)

    # ── Step 3: Decision — REOPTIMIZE or COMPLETE ─────────────────────
    if metrics["weighted_score"] >= OPT_THRESHOLD or iteration >= MAX_ITER:
        # Optimization complete
        reason = (
            f"score {metrics['weighted_score']:.4f} ≥ {OPT_THRESHOLD}"
            if metrics["weighted_score"] >= OPT_THRESHOLD
            else f"max iterations ({MAX_ITER}) reached"
        )
        state["optimization_action"] = "COMPLETE"
        state["status"] = "optimization_complete"
        state["active_node"] = None
        state["logs"].append({
            "agent": "optimizer",
            "action": "optimization_complete",
            "detail": f"✅ Optimization complete ({reason}). Final score: {metrics['weighted_score']:.4f}.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_data": None,
            "output_data": json.dumps({
                "action": "COMPLETE",
                "reason": reason,
                "final_score": metrics["weighted_score"],
                "iterations_run": iteration,
            }),
        })
        _pipeline_states[campaign_id] = state
        return

    # ── Below threshold → REOPTIMIZE ──────────────────────────────────
    directives = generate_optimization_directives(micro_segments, metrics, iteration)

    state["optimization_action"] = "REOPTIMIZE"
    state["optimization_directives"] = directives
    state["iteration"] = iteration + 1
    state["logs"].append({
        "agent": "optimizer",
        "action": "reoptimize_triggered",
        "detail": (
            f"🔁 Score {metrics['weighted_score']:.4f} < {OPT_THRESHOLD}. "
            f"Triggering creative re-generation (iteration {iteration + 1})."
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_data": json.dumps({"directives": directives}),
        "output_data": json.dumps({"action": "REOPTIMIZE", "next_iteration": iteration + 1}),
    })
    _pipeline_states[campaign_id] = state

    time.sleep(1.5)

    # ── Re-run creative agent (simulated) ─────────────────────────────
    state["active_node"] = "creative"
    state["logs"].append({
        "agent": "creative",
        "action": "regenerating_content",
        "detail": f"✍️ Creative Agent regenerating optimized content for iteration {iteration + 1}...",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_data": json.dumps({"directives_length": len(directives)}),
        "output_data": None,
    })
    _pipeline_states[campaign_id] = state

    time.sleep(1.5)

    # Generate new content (simulated — in production, calls LLM)
    underperf_names = ", ".join(s["segment"] for s in underperforming[:2]) if underperforming else target_segment
    state["email_subject"] = (
        f"[v{iteration + 1}] Exclusive {product_name} Offer — Tailored for {underperf_names}"
    )
    state["email_body"] = (
        f"<p>Dear Valued Customer,</p>"
        f"<p>Based on our latest insights, we've crafted a <b>personalized offer</b> "
        f"just for <i>{underperf_names}</i>. 🎯</p>"
        f"<p><b>Why {product_name}?</b></p>"
        f"<ul>"
        f"<li>📈 <b>Superior returns</b> with competitive rates</li>"
        f"<li>🔒 <b>Bank-grade security</b> for your peace of mind</li>"
        f"<li>⏰ <b>Flexible options</b> tailored to your needs</li>"
        f"</ul>"
        f"<p>🎯 <i>This exclusive offer is limited — act now!</i></p>"
        f'<p><u><a href="https://superbfsi.com/xdeposit/explore/">✨ Claim Your {product_name} Offer →</a></u></p>'
        f"<p>Warm regards,<br><i>SuperBFSI Team</i> 🏦</p>"
    )
    state["logs"][-1]["output_data"] = json.dumps({
        "subject": state["email_subject"],
        "body_length": len(state["email_body"]),
    })
    state["logs"][-1]["detail"] = f"✍️ Creative Agent generated optimized content v{iteration + 1}. ✅"
    _pipeline_states[campaign_id] = state

    time.sleep(1)

    # ── Re-run compliance (simulated) ─────────────────────────────────
    state["active_node"] = "compliance"
    state["logs"].append({
        "agent": "compliance",
        "action": "compliance_recheck",
        "detail": f"🛡️ Compliance re-checking optimized content...",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_data": json.dumps({"iteration": iteration + 1}),
        "output_data": None,
    })
    _pipeline_states[campaign_id] = state

    time.sleep(1)

    state["compliance_approved"] = True
    state["compliance_issues"] = []
    state["logs"][-1]["output_data"] = json.dumps({"approved": True, "issues": []})
    state["logs"][-1]["detail"] = "🛡️ Compliance approved the optimized content. ✅"
    _pipeline_states[campaign_id] = state

    # ── Pause at HIL gate for re-approval ─────────────────────────────
    state["active_node"] = "hil_gate"
    state["status"] = "awaiting_approval"
    state["human_approved"] = False
    state["logs"].append({
        "agent": "hil_gate",
        "action": "awaiting_human_approval",
        "detail": (
            f"Pipeline paused. Awaiting human approval for optimized variant "
            f"(iteration {iteration + 1}). 👤"
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_data": json.dumps({
            "email_subject": state.get("email_subject", ""),
            "recipients_count": len(state.get("recipient_emails", [])),
            "iteration": iteration + 1,
        }),
        "output_data": None,
    })
    _pipeline_states[campaign_id] = state


@app.post("/api/optimizer/start/{campaign_id}")
async def start_optimization(campaign_id: str, db: AsyncSession = Depends(get_db)):
    """Manually trigger the autonomous optimization loop for a completed campaign."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")

    state = _pipeline_states.get(campaign_id)
    if not state:
        raise HTTPException(status_code=400, detail="No pipeline state. Run the pipeline first.")

    if state.get("status") not in ("completed", "optimization_complete"):
        raise HTTPException(
            status_code=400,
            detail=f"Campaign must be completed to optimize (current: {state.get('status')})"
        )

    # Reset for optimization
    state["iteration"] = state.get("iteration", 1)
    state["optimization_history"] = state.get("optimization_history", [])

    # Run optimizer in background
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _run_optimizer_loop, campaign_id)

    campaign.status = "optimizing"
    await db.commit()

    return {
        "campaign_id": campaign_id,
        "status": "optimization_started",
        "message": "Autonomous optimization loop started. Poll /api/optimizer/status for updates.",
    }


@app.get("/api/optimizer/status/{campaign_id}")
async def get_optimization_status(campaign_id: str):
    """Get the current optimization loop status, iterations, and micro-segments."""
    state = _pipeline_states.get(campaign_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"No pipeline state for campaign '{campaign_id}'")

    return {
        "campaign_id": campaign_id,
        "status": state.get("status", "unknown"),
        "active_node": state.get("active_node"),
        "iteration": state.get("iteration", 1),
        "optimization_action": state.get("optimization_action"),
        "optimization_history": state.get("optimization_history", []),
        "micro_segments": state.get("micro_segments", []),
        "optimization_directives": state.get("optimization_directives", ""),
        "email_subject": state.get("email_subject"),
        "email_body": state.get("email_body"),
        "logs": state.get("logs", []),
    }
