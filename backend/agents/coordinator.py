"""
CampaignX — Coordinator Agent.

Parses a natural-language campaign brief into a structured,
actionable plan that downstream agents can consume.
"""

import json
import os
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.state import CampaignState


# ─── System Prompt ────────────────────────────────────────────────────────────

COORDINATOR_SYSTEM_PROMPT = """You are the Coordinator Agent for an email marketing campaign system at SuperBFSI, a financial services company.

Your job is to parse a natural-language campaign brief and produce a STRUCTURED PLAN as JSON.

The plan JSON MUST contain these fields:
{
  "product": "<product name, e.g. XDeposit>",
  "segment": "<target customer segment, e.g. female_seniors, young_professionals, all>",
  "tone": "<communication tone: professional | friendly | urgent | premium>",
  "value_props": ["<key value proposition 1>", "<key value proposition 2>"],
  "channel": "email",
  "objective": "<brief description of the campaign goal>",
  "interest_rate_bonus": "<any rate bonus mentioned, e.g. +1%, +1.25%, or null>"
}

Guidelines:
- Extract the product name carefully from the brief
- Infer the segment from demographic keywords (e.g. "female seniors" → "female_seniors")
- Identify value propositions from financial context
- If a rate bonus is mentioned (e.g., +1% or +1.25%), capture it
- Default tone to "professional" for BFSI communications
- Always set channel to "email"

Respond with ONLY the JSON object — no markdown, no explanation."""


# ─── Agent Node ───────────────────────────────────────────────────────────────


def coordinator_node(state: CampaignState) -> Dict[str, Any]:
    """
    LangGraph node: Parse the campaign brief into a structured plan.

    Reads:  state["brief"]
    Writes: state["plan"], state["logs"], state["status"]
    """
    brief = state.get("brief", "")
    logs = list(state.get("logs", []))

    logs.append({
        "agent": "coordinator",
        "action": "parsing_brief",
        "detail": f"Analyzing campaign brief: {brief[:100]}...",
    })

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.1,
        )

        messages = [
            SystemMessage(content=COORDINATOR_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this campaign brief into a structured plan:\n\n{brief}"),
        ]

        response = llm.invoke(messages)
        raw_text = response.content.strip()

        # Clean markdown code fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

        plan = json.loads(raw_text)

        logs.append({
            "agent": "coordinator",
            "action": "plan_created",
            "detail": f"Plan: product={plan.get('product')}, segment={plan.get('segment')}, tone={plan.get('tone')}",
        })

        return {
            "plan": plan,
            "logs": logs,
            "status": "planned",
        }

    except json.JSONDecodeError as e:
        logs.append({
            "agent": "coordinator",
            "action": "parse_error",
            "detail": f"Failed to parse LLM response as JSON: {e}. Raw: {raw_text[:200]}",
        })
        # Fallback plan
        fallback_plan = {
            "product": "XDeposit",
            "segment": "all",
            "tone": "professional",
            "value_props": ["High returns", "Secure investment"],
            "channel": "email",
            "objective": brief[:200],
            "interest_rate_bonus": None,
        }
        return {
            "plan": fallback_plan,
            "logs": logs,
            "status": "planned",
            "errors": list(state.get("errors", [])) + [f"Coordinator JSON parse error: {e}"],
        }

    except Exception as e:
        logs.append({
            "agent": "coordinator",
            "action": "error",
            "detail": f"Coordinator failed: {e}",
        })
        return {
            "plan": {
                "product": "XDeposit",
                "segment": "all",
                "tone": "professional",
                "value_props": ["Financial growth", "Security"],
                "channel": "email",
                "objective": brief[:200],
                "interest_rate_bonus": None,
            },
            "logs": logs,
            "status": "planned",
            "errors": list(state.get("errors", [])) + [f"Coordinator error: {e}"],
        }
