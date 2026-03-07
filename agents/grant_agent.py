import json
from utils.schema import safe_parse, call_gemini_with_retry

def run(topic: str, gap_description: str, methodology: dict) -> dict:
    print("[Agent5]       Grant Writing")
    
    fallback = {
        "problem_statement": "Failed to generate grant proposal.",
        "proposed_methodology": "",
        "evaluation_plan": "",
        "expected_contribution": "",
        "timeline": "",
        "budget_estimate": ""
    }

    try:
        sys_inst = f"""You are a grant proposal writer.
Return ONLY valid JSON matching this schema:
{{
  "problem_statement": "2-3 paragraph problem description",
  "proposed_methodology": "detailed approach referencing the methodology",
  "evaluation_plan": "how results will be measured",
  "expected_contribution": "impact and novelty",
  "timeline": "phased 6-month plan",
  "budget_estimate": "cost breakdown with justification"
}}"""

        prompt = f"""Using the identified research gap and proposed
methodology, generate a complete funding-ready grant proposal.

Research Topic: {topic}
Research Gap: {gap_description}
Methodology: {json.dumps(methodology)}"""

        for attempt in range(2):
            try:
                response = call_gemini_with_retry(prompt, system_instruction=sys_inst)
                return safe_parse(response.text, required_keys=["problem_statement", "proposed_methodology", "evaluation_plan", "expected_contribution", "timeline", "budget_estimate"])
            except Exception as e:
                if attempt == 1:
                    print(f"Agent5 Gemini failed: {e}")
                    raise

    except Exception as e:
        print(f"Agent5 failed: {e}")
        return fallback
