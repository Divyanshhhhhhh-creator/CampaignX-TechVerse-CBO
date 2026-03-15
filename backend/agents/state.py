"""
CampaignX — LangGraph State Schema.

TypedDict defining the shared state that flows through all agent nodes
in the multi-agent state machine.
"""

from typing import Any, Dict, List, Optional, TypedDict


class CampaignState(TypedDict, total=False):
    """Shared state for the LangGraph campaign pipeline."""

    # ── Input ──
    brief: str                              # Natural-language campaign brief
    campaign_id: str                        # DB campaign record ID

    # ── Coordinator output ──
    plan: Dict[str, Any]                    # Structured plan from Coordinator
    # Expected keys: product, segment, tone, value_props, channel

    # ── Strategist output ──
    cohort: List[Dict[str, Any]]            # Customer records from API
    cohort_id: str                          # Cohort snapshot identifier
    recipient_emails: List[str]             # Extracted email list

    # ── Creative output ──
    email_subject: str                      # Generated subject line
    email_body: str                         # Generated HTML body
    content_variants: List[Dict[str, str]]  # Alternative versions

    # ── Compliance output ──
    compliance_approved: bool               # Pass/fail from Compliance Agent
    compliance_issues: List[str]            # List of flagged issues
    compliance_retries: int                 # Number of creative→compliance loops

    # ── API tools (injected at graph start) ──
    api_tools: Dict[str, Any]              # Dynamic tools from OpenAPI discovery
    api_base_url: str                       # Base URL for API calls

    # ── Campaign execution ──
    send_result: Dict[str, Any]            # Response from send_campaign
    report: List[Dict[str, Any]]           # Raw report from get_report
    metrics: Dict[str, Any]                # Aggregated metrics

    # ── Pipeline control ──
    iteration: int                          # Optimization loop counter
    status: str                             # Current pipeline stage
    logs: List[Dict[str, str]]             # Agent reasoning trail
    errors: List[str]                       # Error messages
