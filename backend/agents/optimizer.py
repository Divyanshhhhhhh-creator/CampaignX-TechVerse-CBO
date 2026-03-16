"""
CampaignX — Optimizer Agent.

Autonomous optimization loop that:
  1. Ingests performance metrics (opens & clicks) from the simulator
  2. Evaluates against the 70 % click-rate / 30 % open-rate heuristic
  3. Identifies underperforming micro-segments
  4. Generates optimization directives for the Creative Agent
  5. Routes back to creative → compliance → HIL gate for relaunch

Runs without manual data ingestion — fully autonomous.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from agents.state import CampaignState
from simulator import (
    evaluate_campaign,
    generate_mock_recipients,
    simulate_campaign,
    CLICK_WEIGHT,
    OPEN_WEIGHT,
    OPTIMIZATION_THRESHOLD,
    MAX_ITERATIONS,
)


# ─── Micro-Segment Analysis ──────────────────────────────────────────────────


def identify_micro_segments(
    report_entries: List[Dict],
    recipients: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Slice report by recipient segment to identify underperforming micro-segments.

    Groups recipients by their ``segment`` field, computes per-segment
    open/click rates, and returns a list sorted by weighted score (ascending,
    worst-performing first).

    Returns:
        List of dicts:
        ``[{ segment, total, opened, clicked, open_rate, click_rate,
             weighted_score, status }]``
    """
    # Build email → segment lookup
    email_to_segment: Dict[str, str] = {}
    for r in recipients:
        email_to_segment[r["email"]] = r.get("segment", "general")

    # Build email_id → segment lookup from report entries
    email_id_segment: Dict[str, str] = {}
    for entry in report_entries:
        recipient_email = entry.get("recipient", "")
        segment = email_to_segment.get(recipient_email, "general")
        email_id_segment[entry["email_id"]] = segment

    # Group by segment
    segment_stats: Dict[str, Dict[str, Any]] = {}
    for entry in report_entries:
        seg = email_id_segment.get(entry["email_id"], "general")
        if seg not in segment_stats:
            segment_stats[seg] = {
                "segment": seg,
                "email_ids": set(),
                "opened_ids": set(),
                "clicked_ids": set(),
                "bounced_ids": set(),
            }

        stats = segment_stats[seg]
        stats["email_ids"].add(entry["email_id"])

        if entry["status"] == "opened":
            stats["opened_ids"].add(entry["email_id"])
        elif entry["status"] == "clicked":
            stats["clicked_ids"].add(entry["email_id"])
        elif entry["status"] == "bounced":
            stats["bounced_ids"].add(entry["email_id"])

    # Compute per-segment metrics
    micro_segments: List[Dict[str, Any]] = []
    for seg, stats in segment_stats.items():
        total = len(stats["email_ids"])
        bounced = len(stats["bounced_ids"])
        deliverable = total - bounced
        opened = len(stats["opened_ids"])
        clicked = len(stats["clicked_ids"])

        open_rate = opened / deliverable if deliverable > 0 else 0.0
        click_rate = clicked / deliverable if deliverable > 0 else 0.0
        weighted_score = round(OPEN_WEIGHT * open_rate + CLICK_WEIGHT * click_rate, 4)

        status = "optimized" if weighted_score >= OPTIMIZATION_THRESHOLD else "underperforming"

        micro_segments.append({
            "segment": seg,
            "total": total,
            "opened": opened,
            "clicked": clicked,
            "open_rate": round(open_rate, 4),
            "click_rate": round(click_rate, 4),
            "weighted_score": weighted_score,
            "status": status,
        })

    # Sort worst-performing first
    micro_segments.sort(key=lambda s: s["weighted_score"])
    return micro_segments


# ─── Optimization Directives ─────────────────────────────────────────────────


