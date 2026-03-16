import httpx

url = "https://api.campaignx.com/api/v1/signup"
data = {
    "team_name": "TechVerse",
    "team_email": "divyansh.shukla688@gmail.com"
}
try:
    with httpx.Client(verify=False) as client: # Disable strict SSL just to get the API key
        response = client.post(url, json=data)
        print("Status:", response.status_code)
        print("Response:", response.text)
except Exception as e:
    print("Error:", e)
