import json
import os

CACHE_DIR = "cache"

def save(stage: str, data: dict):
    """Write to cache/{stage}.json"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(f"{CACHE_DIR}/{stage}.json", "w") as f:
        json.dump(data, f, indent=2)

def load(stage: str) -> dict | None:
    """Read from cache/{stage}.json if it exists, otherwise return None.
    
    For the 'papers' stage, validates that the cached topic matches the current topic.
    """
    path = f"{CACHE_DIR}/{stage}.json"
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        
        # Topic validation for papers stage
        if stage == "papers" and data:
            cached_topic = data.get("topic", "")
            topic_file = f"{CACHE_DIR}/_topic.txt"
            if os.path.exists(topic_file):
                with open(topic_file) as tf:
                    current_topic = tf.read().strip()
                
                # If topics don't match, invalidate cache
                if cached_topic.strip() != current_topic.strip():
                    print(f"  ⚠️  Cache invalidated: topic changed from '{cached_topic}' to '{current_topic}'")
                    return None
        
        return data
    return None
