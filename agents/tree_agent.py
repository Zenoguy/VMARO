import os
import json
from utils.schema import safe_parse, call_gemini_with_retry

def run(papers: dict) -> dict:
    print("[TreeBuilder]  Building thematic tree")
    
    # MOCK_MODE check isn't strictly requested for all agents at the top of run(),
    # but the prompt says literature_agent uses mock_mode flag, others might just rely on tests passing mock dicts.
    # We will enforce schema parsing and fallback.
    
    fallback = {
        "root": papers.get("topic", "Unknown Topic"),
        "themes": [],
        "emerging_directions": []
    }

    try:
        sys_inst = f"""You are a research taxonomist.
Return ONLY valid JSON matching this schema:
{{
  "root": "{papers.get("topic")}",
  "themes": [
    {{ "theme_id": "T1", "theme_name": "...", "papers": [...paper objects...] }}
  ],
  "emerging_directions": ["...", "..."]
}}"""

        prompt = f"""Given these papers on "{papers.get("topic")}", cluster them into
3–5 high-level themes. Identify emerging directions not covered by existing papers.

Papers: {json.dumps(papers)}"""

        for attempt in range(2):
            try:
                response = call_gemini_with_retry(prompt, system_instruction=sys_inst)
                return safe_parse(response.text, required_keys=["root", "themes", "emerging_directions"])
            except Exception as e:
                if attempt == 1:
                    print(f"TreeBuilder Groq failed: {e}")
                    raise

    except Exception as e:
        print(f"TreeBuilder failed: {e}")
        return fallback
