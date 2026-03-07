import os
import json
import re
import time
import itertools
from dotenv import load_dotenv

load_dotenv(override=True)

keys = [k for k in [os.getenv(f"GEMINI_KEY_{i}") for i in (1, 2, 3)] if k]
key_pool = itertools.cycle(keys) if keys else None

def get_api_key() -> str:
    """Return the next API key from the pool."""
    return next(key_pool) if key_pool else ""

from google.genai import types

from google import genai

def call_gemini_with_retry(prompt, system_instruction=None, retries=6):
    client = genai.Client(api_key=get_api_key())
    for attempt in range(retries):
        try:
            config = types.GenerateContentConfig(
                response_mime_type="application/json"
            )
            if system_instruction:
                config.system_instruction = system_instruction
                
            return client.models.generate_content(
                model="gemini-flash-latest",
                contents=prompt,
                config=config
            )
        except Exception as e:
            err = str(e)
            if "429" in err:
                match = re.search(r'retryDelay.*?(\d+)s', err)
                wait = int(match.group(1)) + 5 if match else 60
                print(f"  429 — waiting {wait}s before retry {attempt+1}/{retries}")
                time.sleep(wait)
            elif "503" in err and "UNAVAILABLE" in err:
                wait = 15
                print(f"  503 Unavailable — waiting {wait}s before retry {attempt+1}/{retries}")
                time.sleep(wait)
            elif "400" in err and "API_KEY_INVALID" in err:
                print(f"  Invalid API Key — swapping to next key in pool...")
                client = genai.Client(api_key=get_api_key())
            else:
                raise  # non-429/400 errors fail immediately
    raise Exception("Max retries exceeded")

def safe_parse(text: str, required_keys: list = None) -> dict:
    """
    Parses JSON and optionally validates required keys.
    Raises ValueError on failure.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}\\nRaw text was:\\n{text}")
        
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data).__name__}")
        
    if not data:
        raise ValueError("Parsed JSON is empty")
        
    if required_keys:
        missing = [k for k in required_keys if k not in data]
        if missing:
            raise ValueError(f"Missing required keys: {missing}")
            
    return data
