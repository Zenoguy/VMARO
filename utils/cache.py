import json
import os

CACHE_DIR = "cache"

def save(stage: str, data: dict):
    """Write to cache/{stage}.json"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(f"{CACHE_DIR}/{stage}.json", "w") as f:
        json.dump(data, f, indent=2)

def load(stage: str) -> dict | None:
    """Read from cache/{stage}.json if it exists, otherwise return None."""
    path = f"{CACHE_DIR}/{stage}.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None
