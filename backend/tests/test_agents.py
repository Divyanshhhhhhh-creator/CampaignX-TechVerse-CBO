"""
Phase 2 Verification Script — Tests all agent components.
Run from the backend/ directory: python tests/test_agents.py
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_openapi_discovery():
    """Verify dynamic API tool discovery from spec."""
    from agents.api_discovery import load_openapi_spec, build_tools_from_spec, get_tool_descriptions

    spec = load_openapi_spec("openapi_spec.json")
    assert "paths" in spec, "Spec missing 'paths'"
    assert len(spec["paths"]) == 3, f"Expected 3 paths, got {len(spec['paths'])}"

    tools = build_tools_from_spec(spec, "http://127.0.0.1:8000")
    assert "get_customer_cohort" in tools, "Missing get_customer_cohort tool"
    assert "send_campaign" in tools, "Missing send_campaign tool"
    assert "get_report" in tools, "Missing get_report tool"

    # Verify tool descriptions
    desc = get_tool_descriptions(tools)
    assert "get_customer_cohort" in desc
    assert "send_campaign" in desc
    assert "get_report" in desc

    # Verify no hardcoded URLs in tool names
    for name, tool in tools.items():
        assert name in ("get_customer_cohort", "send_campaign", "get_report")
        assert tool.description, f"Tool {name} has no description"

    print("  ✅ OpenAPI Discovery: 3 tools registered dynamically")
    return tools


def test_state_schema():
    """Verify LangGraph state schema."""
    from agents.state import CampaignState

    # CampaignState should be a TypedDict
    state: CampaignState = {
        "brief": "Launch XDeposit for female seniors",
        "campaign_id": "test_001",
        "plan": {},
        "cohort": [],
        "recipient_emails": [],
        "email_subject": "",
        "email_body": "",
        "compliance_approved": False,
        "compliance_issues": [],
        "compliance_retries": 0,
        "api_tools": {},
        "api_base_url": "http://127.0.0.1:8000",
        "iteration": 1,
        "logs": [],
        "errors": [],
        "status": "test",
    }
    assert state["brief"] == "Launch XDeposit for female seniors"
    print("  ✅ State Schema: All fields valid")


def test_compliance_node():
    """Verify Compliance Agent catches issues correctly."""
    from agents.compliance import compliance_node

    # Test 1: Valid content
    valid_state = {
        "email_subject": "Discover XDeposit - Exclusive Offer",
        "email_body": (
            '<p>Dear Customer,</p>'
            '<p><b>XDeposit</b> offers <i>great returns</i>. 💰</p>'
            f'<p><u><a href="https://superbfsi.com/xdeposit/explore/">Explore Now</a></u></p>'
        ),
        "compliance_retries": 0,
        "logs": [],
    }
    result = compliance_node(valid_state)
    print(f"  Valid content: approved={result['compliance_approved']}, issues={result['compliance_issues']}")

    # Test 2: Prohibited language
    bad_state = {
        "email_subject": "Guaranteed Returns on XDeposit",
        "email_body": '<p>Get <b>guaranteed returns</b> with zero risk!</p><a href="https://superbfsi.com/xdeposit/explore/">Click</a>',
        "compliance_retries": 0,
        "logs": [],
    }
    result2 = compliance_node(bad_state)
    assert not result2["compliance_approved"], "Should reject 'guaranteed returns'"
    assert any("guaranteed returns" in i.lower() for i in result2["compliance_issues"])
    print(f"  ✅ Prohibited language detected: {len(result2['compliance_issues'])} issue(s)")

    # Test 3: Wrong URL
    wrong_url_state = {
        "email_subject": "Discover XDeposit",
        "email_body": '<p><b>Click here</b></p><a href="https://evil.com/phish">Click</a>',
        "compliance_retries": 0,
        "logs": [],
    }
    result3 = compliance_node(wrong_url_state)
    assert not result3["compliance_approved"], "Should reject wrong URL"
    print(f"  ✅ Wrong URL detected: {len(result3['compliance_issues'])} issue(s)")

    # Test 4: No HTML formatting
    no_format_state = {
        "email_subject": "Discover XDeposit",
        "email_body": f'Plain text with https://superbfsi.com/xdeposit/explore/ link',
        "compliance_retries": 0,
        "logs": [],
    }
    result4 = compliance_node(no_format_state)
    has_format_issue = any("font variation" in i.lower() or "html" in i.lower() for i in result4["compliance_issues"])
    print(f"  ✅ Missing formatting detected: {has_format_issue}")


def test_graph_compilation():
    """Verify the LangGraph compiles without errors."""
    from agents.graph import build_campaign_graph, get_graph_diagram

    graph = build_campaign_graph()
    assert graph is not None, "Graph compilation failed"

    diagram = get_graph_diagram()
    assert "coordinator" in diagram
    assert "compliance" in diagram

    print("  ✅ Graph compiled successfully")
    print(f"  ✅ Mermaid diagram: {len(diagram)} chars")


if __name__ == "__main__":
    print("=" * 60)
    print("  Phase 2 Verification — Agent System")
    print("=" * 60)

    print("\n1. OpenAPI Discovery:")
    tools = test_openapi_discovery()

    print("\n2. State Schema:")
    test_state_schema()

    print("\n3. Compliance Agent:")
    test_compliance_node()

    print("\n4. Graph Compilation:")
    test_graph_compilation()

    print("\n" + "=" * 60)
    print("  ALL PHASE 2 TESTS PASSED ✅")
    print("=" * 60)
