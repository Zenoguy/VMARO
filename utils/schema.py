import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

def get_api_key() -> str:
    """Return the primary API key."""
    return os.getenv("GEMINI_KEY_1", "")

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
