"""
CampaignX — Local Gamification Engine.

A deterministic‑stochastic simulator that mocks the CampaignX API
(/api/v1/get_report) to protect the strict 100 req/day API limit.

When a seed is provided, results are fully reproducible.
Performance is weighted: 70 % click‑rate + 30 % open‑rate.
"""

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

# ─── Configuration ────────────────────────────────────────────────────────────

# Realistic base‑rate ranges (will be sampled uniformly)
OPEN_RATE_RANGE: Tuple[float, float] = (0.25, 0.40)
CLICK_RATE_RANGE: Tuple[float, float] = (0.08, 0.18)

# Weighted scoring
CLICK_WEIGHT: float = 0.70
OPEN_WEIGHT: float = 0.30

# Threshold below which the engine recommends further optimization
OPTIMIZATION_THRESHOLD: float = 0.18

# Per‑iteration improvement curve (diminishing returns)
IMPROVEMENT_FACTOR: float = 0.12        # max ~12 % relative lift per iteration
MAX_ITERATIONS: int = 5

# Bounce probability
BOUNCE_RATE: float = 0.03

# ─── Mock Data Generation ────────────────────────────────────────────────────

FIRST_NAMES = [
    "Aarav", "Priya", "Rohan", "Sneha", "Vikram", "Anjali", "Karan", "Meera",
    "Arjun", "Divya", "Rahul", "Neha", "Siddharth", "Pooja", "Aditya", "Kavita",
    "Manish", "Ritu", "Suresh", "Lakshmi", "Deepak", "Sunita", "Rajesh", "Anita",
    "Nikhil", "Swati", "Amit", "Geeta", "Varun", "Rekha",
]

LAST_NAMES = [
    "Sharma", "Patel", "Singh", "Kumar", "Gupta", "Reddy", "Joshi", "Mehta",
    "Verma", "Nair", "Iyer", "Das", "Chopra", "Rao", "Bhat", "Menon",
    "Agarwal", "Pandey", "Mishra", "Chauhan", "Desai", "Pillai", "Sinha", "Malik",
]

DOMAINS = ["superbfsi.in", "bankmail.co", "finserve.com", "trustmail.in"]


def generate_mock_recipients(
    count: int = 200,
    segment: Optional[str] = None,
    rng: Optional[random.Random] = None,
) -> List[Dict[str, Any]]:
    """
    Create *count* fake email recipients.

    Returns:
        List of dicts with keys: ``name``, ``email``, ``segment``.
    """
    _rng = rng or random.Random()
    recipients: List[Dict[str, Any]] = []
    for _ in range(count):
        first = _rng.choice(FIRST_NAMES)
        last = _rng.choice(LAST_NAMES)
        domain = _rng.choice(DOMAINS)
        uid = _rng.randint(100, 999)
        email = f"{first.lower()}.{last.lower()}{uid}@{domain}"
        recipients.append({
            "name": f"{first} {last}",
            "email": email,
            "segment": segment or "general",
        })
    return recipients


# ─── Core Simulation ─────────────────────────────────────────────────────────


def simulate_campaign(
    campaign_id: str,
    recipients: List[Dict[str, Any]],
    iteration: int = 1,
    previous_open_rate: Optional[float] = None,
    previous_click_rate: Optional[float] = None,
    seed: Optional[int] = None,
) -> List[Dict]:
    """
    For each recipient, probabilistically generate email events.

    Returns an array of dicts matching the ``/api/v1/get_report`` schema:
    ``[{ campaign_id, email_id, recipient, event_type, status, timestamp }, …]``

    Clicks are only possible for recipients who opened the email.
    """
    rng = random.Random(seed)
    base_time = datetime.now(timezone.utc) - timedelta(hours=24)

    # Determine effective rates — first iteration uses random base rates,
    # subsequent iterations improve on previous rates.
    if iteration == 1 or previous_open_rate is None or previous_click_rate is None:
        effective_open_rate = rng.uniform(*OPEN_RATE_RANGE)
        effective_click_rate = rng.uniform(*CLICK_RATE_RANGE)
    else:
        # Diminishing‑returns improvement
        decay = IMPROVEMENT_FACTOR / iteration
        effective_open_rate = min(float(previous_open_rate or 0), 0.85) * (1 + decay)
        effective_open_rate = min(effective_open_rate, 0.85)
        effective_click_rate = min(float(previous_click_rate or 0), 0.60) * (1 + decay * 1.3)
        effective_click_rate = min(effective_click_rate, 0.60)

    report_entries: List[Dict] = []
    email_counter = 0

    for recipient in recipients:
        email_counter += 1
        email_id = f"em_{campaign_id}_{email_counter:04d}"
        ts_offset = rng.randint(0, 86_400)  # random second within 24h window
        event_time = base_time + timedelta(seconds=ts_offset)

        # Check for bounce first
        if rng.random() < BOUNCE_RATE:
            report_entries.append({
                "campaign_id": campaign_id,
                "email_id": email_id,
                "recipient": recipient["email"],
                "event_type": "EO",
                "status": "bounced",
                "timestamp": event_time.isoformat(),
            })
            continue

        # Delivery event (implicit — every non‑bounced email is delivered)
        opened = rng.random() < effective_open_rate

        if opened:
            open_time = event_time + timedelta(seconds=rng.randint(60, 7200))
            report_entries.append({
                "campaign_id": campaign_id,
                "email_id": email_id,
                "recipient": recipient["email"],
                "event_type": "EO",
                "status": "opened",
                "timestamp": open_time.isoformat(),
            })

            # Clicks only if opened
            clicked = rng.random() < (effective_click_rate / effective_open_rate)
            if clicked:
                click_time = open_time + timedelta(seconds=rng.randint(10, 3600))
                report_entries.append({
                    "campaign_id": campaign_id,
                    "email_id": email_id,
                    "recipient": recipient["email"],
                    "event_type": "EC",
                    "status": "clicked",
                    "timestamp": click_time.isoformat(),
                })
        else:
            # Delivered but not opened
            report_entries.append({
                "campaign_id": campaign_id,
                "email_id": email_id,
                "recipient": recipient["email"],
                "event_type": "EO",
                "status": "delivered",
                "timestamp": event_time.isoformat(),
            })

    return report_entries


