"""
CampaignX — Strategist Agent.

Uses the dynamically-discovered ``get_customer_cohort`` tool to fetch
the latest customer data. Forces fresh "Test Phase" cohort — no caching.
"""

import json
import os
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.state import CampaignState
from agents.api_discovery import get_tool_descriptions


# ─── System Prompt ────────────────────────────────────────────────────────────

STRATEGIST_SYSTEM_PROMPT = """You are the Strategist Agent for SuperBFSI email campaigns.

Your job is to use the dynamically-discovered API tools to fetch the LATEST customer cohort data
for the target segment specified in the campaign plan.

CRITICAL INSTRUCTIONS:
1. ALWAYS use the get_customer_cohort tool with no_cache="true" to force fresh data
2. NEVER rely on cached or stale cohort data — always pull the latest "Test Phase" cohort
3. Extract the list of recipient email addresses from the cohort response
4. Analyze the cohort demographics to provide segmentation insights

You will receive:
- The campaign plan (product, segment, tone, etc.)
- The available API tools (dynamically discovered from OpenAPI spec)

Respond with a JSON object:
{
  "segment_analysis": "<brief analysis of the cohort demographics>",
  "recommended_approach": "<how to tailor the campaign for this segment>",
  "cohort_size": <number of recipients>,
  "key_insights": ["<insight 1>", "<insight 2>"]
}

Respond with ONLY the JSON — no markdown, no explanation."""


# ─── Agent Node ───────────────────────────────────────────────────────────────


def strategist_node(state: CampaignState) -> Dict[str, Any]:
    """
    LangGraph node: Fetch customer cohort and analyze segment.

    Reads:  state["plan"], state["api_tools"]
    Writes: state["cohort"], state["cohort_id"], state["recipient_emails"],
            state["logs"], state["status"]
    """
    plan = state.get("plan", {})
    api_tools = state.get("api_tools", {})
    logs = list(state.get("logs", []))
    segment = plan.get("segment", "all")

    logs.append({
        "agent": "strategist",
        "action": "fetching_cohort",
        "detail": f"Dynamically calling get_customer_cohort for segment='{segment}' with no_cache=true",
    })

    # ── Step 1: Call the dynamically-discovered API tool ──
    cohort_data = {}
    customers = []
    cohort_id = ""

    cohort_tool = api_tools.get("get_customer_cohort")
    if cohort_tool:
        try:
            raw_result = cohort_tool.invoke({
                "segment": segment,
                "no_cache": "true",
            })
            cohort_data = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
            customers = cohort_data.get("customers", [])
            cohort_id = cohort_data.get("cohort_id", "unknown")

            logs.append({
                "agent": "strategist",
                "action": "cohort_fetched",
                "detail": f"Fetched {len(customers)} customers from cohort '{cohort_id}' (segment: {segment})",
            })
        except Exception as e:
            logs.append({
                "agent": "strategist",
                "action": "api_error",
                "detail": f"get_customer_cohort failed: {e}. Using fallback data.",
            })
    else:
        logs.append({
            "agent": "strategist",
            "action": "tool_not_found",
            "detail": "get_customer_cohort tool not available. Using empty cohort.",
        })

    # Extract emails
    recipient_emails = [c.get("email", "") for c in customers if c.get("email")]

    # ── Step 2: LLM analysis of the segment ──
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.2,
        )

        tool_descriptions = get_tool_descriptions(api_tools)

        messages = [
            SystemMessage(content=STRATEGIST_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Campaign Plan:\n{json.dumps(plan, indent=2)}\n\n"
                f"Cohort Data Summary:\n"
                f"- Segment: {segment}\n"
                f"- Total customers: {len(customers)}\n"
                f"- Cohort ID: {cohort_id}\n"
                f"- Sample records: {json.dumps(customers[:3], indent=2)}\n\n"
                f"Dynamically Discovered Tools:\n{tool_descriptions}\n\n"
                f"Provide your segment analysis as JSON."
            )),
        ]

        response = llm.invoke(messages)
        raw_text = response.content.strip()

        # Clean markdown
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

        segment_analysis = json.loads(raw_text)
        logs.append({
            "agent": "strategist",
            "action": "analysis_complete",
            "detail": f"Segment analysis: {segment_analysis.get('recommended_approach', 'N/A')[:100]}",
        })

    except Exception as e:
        segment_analysis = {
            "segment_analysis": f"Cohort of {len(customers)} customers in '{segment}'",
            "recommended_approach": "Standard professional outreach",
            "cohort_size": len(customers),
            "key_insights": ["Segment data available", "Ready for creative content"],
        }
        logs.append({
            "agent": "strategist",
            "action": "analysis_fallback",
            "detail": f"LLM analysis failed ({e}), using fallback.",
        })

    return {
        "cohort": customers,
        "cohort_id": cohort_id,
        "recipient_emails": recipient_emails,
        "logs": logs,
        "status": "cohort_ready",
    }
