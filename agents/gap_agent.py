import json
from utils.schema import safe_parse, call_gemini_with_retry

def run(tree: dict, trends: dict) -> dict:
    print("[Agent3]       Gap Identification")
    
    fallback = {
        "identified_gaps": [],
        "selected_gap": ""
    }

    try:
        sys_inst = f"""You are a research gap analyst.
Return ONLY valid JSON matching this schema:
{{
  "identified_gaps": [
    {{ "gap_id": "G1", "description": "...", "why_underexplored": "..." }}
  ],
  "selected_gap": "G1"
}}"""

        prompt = f"""Given this research tree and identified trends, find
underexplored intersections that represent meaningful research gaps.

Tree: {json.dumps(tree)}
Identified Trends: {json.dumps(trends)}"""

        for attempt in range(2):
            try:
                response = call_gemini_with_retry(prompt, system_instruction=sys_inst)
                return safe_parse(response.text, required_keys=["identified_gaps", "selected_gap"])
            except Exception as e:
                if attempt == 1:
                    print(f"Agent3 Groq failed: {e}")
                    raise

    except Exception as e:
        print(f"Agent3 failed: {e}")
        return fallback