# ─── Scoring & Evaluation ────────────────────────────────────────────────────


def calculate_weighted_score(open_rate: float, click_rate: float) -> float:
    """
    Weighted campaign performance score.
    Click‑rate is weighted at 70 %, open‑rate at 30 %.
    """
    return round(OPEN_WEIGHT * open_rate + CLICK_WEIGHT * click_rate, 6)


def evaluate_campaign(report_entries: List[Dict]) -> Dict:
    """
    Aggregate raw report entries into summary metrics.

    Returns:
        Dict with ``total_sent``, ``total_opened``, ``total_clicked``,
        ``total_bounced``, ``open_rate``, ``click_rate``,
        ``weighted_score``, ``recommendation``.
    """
    unique_emails = {e["email_id"] for e in report_entries}
    total_sent = len(unique_emails)

    if total_sent == 0:
        return {
            "total_sent": 0,
            "total_opened": 0,
            "total_clicked": 0,
            "total_bounced": 0,
            "open_rate": 0.0,
            "click_rate": 0.0,
            "weighted_score": 0.0,
            "recommendation": "OPTIMIZE",
        }

    opened_ids = {e["email_id"] for e in report_entries if e["status"] == "opened"}
    clicked_ids = {e["email_id"] for e in report_entries if e["status"] == "clicked"}
    bounced_ids = {e["email_id"] for e in report_entries if e["status"] == "bounced"}

    total_opened = len(opened_ids)
    total_clicked = len(clicked_ids)
    total_bounced = len(bounced_ids)

    deliverable = total_sent - total_bounced
    open_rate = total_opened / deliverable if deliverable > 0 else 0.0
    click_rate = total_clicked / deliverable if deliverable > 0 else 0.0

    score = calculate_weighted_score(open_rate, click_rate)
    recommendation = "COMPLETE" if score >= OPTIMIZATION_THRESHOLD else "OPTIMIZE"

    return {
        "total_sent": total_sent,
        "total_opened": total_opened,
        "total_clicked": total_clicked,
        "total_bounced": total_bounced,
        "open_rate": round(open_rate, 4),
        "click_rate": round(click_rate, 4),
        "weighted_score": round(score, 4),
        "recommendation": recommendation,
    }


def simulate_optimization(
    campaign_id: str,
    recipients: List[Dict[str, Any]],
    previous_open_rate: float,
    previous_click_rate: float,
    iteration: int,
    seed: Optional[int] = None,
) -> Tuple[List[Dict], Dict]:
    """
    Run a new simulation iteration with improved rates (diminishing returns).

    Returns:
        (report_entries, summary_dict)
    """
    if iteration > MAX_ITERATIONS:
        raise ValueError(f"Max iterations ({MAX_ITERATIONS}) exceeded")

    report = simulate_campaign(
        campaign_id=campaign_id,
        recipients=recipients,
        iteration=iteration,
        previous_open_rate=previous_open_rate,
        previous_click_rate=previous_click_rate,
        seed=seed,
    )
    summary = evaluate_campaign(report)
    return report, summary


# ─── Full Pipeline Helper ────────────────────────────────────────────────────


def run_full_simulation(
    campaign_id: str,
    recipient_count: int = 200,
    segment: Optional[str] = None,
    seed: Optional[int] = None,
) -> Dict:
    """
    One‑shot convenience: generate recipients → simulate → evaluate.

    Returns dict with ``recipients``, ``report``, ``summary``, ``iteration``.
    """
    rng: Optional[random.Random] = random.Random(seed) if seed is not None else None
    recipients = generate_mock_recipients(recipient_count, segment, rng)

    # Derive a sub‑seed from the main seed for the simulation
    sim_seed = rng.randint(0, 2**31) if rng is not None else None
    report = simulate_campaign(campaign_id, recipients, iteration=1, seed=sim_seed)
    summary = evaluate_campaign(report)

    return {
        "campaign_id": campaign_id,
        "iteration": 1,
        "recipients": recipients,
        "report": report,
        "summary": summary,
    }
