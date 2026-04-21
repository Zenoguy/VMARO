"""
Smoke Test — Groq API Connectivity
Run from repo root: python smoke_test_gemini.py
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

from groq import Groq
from utils.schema import get_api_key, safe_parse

SEPARATOR = "-" * 50

def test_env_keys():
    print("\n[1/4] Checking .env keys...")
    keys = [os.getenv(f"GROQ_API_KEY_{i}") for i in range(1, 4)]
    found = [(i+1, k) for i, k in enumerate(keys) if k]
    missing = [i+1 for i, k in enumerate(keys) if not k]

    for idx, key in found:
        print(f"  ✅ GROQ_API_KEY_{idx} = {key[:8]}...{key[-4:]}")
    for idx in missing:
        print(f"  ⚠️  GROQ_API_KEY_{idx} = not set")

    if not found:
        print("  ❌ No keys found — add at least GROQ_API_KEY_1 to .env")
        sys.exit(1)

    print(f"  → {len(found)} key(s) loaded, {len(missing)} missing")
    return len(found)


def test_basic_completion():
    print("\n[3/4] Testing basic Groq completion...")
    try:
        client = Groq(api_key=get_api_key())
        response = client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=[{"role": "user", "content": "Reply with exactly one word: OK"}],
            temperature=0.7
        )
        text = response.choices[0].message.content.strip()
        if "OK" in text.upper():
            print(f"  ✅ Model responded: '{text}'")
        else:
            print(f"  ⚠️  Unexpected response (model is live but replied): '{text}'")
    except Exception as e:
        print(f"  ❌ Completion failed: {e}")
        sys.exit(1)


def test_json_output():
    print("\n[4/4] Testing structured JSON output...")
    try:
        client = Groq(api_key=get_api_key())
        prompt = """Return ONLY valid JSON — no markdown, no extra text:
{
  "status": "ok",
  "message": "groq json test passed"
}"""
        response = client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        raw = response.choices[0].message.content
        parsed = safe_parse(raw)

        if parsed.get("status") == "ok":
            print(f"  ✅ JSON parsed cleanly: {parsed}")
        else:
            print(f"  ⚠️  JSON parsed but unexpected content: {parsed}")

    except Exception as e:
        print(f"  ❌ JSON test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print(SEPARATOR)
    print("VMARO — Groq API Smoke Test")
    print(SEPARATOR)

    num_keys = test_env_keys()
    test_basic_completion()
    test_json_output()

    print(f"\n{SEPARATOR}")
    print("✅ All Groq checks passed — ready for Phase 3")
    print(SEPARATOR)