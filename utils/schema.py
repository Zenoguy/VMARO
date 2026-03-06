import itertools
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

# Filter out empty or None keys
_keys = [k for k in [os.getenv(f"GEMINI_KEY_{i}") for i in range(1, 4)] if k]
# Use itertools.cycle for round-robin, fallback to a single empty string if no keys exist
_key_pool = itertools.cycle(_keys) if _keys else itertools.cycle([""])

def get_api_key() -> str:
    """Return next key from pool."""
    return next(_key_pool)

def clean_json_response(text: str) -> str:
    """
    Strip markdown fences Gemini Flash occasionally wraps around JSON.
    Handles ```json, ```, and surrounding whitespace.
    """
    if not isinstance(text, str):
        return str(text)
        
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()

def safe_parse(text: str) -> dict:
    """
    Calls clean_json_response() then json.loads().
    Raises ValueError on failure.
    """
    cleaned = clean_json_response(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}\nCleaned text was:\n{cleaned}")
