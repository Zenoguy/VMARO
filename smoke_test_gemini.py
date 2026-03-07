"""
Smoke Test — Gemini Flash Connectivity
Run from repo root: python smoke_test_gemini.py
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

from google import genai
from utils.schema import get_api_key, clean_json_response, safe_parse

SEPARATOR = "-" * 50

def test_env_keys():
    print("\n[1/4] Checking .env keys...")
    keys = [os.getenv(f"GEMINI_KEY_{i}") for i in range(1, 4)]
    found = [(i+1, k) for i, k in enumerate(keys) if k]
    missing = [i+1 for i, k in enumerate(keys) if not k]

    for idx, key in found:
        print(f"  ✅ GEMINI_KEY_{idx} = {key[:8]}...{key[-4:]}")
    for idx in missing:
        print(f"  ⚠️  GEMINI_KEY_{idx} = not set")

    if not found:
        print("  ❌ No keys found — add at least GEMINI_KEY_1 to .env")
        sys.exit(1)

    print(f"  → {len(found)} key(s) loaded, {len(missing)} missing")
    return len(found)


def test_basic_completion():
    print("\n[3/4] Testing basic Gemini Flash completion...")
    try:
        client = genai.Client(api_key=get_api_key())
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents="Reply with exactly one word: OK"
        )
        text = response.text.strip()
        if "OK" in text.upper():
            print(f"  ✅ Model responded: '{text}'")
        else:
            print(f"  ⚠️  Unexpected response (model is live but replied): '{text}'")
    except Exception as e:
        print(f"  ❌ Completion failed: {e}")
        sys.exit(1)


def test_json_output():
    print("\n[4/4] Testing structured JSON output + clean_json_response()...")
    try:
        client = genai.Client(api_key=get_api_key())
        prompt = """Return ONLY valid JSON — no markdown, no extra text:
{
  "status": "ok",
  "message": "gemini flash json test passed"
}"""
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt
        )
        raw = response.text
        parsed = safe_parse(raw)

        if parsed.get("status") == "ok":
            print(f"  ✅ JSON parsed cleanly: {parsed}")
        else:
            print(f"  ⚠️  JSON parsed but unexpected content: {parsed}")

        # Also test that clean_json_response handles fenced output
        fenced = "```json\n{\"status\": \"ok\"}\n```"
        assert safe_parse(fenced) == {"status": "ok"}
        print("  ✅ clean_json_response() strips fences correctly")

    except Exception as e:
        print(f"  ❌ JSON test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print(SEPARATOR)
    print("VMARO — Gemini Flash Smoke Test")
    print(SEPARATOR)

    num_keys = test_env_keys()
    test_basic_completion()
    test_json_output()

    print(f"\n{SEPARATOR}")
    print("✅ All Gemini checks passed — ready for Phase 3")
    print(SEPARATOR)