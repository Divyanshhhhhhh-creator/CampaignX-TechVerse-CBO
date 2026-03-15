"""
CampaignX — LangGraph State Machine.

Wires the four agent nodes into a directed graph:

    START → coordinator → strategist → creative → compliance → END
                                         ↑                    │
                                         └────────────────────┘
                                         (if compliance rejects,
                                          retry creative — max 3×)

API tools are injected at graph start via the ``api_tools`` state key.
"""

import os
from typing import Any, Dict

from langgraph.graph import END, StateGraph

from agents.state import CampaignState
from agents.coordinator import coordinator_node
from agents.strategist import strategist_node
from agents.creative import creative_node
from agents.compliance import compliance_node
from agents.api_discovery import discover_api_tools


# ─── Constants ────────────────────────────────────────────────────────────────

MAX_COMPLIANCE_RETRIES = 3
DEFAULT_SPEC_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "openapi_spec.json")


# ─── Routing Function ────────────────────────────────────────────────────────


def _compliance_router(state: CampaignState) -> str:
    """
    After compliance check:
      - If approved → END
      - If rejected and retries < max → creative (retry loop)
      - If rejected and retries >= max → END (with issues logged)
    """
    approved = state.get("compliance_approved", False)
    retries = state.get("compliance_retries", 0)

    if approved:
        return "end"
    elif retries < MAX_COMPLIANCE_RETRIES:
        return "retry_creative"
    else:
        return "end"


# ─── Graph Builder ────────────────────────────────────────────────────────────


def build_campaign_graph() -> StateGraph:
    """
    Construct the LangGraph StateGraph for the campaign pipeline.

    Returns a compiled graph ready for .invoke() or .stream().
    """
    graph = StateGraph(CampaignState)

    # Add nodes
    graph.add_node("coordinator", coordinator_node)
    graph.add_node("strategist", strategist_node)
    graph.add_node("creative", creative_node)
    graph.add_node("compliance", compliance_node)

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
            "end": END,
            "retry_creative": "creative",
        },
    )

    return graph.compile()


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
        "logs": [],
        "errors": [],
        "status": "starting",
    }

    # Build and execute
    graph = build_campaign_graph()
    final_state = graph.invoke(initial_state)

    return final_state


# ─── Graph Visualization Helper ──────────────────────────────────────────────


def get_graph_diagram() -> str:
    """Return a Mermaid diagram of the graph for documentation."""
    return """
graph LR
    START((Start)) --> coordinator[🧭 Coordinator]
    coordinator --> strategist[📊 Strategist]
    strategist --> creative[✍️ Creative]
    creative --> compliance{🛡️ Compliance}
    compliance -->|Approved| END((End))
    compliance -->|Rejected & retries < 3| creative
    compliance -->|Rejected & retries >= 3| END
    """
