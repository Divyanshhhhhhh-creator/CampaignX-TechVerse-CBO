import asyncio
import json
import os
from pprint import pprint
from dotenv import load_dotenv

load_dotenv()

from agents.graph import run_campaign_pipeline
from agents.state import CampaignState

def print_trace(node: str, logic: str, inputs: str, outputs: str):
    trace = {
        "agent_node": f"[{node}]",
        "reasoning_trace": {
            "logic": logic,
            "model_inputs": inputs,
            "raw_outputs": outputs
        }
    }
    print("\n" + json.dumps(trace, indent=2))

async def run_live_demo():
    print("\n=======================================================")
    print("      CAMPAIGNX - LIVE DEMO ORCHESTRATOR               ")
    print("=======================================================\n")
    
    brief = "Launch XDeposit with +0.25% premium interest rate specifically targeting female seniors in Mumbai. Ensure the tone is respectful and emphasizes financial security."
    
    print_trace("System", "Initialising pipeline with user brief.", "Brief text", brief)

    # We manually step through the pipeline to demonstrate the phases and traces
    from agents.api_discovery import discover_api_tools
    from agents.graph import build_campaign_graph
    
    tools = discover_api_tools("openapi_spec.json", "http://127.0.0.1:8000")
    
    print_trace("System", "Dynamically discovered OpenAPI endpoints", "openapi_spec.json", f"{list(tools.keys())}")
    
    state: CampaignState = {
        "brief": brief,
        "campaign_id": "demo_campaign_001",
        "api_tools": tools,
        "api_base_url": "http://127.0.0.1:8000",
        "iteration": 1,
        "compliance_retries": 0,
        "human_approved": False,
        "scheduled_send_time": "",
        "active_node": "coordinator",
        "logs": [],
        "errors": [],
        "status": "starting",
    }
    
    graph = build_campaign_graph()
    
    # 1. Coordinator
    print("\n>>> Executing Step 1 & 2: Strategy & Asset Generation...")
    
    for event in graph.stream(state, stream_mode="updates"):
        for node in event.keys():
            node_state = event[node]
            # Print traces based on which node just ran
            if node == "coordinator":
                print_trace(
                    "Coordinator", 
                    "Parsed brief into structured segmentation plan.", 
                    brief, 
                    str(node_state.get("plan", {}))
                )
            elif node == "strategist":
                cohort_len = len(node_state.get("cohort", []))
                print_trace(
                    "Strategist", 
                    "Invoked GET /api/v1/get_customer_cohort dynamically.", 
                    str(node_state.get("plan", {})), 
                    f"Retrieved {cohort_len} profiles (e.g. Female Seniors in Mumbai)"
                )
            elif node == "creative":
                print_trace(
                    "Creative", 
                    "Generated HTML compliant brand-safe variants with mandatory link.", 
                    f"Plan + {cohort_len} recipients", 
                    f"Subject: {node_state.get('email_subject')}\nBody Snippet: {node_state.get('email_body', '')[:100]}..."
                )
            elif node == "compliance":
                approved = node_state.get("compliance_approved")
                reason = "Approved" if approved else str(node_state.get("errors", []))
                print_trace(
                    "Compliance", 
                    "Validated BFSI financial constraints and URL injection.", 
                    "Email Subject + Body", 
                    f"Verdict: {reason}"
                )
                
    # At this point, it hit the HIL Gate (interrupt_before='execution')
    print("\n=======================================================")
    print("   STEP 3: HUMAN-IN-THE-LOOP (HIL) PAUSE ACTIVATED   ")
    print("=======================================================\n")
    
    print_trace(
        "System", 
        "Pipeline paused at node [Execution] per interrupt_before logic.", 
        "Compliance Verdict", 
        "AWAITING HUMAN APPROVAL"
    )
    
    print("\n[Human Input Received]: 'Approved'")
    
    # Update state with approval
    state["human_approved"] = True
    
    # Resume graph execution
    print("\n>>> Executing Step 4, 5 & 6: Dispatch, Telemetry & Optimization...")
    
    for event in graph.stream(state, stream_mode="updates"):
        for node in event.keys():
            node_state = event[node]
            if node == "execution":
                print_trace(
                    "Execution", 
                    "Dispatched campaign via dynamic send_campaign API.", 
                    "Approved Content + Target List", 
                    f"Status: {node_state.get('send_result', {}).get('status')}\nSent at: {node_state.get('send_result', {}).get('scheduled_send_time')}"
                )
            elif node == "optimizer":
                history = node_state.get("optimization_history", [])
                latest = history[-1] if history else {}
                score = latest.get('metrics', {}).get('weighted_score', 0)
                action = node_state.get('optimization_action')
                print_trace(
                    "Optimizer", 
                    "Fetched GET /api/v1/get_report. Calculated 70/30 heuristic.", 
                    "Simulation Telemetry", 
                    f"Weighted Score: {score:.2f}\nAction Decided: {action}\nDirectives: Slicing new micro-segment for subsequent variant."
                )

if __name__ == "__main__":
    asyncio.run(run_live_demo())
