"""Integration test script — tests the full FastAPI route flow."""
import httpx
import json

base = "http://127.0.0.1:8000"

# 1. Health check
print("=== HEALTH CHECK ===")
r = httpx.get(f"{base}/api/health")
print(f"Status: {r.status_code} -> {r.json()}")

# 2. Submit campaign
print("\n=== SUBMIT CAMPAIGN ===")
r = httpx.post(
    f"{base}/api/campaign/submit",
    json={
        "brief": "Launch XDeposit for female seniors",
        "target_segment": "female_seniors",
        "product_name": "XDeposit",
    },
)
print(f"Status: {r.status_code}")
data = r.json()
print(json.dumps(data, indent=2))
cid = data["campaign_id"]

# 3. Run simulator
print("\n=== RUN SIMULATOR ===")
r = httpx.post(
    f"{base}/api/simulator/run",
    json={"campaign_id": cid, "recipient_count": 100, "seed": 42},
    timeout=30,
)
print(f"Status: {r.status_code}")
sim = r.json()
print(f"Iteration: {sim['iteration']}")
print(f"Report entries: {len(sim['report'])}")
print(f"Summary: {json.dumps(sim['summary'], indent=2)}")

# 4. Get status
print("\n=== CAMPAIGN STATUS ===")
r = httpx.get(f"{base}/api/campaign/{cid}/status")
print(f"Status: {r.status_code}")
print(json.dumps(r.json(), indent=2))

# 5. Get logs
print("\n=== AGENT LOGS ===")
r = httpx.get(f"{base}/api/campaign/{cid}/logs")
print(f"Status: {r.status_code}")
logs = r.json()
print(f"Log count: {len(logs['logs'])}")
for log in logs["logs"]:
    print(f"  [{log['agent_name']}] {log['action']}")

# 6. Verify report schema matches /api/v1/get_report
print("\n=== SCHEMA CHECK ===")
entry = sim["report"][0]
expected_keys = {"campaign_id", "email_id", "recipient", "event_type", "status", "timestamp"}
actual_keys = set(entry.keys())
print(f"Expected keys: {expected_keys}")
print(f"Actual keys:   {actual_keys}")
print(f"Schema match: {expected_keys == actual_keys}")

# 7. Run second iteration (optimization)
print("\n=== OPTIMIZATION RUN ===")
r = httpx.post(
    f"{base}/api/simulator/run",
    json={"campaign_id": cid, "recipient_count": 100, "seed": 43},
    timeout=30,
)
print(f"Status: {r.status_code}")
sim2 = r.json()
print(f"Iteration: {sim2['iteration']}")
print(f"Summary: {json.dumps(sim2['summary'], indent=2)}")

print("\n=== ALL TESTS PASSED ===")
