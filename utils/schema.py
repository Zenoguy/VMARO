import os
import json
import re
import time
import itertools
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

keys = [k for k in [os.getenv(f"GROQ_API_KEY_{i}") for i in (1, 2, 3)] if k]
if not keys and os.getenv("GROQ_API_KEY"):
    keys = [os.getenv("GROQ_API_KEY")]
key_pool = itertools.cycle(keys) if keys else None

def get_key_pool():
    global key_pool
    keys = [k for k in [os.getenv(f"GROQ_API_KEY_{i}") for i in (1, 2, 3)] if k]
    if not keys and os.getenv("GROQ_API_KEY"):
        keys = [os.getenv("GROQ_API_KEY")]
    if keys:
        if not key_pool:
            key_pool = itertools.cycle(keys)
    else:
        key_pool = None
    return key_pool

def get_api_key() -> str:
    """Return the next API key from the pool."""
    pool = get_key_pool()
    return next(pool) if pool else ""

def get_groq_client():
    key = get_api_key()
    return Groq(api_key=key) if key else Groq()

def call_gemini_with_retry(prompt, system_instruction=None, retries=6):
    """
    Call Groq API with retry logic.
    Renamed from call_gemini_with_retry for backward compatibility.
    """
    client = get_groq_client()
    model_name = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    for attempt in range(retries):
        try:
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.6,
                max_completion_tokens=2048,
                top_p=0.95,
            )
            
            # Create a response object that mimics Gemini's structure
            class GroqResponse:
                def __init__(self, content):
                    self.text = content
                    
            return GroqResponse(response.choices[0].message.content)
            
        except Exception as e:
            err = str(e)
            if "429" in err or "rate_limit" in err.lower():
                # Be more specific to avoid matching random request IDs ending in 's'
                match = re.search(r'try again in (\d+\.?\d*)s', err.lower()) or re.search(r'retry after (\d+)', err.lower())
                wait = int(float(match.group(1))) + 2 if match else 30
                # Cap maximum wait time to 60 seconds to prevent getting stuck
                wait = min(max(wait, 5), 60)
                print(f"  429 Rate Limit — waiting {wait}s before retry {attempt+1}/{retries}")
                time.sleep(wait)
                client = get_groq_client() # Rotate key on 429
            elif "503" in err or "unavailable" in err.lower():
                wait = 15
                print(f"  503 Unavailable — waiting {wait}s before retry {attempt+1}/{retries}")
                time.sleep(wait)
            elif "401" in err or "invalid_api_key" in err.lower() or "invalid api key" in err.lower():
                print(f"  Invalid API Key — swapping to next key in pool...")
                client = get_groq_client()
            else:
                print(f"  ⚠️  Groq error: {err[:120]}")
                raise  # non-429/401/503 errors fail immediately
    raise Exception("Max retries exceeded")

def safe_parse(text: str, required_keys: list = None) -> dict:
    """
    Parses JSON and optionally validates required keys.
    Raises ValueError on failure.
    """
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```[a-zA-Z]*\n', '', text)
        text = re.sub(r'\n```$', '', text)
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
