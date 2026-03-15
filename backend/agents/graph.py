"""
CampaignX — LangGraph State Machine.

Wires the agent nodes into a directed graph with Human-in-the-Loop:

    START → coordinator → strategist → creative → compliance →
                                         ↑                    │
                                         └────────────────────┘
                                         (if compliance rejects,
                                          retry creative — max 3×)
    compliance (approved) → execution (interrupt_before — HIL gate) → END

API tools are injected at graph start via the ``api_tools`` state key.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from langgraph.graph import END, StateGraph

from agents.state import CampaignState
from agents.coordinator import coordinator_node
from agents.strategist import strategist_node
from agents.creative import creative_node
from agents.compliance import compliance_node
from agents.optimizer import optimizer_node
from agents.api_discovery import discover_api_tools


# ─── Constants ────────────────────────────────────────────────────────────────

MAX_COMPLIANCE_RETRIES = 3
DEFAULT_SPEC_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "openapi_spec.json")

# Ordered list of agent nodes for pipeline visualization
PIPELINE_NODES = [
    {"id": "coordinator", "label": "🧭 Coordinator", "description": "Parses campaign brief into structured plan"},
    {"id": "strategist", "label": "📊 Strategist", "description": "Identifies target cohort from API"},
    {"id": "creative", "label": "✍️ Creative", "description": "Generates email subject & body"},
    {"id": "compliance", "label": "🛡️ Compliance", "description": "BFSI brand-safety validation"},
    {"id": "hil_gate", "label": "👤 Human Approval", "description": "Awaiting human approve/reject"},
    {"id": "execution", "label": "🚀 Execution", "description": "Sends campaign to recipients"},
    {"id": "optimizer", "label": "🔄 Optimizer", "description": "Autonomous performance optimization loop"},
]


# ─── Execution Node ─────────────────────────────────────────────────────────


def execution_node(state: CampaignState) -> Dict[str, Any]:
    """
    LangGraph node: Execute the campaign (send emails).

    This node is gated by interrupt_before — the pipeline will pause
    here until a human approves or rejects the campaign.

    Reads:  state["human_approved"], state["email_subject"], state["email_body"],
            state["recipient_emails"]
    Writes: state["send_result"], state["logs"], state["status"]
    """
    logs = list(state.get("logs", []))
    approved = state.get("human_approved", False)

    if not approved:
        logs.append({
            "agent": "execution",
            "action": "rejected",
            "detail": "Campaign was rejected by human reviewer.",
        })
        return {
            "send_result": {"status": "rejected", "reason": "Human reviewer rejected the campaign"},
            "logs": logs,
            "status": "rejected",
            "active_node": "execution",
        }

    subject = state.get("email_subject", "")
    recipients = state.get("recipient_emails", [])
    send_time = state.get("scheduled_send_time", datetime.now(timezone.utc).isoformat())

    logs.append({
        "agent": "execution",
        "action": "sending_campaign",
        "detail": f"Sending '{subject[:50]}...' to {len(recipients)} recipients at {send_time}.",
    })

    # Simulated send result (in production, this would call the actual API)
    send_result = {
        "status": "sent",
        "recipients_count": len(recipients),
        "subject": subject,
        "scheduled_send_time": send_time,
        "message": f"Campaign sent to {len(recipients)} recipients successfully.",
    }

    logs.append({
        "agent": "execution",
        "action": "campaign_sent",
        "detail": f"Campaign successfully sent to {len(recipients)} recipients. ✅",
    })

    return {
        "send_result": send_result,
        "logs": logs,
        "status": "completed",
        "active_node": "execution",
    }


# ─── Routing Function ────────────────────────────────────────────────────────


def _compliance_router(state: CampaignState) -> str:
    """
    After compliance check:
      - If approved → execution (with HIL gate)
      - If rejected and retries < max → creative (retry loop)
      - If rejected and retries >= max → END (with issues logged)
    """
    approved = state.get("compliance_approved", False)
    retries = state.get("compliance_retries", 0)

    if approved:
        return "execution"
    elif retries < MAX_COMPLIANCE_RETRIES:
        return "retry_creative"
    else:
        return "end"


def _optimizer_router(state: CampaignState) -> str:
    """
    After optimizer evaluates performance:
      - If REOPTIMIZE and iterations remain → creative (loop back)
      - If COMPLETE or max iterations → END
    """
    action = state.get("optimization_action", "COMPLETE")
    iteration = state.get("iteration", 1)

    if action == "REOPTIMIZE" and iteration <= MAX_COMPLIANCE_RETRIES + 2:
        return "reoptimize_creative"
    else:
        return "end"


# ─── Graph Builder ────────────────────────────────────────────────────────────


def build_campaign_graph() -> StateGraph:
    """
    Construct the LangGraph StateGraph for the campaign pipeline.

    Uses interrupt_before on the 'execution' node to implement
    the Human-in-the-Loop (HIL) approval gate.

    Returns a compiled graph ready for .invoke() or .stream().
    """
    graph = StateGraph(CampaignState)

    # Add nodes
    graph.add_node("coordinator", coordinator_node)
    graph.add_node("strategist", strategist_node)
    graph.add_node("creative", creative_node)
    graph.add_node("compliance", compliance_node)
    graph.add_node("execution", execution_node)
    graph.add_node("optimizer", optimizer_node)

    # Linear edges
    graph.set_entry_point("coordinator")
    graph.add_edge("coordinator", "strategist")
    graph.add_edge("strategist", "creative")
    graph.add_edge("creative", "compliance")

    # Conditional edge from compliance
    graph.add_conditional_edges(
        "compliance",
        _compliance_router,
        {
            "execution": "execution",
            "end": END,
            "retry_creative": "creative",
        },
    )

    # Execution → Optimizer (autonomous loop)
    graph.add_edge("execution", "optimizer")

    # Conditional edge from optimizer
    graph.add_conditional_edges(
        "optimizer",
        _optimizer_router,
        {
            "reoptimize_creative": "creative",
            "end": END,
        },
    )

    # Compile with interrupt_before on execution node (HIL gate)
    return graph.compile(interrupt_before=["execution"])


# ─── Convenience Runner ──────────────────────────────────────────────────────


def run_campaign_pipeline(
    brief: str,
    campaign_id: str = "",
    spec_path: str = DEFAULT_SPEC_PATH,
    base_url: str = "http://127.0.0.1:8000",
) -> Dict[str, Any]:
    """
    End-to-end campaign pipeline execution.

    1. Discovers API tools dynamically from OpenAPI spec
    2. Injects tools into state
    3. Runs the full graph: coordinator → strategist → creative → compliance
    4. Pauses at execution node (interrupt_before) for human approval

    Args:
        brief:       Natural-language campaign brief.
        campaign_id: DB campaign record ID (optional).
        spec_path:   Path to the OpenAPI spec file.
        base_url:    Base URL for the API (local simulator or production).

    Returns:
        Final state dict with all pipeline outputs.
    """
    # Dynamic API tool discovery
    api_tools = discover_api_tools(spec_path, base_url)

    # Initial state
    initial_state: CampaignState = {
        "brief": brief,
        "campaign_id": campaign_id,
        "api_tools": api_tools,
        "api_base_url": base_url,
        "iteration": 1,
        "compliance_retries": 0,
        "human_approved": False,
        "scheduled_send_time": "",
        "active_node": "coordinator",
        "logs": [],
        "errors": [],
        "status": "starting",
    }

    # Build and execute
    graph = build_campaign_graph()
    final_state = graph.invoke(initial_state)

    return final_state


def get_pipeline_nodes() -> list:
    """Return the ordered list of pipeline nodes for frontend visualization."""
    return PIPELINE_NODES


# ─── Graph Visualization Helper ──────────────────────────────────────────────


def get_graph_diagram() -> str:
    """Return a Mermaid diagram of the graph for documentation."""
    return """
graph LR
    START((Start)) --> coordinator[🧭 Coordinator]
    coordinator --> strategist[📊 Strategist]
    strategist --> creative[✍️ Creative]
    creative --> compliance{🛡️ Compliance}
    compliance -->|Approved| hil_gate{👤 HIL Gate}
    hil_gate -->|Approved| execution[🚀 Execution]
    hil_gate -->|Rejected| END((End))
    compliance -->|Rejected & retries < 3| creative
    compliance -->|Rejected & retries >= 3| END
    execution --> optimizer{🔄 Optimizer}
    optimizer -->|REOPTIMIZE| creative
    optimizer -->|COMPLETE| END
    """
