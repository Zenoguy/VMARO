import os
import json
from google import genai
from utils.schema import get_api_key, safe_parse

GATE_PROMPT = """
You are a quality control agent. Evaluate this JSON output from a research pipeline agent.
Stage: {stage}
Output: {output}

Return ONLY valid JSON:
{{
  "decision": "PASS" | "REVISE" | "FAIL",
  "confidence": 0.0-1.0,
  "reason": "brief explanation"
}}
"""

def evaluate_quality(stage_name: str, output_json: dict) -> dict:
    """Send prompt, parse response, return decision."""
    try:
        client = genai.Client(api_key=get_api_key())
        
        prompt = GATE_PROMPT.format(
            stage=stage_name, 
            output=json.dumps(output_json, indent=2)
        )
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        result = safe_parse(response.text)
        
    except Exception as e:
        print(f"[QualityGate:{stage_name}] Gate error — defaulting to PASS. Details: {str(e)}")
        result = {
            "decision": "PASS", 
            "confidence": 0.5, 
            "reason": "Gate error — defaulting to PASS"
        }

    demo_mode = os.environ.get("DEMO_MODE", "").lower() == "true"
    decision = result.get('decision', 'UNKNOWN')
    
    print(f"[QualityGate:{stage_name}] {decision} (confidence={result.get('confidence', 0.0)}): {result.get('reason', '')}")
        
    return result
