import requests
import json
import time

url = "https://api.semanticscholar.org/graph/v1/paper/search"
params = {"query": "federated learning", "limit": 1}

print("Hitting Semantic Scholar without API key to trigger 429...")
for i in range(50):
    r = requests.get(url, params=params)
    if r.status_code == 429:
        print(f"Triggered 429 on attempt {i+1}")
        print("Response Headers:")
        print(json.dumps(dict(r.headers), indent=2))
        break
else:
    print("Could not trigger 429 easily.")
