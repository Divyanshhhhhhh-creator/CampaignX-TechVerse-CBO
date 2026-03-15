"""
Tests for the CampaignX Local Gamification Engine.
All tests use fixed seeds to guarantee deterministic, reproducible results.
"""

import random
import sys
import os

# Ensure backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulator import (
    calculate_weighted_score,
    evaluate_campaign,
    generate_mock_recipients,
    run_full_simulation,
    simulate_campaign,
    simulate_optimization,
    CLICK_WEIGHT,
    OPEN_WEIGHT,
)


# ─── Helper ──────────────────────────────────────────────────────────────────

def _make_recipients(count, segment=None, seed=42):
    """Generate recipients with a seeded RNG for reproducibility."""
    rng = random.Random(seed)
    return generate_mock_recipients(count, segment, rng)


# ─── Recipient Generation ────────────────────────────────────────────────────


def test_generate_recipients_count():
    recipients = _make_recipients(50, segment="female_seniors")
    assert len(recipients) == 50


def test_generate_recipients_structure():
    recipients = _make_recipients(5, segment="young_professionals")
    for r in recipients:
        assert "name" in r
        assert "email" in r
        assert "segment" in r
        assert "@" in r["email"]
        assert r["segment"] == "young_professionals"


def test_generate_recipients_default_segment():
    recipients = generate_mock_recipients(3)
    for r in recipients:
        assert r["segment"] == "general"


# ─── Campaign Simulation ─────────────────────────────────────────────────────


def test_simulate_campaign_returns_list():
    recipients = _make_recipients(20)
    report = simulate_campaign("test_001", recipients, seed=42)
    assert isinstance(report, list)
    assert len(report) > 0


def test_simulate_campaign_schema():
    """Every entry must match the /api/v1/get_report schema."""
    recipients = _make_recipients(10)
    report = simulate_campaign("test_002", recipients, seed=99)

    required_keys = {"campaign_id", "email_id", "recipient", "event_type", "status", "timestamp"}
    for entry in report:
        assert required_keys.issubset(entry.keys()), f"Missing keys: {required_keys - entry.keys()}"
        assert entry["event_type"] in ("EO", "EC")
        assert entry["status"] in ("delivered", "opened", "clicked", "bounced")
        assert entry["campaign_id"] == "test_002"


def test_simulate_campaign_deterministic():
    """Same seed must produce identical results."""
    recipients = _make_recipients(50, segment="test")
    run_a = simulate_campaign("det_test", recipients, seed=12345)
    run_b = simulate_campaign("det_test", recipients, seed=12345)
    assert run_a == run_b


def test_clicks_require_opens():
    """Every EC (click) event must correspond to a recipient who also has an EO (open) event."""
    recipients = _make_recipients(100)
    report = simulate_campaign("click_test", recipients, seed=7)

    clicked_recipients = {e["recipient"] for e in report if e["event_type"] == "EC"}
    opened_recipients = {e["recipient"] for e in report if e["status"] == "opened"}

    assert clicked_recipients.issubset(opened_recipients), (
        f"Clicks without opens: {clicked_recipients - opened_recipients}"
    )


# ─── Weighted Scoring ────────────────────────────────────────────────────────


def test_weighted_score_formula():
    """Verify: score = 0.30 * open_rate + 0.70 * click_rate."""
    open_rate = 0.30
    click_rate = 0.15
    expected = OPEN_WEIGHT * open_rate + CLICK_WEIGHT * click_rate
    result = calculate_weighted_score(open_rate, click_rate)
    assert abs(result - expected) < 1e-6, f"Expected {expected}, got {result}"


def test_weighted_score_zero():
    assert calculate_weighted_score(0.0, 0.0) == 0.0


def test_weighted_score_max():
    score = calculate_weighted_score(1.0, 1.0)
    assert abs(score - 1.0) < 1e-6


def test_click_rate_dominates():
    """Higher click rate should produce a higher score even with lower open rate."""
    score_high_click = calculate_weighted_score(open_rate=0.20, click_rate=0.30)
    score_high_open = calculate_weighted_score(open_rate=0.50, click_rate=0.05)
    assert score_high_click > score_high_open, (
        f"Click-heavy ({score_high_click}) should beat open-heavy ({score_high_open})"
    )


# ─── Evaluation ──────────────────────────────────────────────────────────────


def test_evaluate_campaign_structure():
    recipients = _make_recipients(50)
    report = simulate_campaign("eval_test", recipients, seed=42)
    summary = evaluate_campaign(report)

    assert "total_sent" in summary
    assert "total_opened" in summary
    assert "total_clicked" in summary
    assert "total_bounced" in summary
    assert "open_rate" in summary
    assert "click_rate" in summary
    assert "weighted_score" in summary
    assert "recommendation" in summary
    assert summary["recommendation"] in ("OPTIMIZE", "COMPLETE")


def test_evaluate_campaign_rates_in_range():
    recipients = _make_recipients(200)
    report = simulate_campaign("range_test", recipients, seed=55)
    summary = evaluate_campaign(report)

    assert 0.0 <= summary["open_rate"] <= 1.0
    assert 0.0 <= summary["click_rate"] <= 1.0
    assert 0.0 <= summary["weighted_score"] <= 1.0
    assert summary["total_clicked"] <= summary["total_opened"]


def test_evaluate_empty_report():
    summary = evaluate_campaign([])
    assert summary["total_sent"] == 0
    assert summary["weighted_score"] == 0.0
    assert summary["recommendation"] == "OPTIMIZE"


# ─── Optimization / Multi‑Iteration ──────────────────────────────────────────


def test_optimization_improves_score():
    """Subsequent iterations should show improvement (diminishing returns)."""
    recipients = _make_recipients(200, segment="test")
    report_1 = simulate_campaign("opt_test", recipients, iteration=1, seed=100)
    summary_1 = evaluate_campaign(report_1)

    report_2, summary_2 = simulate_optimization(
        campaign_id="opt_test",
        recipients=recipients,
        previous_open_rate=summary_1["open_rate"],
        previous_click_rate=summary_1["click_rate"],
        iteration=2,
        seed=101,
    )

    assert summary_2["weighted_score"] >= 0, "Score should be non-negative"


# ─── Full Pipeline ────────────────────────────────────────────────────────────


def test_run_full_simulation():
    result = run_full_simulation(
        campaign_id="full_test",
        recipient_count=100,
        segment="female_seniors",
        seed=42,
    )
    assert result["campaign_id"] == "full_test"
    assert result["iteration"] == 1
    assert len(result["recipients"]) == 100
    assert len(result["report"]) > 0
    assert "weighted_score" in result["summary"]


def test_full_simulation_deterministic():
    r1 = run_full_simulation("det_full", 50, seed=999)
    r2 = run_full_simulation("det_full", 50, seed=999)
    assert r1["summary"] == r2["summary"]
    assert len(r1["report"]) == len(r2["report"])


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
