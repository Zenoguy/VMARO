import json
from utils.schema import safe_parse, call_gemini_with_retry

def run(gap_description: str, topic: str) -> dict:
    print("[Agent4]       Methodology Design")
    
    fallback = {
        "suggested_datasets": [],
        "evaluation_metrics": [],
        "baseline_models": [],
        "experimental_design": "Failed to generate methodology.",
        "tools_and_frameworks": []
    }

    try:
        sys_inst = f"""You are a research methodology expert.
Return ONLY valid JSON matching this schema:
{{
  "suggested_datasets": ["dataset1", "dataset2"],
  "evaluation_metrics": ["metric1", "metric2"],
  "baseline_models": ["baseline1", "baseline2"],
  "experimental_design": "step-by-step methodology",
  "tools_and_frameworks": ["tool1", "tool2"]
}}"""

        prompt = f"""Given this research gap, recommend a concrete
experimental methodology.

Research Gap: {gap_description}
Research Topic: {topic}"""

        for attempt in range(2):
            try:
                response = call_gemini_with_retry(prompt, system_instruction=sys_inst)
                return safe_parse(response.text, required_keys=["suggested_datasets", "evaluation_metrics", "baseline_models", "experimental_design", "tools_and_frameworks"])
            except Exception as e:
                if attempt == 1:
                    print(f"Agent4 Groq failed: {e}")
                    raise

    except Exception as e:
        print(f"Agent4 failed: {e}")
        return fallback
