import json
from utils.schema import safe_parse, call_gemini_with_retry

def run(tree: dict) -> dict:
    print("[Agent2]       Trend Analysis")
    
    fallback = {
        "dominant_clusters": [],
        "emerging_trends": []
    }

    try:
        sys_inst = """You are a research trend analyst.
Return ONLY valid JSON matching this schema:
{
  "dominant_clusters": ["cluster 1", "cluster 2"],
  "emerging_trends": ["trend 1", "trend 2"]
}"""

        prompt = f"""Analyze this hierarchical research tree and identify
dominant research clusters and emerging directions.

Tree: {json.dumps(tree)}"""

        for attempt in range(2):
            try:
                response = call_gemini_with_retry(prompt, system_instruction=sys_inst)
                return safe_parse(response.text, required_keys=["dominant_clusters", "emerging_trends"])
            except Exception as e:
                if attempt == 1:
                    print(f"Agent2 Groq failed: {e}")
                    raise

    except Exception as e:
        print(f"Agent2 failed: {e}")
        return fallback
