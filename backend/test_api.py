import requests
import json

try:
    # First get a valid campaign ID
    res = requests.get("http://127.0.0.1:8000/api/campaigns")
    if res.status_code == 200 and len(res.json()) > 0:
        campaign_id = res.json()[0]["campaign_id"]
        print(f"Testing with campaign_id: {campaign_id}")
        
        # Test pipeline run
        post_res = requests.post(
            "http://127.0.0.1:8000/api/pipeline/run",
            json={"campaign_id": campaign_id}
        )
        print(f"Status Code: {post_res.status_code}")
        print(f"Response: {post_res.text}")
    else:
        print("No campaigns found to test with")
except Exception as e:
    print(f"Error: {e}")