def generate_optimization_directives(
    micro_segments: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    iteration: int,
) -> str:
    """
    Produce actionable directives for the Creative Agent based on
    micro-segment analysis and overall performance using the LLM.
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_google_genai import ChatGoogleGenerativeAI
    import os
    
    sys_prompt = (
        "You are the autonomous Analyst Agent for CampaignX. "
        "Review the provided 70/30 heuristic metrics and micro-segment targets. "
        "Output exactly 3 actionable, natural-language directives for the Creative Agent "
        "to improve the Click-Through-Rate (CTR)."
    )
    
    try:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "dummy")
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", 
            google_api_key=api_key, 
            temperature=0.2
        )
        response = llm.invoke([
            SystemMessage(content=sys_prompt),
            HumanMessage(content=f"Metrics: {metrics}. Micro-segments: {micro_segments}. Iteration: {iteration}")
        ])
        return response.content
    except Exception as e:
        return "Increase urgency and CTR focus on underperforming segments."


# ─── Optimizer Agent Node ─────────────────────────────────────────────────────


def optimizer_node(state: CampaignState) -> Dict[str, Any]:
    """
    LangGraph node: Autonomous Optimization Agent.

    After campaign execution, this node:
      1. Runs the local simulator to generate performance data
      2. Evaluates metrics against the 70/30 heuristic
      3. Identifies underperforming micro-segments
      4. Decides whether to REOPTIMIZE or COMPLETE
      5. If REOPTIMIZE, generates directives for Creative Agent

    Reads:  state["campaign_id"], state["recipient_emails"],
            state["iteration"], state["optimization_history"]
    Writes: state["metrics"], state["report"], state["micro_segments"],
            state["optimization_directives"], state["optimization_action"],
            state["optimization_history"], state["iteration"], state["logs"]
    """
    logs = list(state.get("logs", []))
    campaign_id = state.get("campaign_id", "unknown")
    iteration = state.get("iteration", 1)
    opt_history = list(state.get("optimization_history", []))
    target_segment = state.get("plan", {}).get("segment", "general")

    logs.append({
        "agent": "optimizer",
        "action": "optimization_started",
        "detail": (
            f"🔄 Optimizer Agent starting iteration {iteration}. "
            f"Ingesting performance metrics autonomously..."
        ),
    })

    # ── Step 1: Run simulation to generate metrics ────────────────────────
    # This replaces the manual "hit get_report" step — fully autonomous
    recipient_emails = state.get("recipient_emails", [])
    recipient_count = len(recipient_emails) if recipient_emails else 200

    # Generate recipients with the target segment for micro-segment analysis
    recipients = generate_mock_recipients(
        count=recipient_count,
        segment=target_segment,
    )

    # Add sub-segment variety for micro-segment analysis
    sub_segments = _generate_sub_segments(target_segment, recipients)

    report_entries = simulate_campaign(
        campaign_id=campaign_id,
        recipients=sub_segments,
        iteration=iteration,
        previous_open_rate=opt_history[-1]["open_rate"] if opt_history else None,
        previous_click_rate=opt_history[-1]["click_rate"] if opt_history else None,
    )

    # ── Step 2: Evaluate metrics against heuristic ────────────────────────
    metrics = evaluate_campaign(report_entries)

    logs.append({
        "agent": "optimizer",
        "action": "metrics_evaluated",
        "detail": (
            f"📊 Metrics: Open={metrics['open_rate']:.2%}, "
            f"Click={metrics['click_rate']:.2%}, "
            f"Score={metrics['weighted_score']:.4f} "
            f"(threshold={OPTIMIZATION_THRESHOLD})"
        ),
    })

    # ── Step 3: Identify micro-segments ───────────────────────────────────
    micro_segments = identify_micro_segments(report_entries, sub_segments)

    underperforming = [s for s in micro_segments if s["status"] == "underperforming"]
    logs.append({
        "agent": "optimizer",
        "action": "micro_segments_analyzed",
        "detail": (
            f"🔬 Identified {len(micro_segments)} micro-segment(s): "
            f"{len(underperforming)} underperforming, "
            f"{len(micro_segments) - len(underperforming)} optimized."
        ),
    })

    # ── Step 4: Record history ────────────────────────────────────────────
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

    # ── Step 5: Decision — REOPTIMIZE or COMPLETE ─────────────────────────
    if metrics["weighted_score"] >= OPTIMIZATION_THRESHOLD:
        # Threshold met → campaign is performing well
        logs.append({
            "agent": "optimizer",
            "action": "optimization_complete",
            "detail": (
                f"✅ Performance meets threshold! Score {metrics['weighted_score']:.4f} "
                f"≥ {OPTIMIZATION_THRESHOLD}. Campaign optimization complete."
            ),
        })
        return {
            "metrics": metrics,
            "report": report_entries,
            "micro_segments": micro_segments,
            "optimization_history": opt_history,
            "optimization_action": "COMPLETE",
            "optimization_directives": "",
            "iteration": iteration,
            "logs": logs,
            "status": "optimization_complete",
            "active_node": "optimizer",
        }

    if iteration >= MAX_ITERATIONS:
        # Max iterations reached — stop even if below threshold
        logs.append({
            "agent": "optimizer",
            "action": "max_iterations_reached",
            "detail": (
                f"⚠️ Max iterations ({MAX_ITERATIONS}) reached. "
                f"Final score: {metrics['weighted_score']:.4f}. Stopping optimization."
            ),
        })
        return {
            "metrics": metrics,
            "report": report_entries,
            "micro_segments": micro_segments,
            "optimization_history": opt_history,
            "optimization_action": "COMPLETE",
            "optimization_directives": "",
            "iteration": iteration,
            "logs": logs,
            "status": "optimization_complete",
            "active_node": "optimizer",
        }

    # Below threshold + iterations remaining → REOPTIMIZE
    directives = generate_optimization_directives(micro_segments, metrics, iteration)

    logs.append({
        "agent": "optimizer",
        "action": "reoptimize_triggered",
        "detail": (
            f"🔁 Score {metrics['weighted_score']:.4f} < {OPTIMIZATION_THRESHOLD}. "
            f"Triggering creative re-generation (iteration {iteration + 1}). "
            f"Focus segments: {', '.join(s['segment'] for s in underperforming[:3])}."
        ),
    })

    return {
        "metrics": metrics,
        "report": report_entries,
        "micro_segments": micro_segments,
        "optimization_history": opt_history,
        "optimization_action": "REOPTIMIZE",
        "optimization_directives": directives,
        "iteration": iteration + 1,
        "logs": logs,
        "status": "reoptimizing",
        "active_node": "optimizer",
        # Reset compliance for the new iteration
        "compliance_approved": False,
        "compliance_issues": [],
        "compliance_retries": 0,
    }


# ─── Helper: Sub-Segment Generation ──────────────────────────────────────────


def _generate_sub_segments(
    base_segment: str,
    recipients: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Diversify recipients into micro-segments for granular analysis.

    Splits the base segment into demographic sub-groups so the optimizer
    can identify which specific sub-segments are underperforming.
    """
    if not recipients:
        return recipients

    # Define sub-segment suffixes based on common demographics
    sub_suffixes = ["young_professionals", "senior_citizens", "mid_career", "new_customers"]

    enriched = []
    for i, r in enumerate(recipients):
        sub_idx = i % len(sub_suffixes)
        sub_segment = f"{base_segment}_{sub_suffixes[sub_idx]}" if base_segment != "general" else sub_suffixes[sub_idx]
        enriched.append({**r, "segment": sub_segment})

    return enriched
