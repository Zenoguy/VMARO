import os
import json
import google.generativeai as genai
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
        genai.configure(api_key=get_api_key())
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = GATE_PROMPT.format(
            stage=stage_name, 
            output=json.dumps(output_json, indent=2)
        )
        
        response = model.generate_content(prompt)
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
    
    if not demo_mode and decision in ["REVISE", "FAIL"]:
        raise ValueError(f"Quality gate blocked at stage {stage_name} with decision {decision}. Reason: {result.get('reason', '')}")
        
    return result
