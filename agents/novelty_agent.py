import json
from utils.schema import safe_parse, call_gemini_with_retry

def run(grant: dict, tree: dict) -> dict:
    print("[Agent6]       Novelty Scoring")
    
    fallback = {
        "closest_papers": [],
        "similarity_reasoning": "Failed to generate novelty score.",
        "novelty_score": 0,
        "score_justification": ""
    }

    try:
        # Step 1 — Theme Navigation
        theme_names_and_ids = [
            {"theme_id": t.get("theme_id"), "theme_name": t.get("theme_name")} 
            for t in tree.get("themes", [])
        ]
        
        sys_inst1 = f"""You are a research evaluator.
Return ONLY valid JSON matching this schema:
{{
  "selected_theme_ids": ["T1", "T3"],
  "reasoning": "why these themes are most relevant"
}}"""

        prompt_step1 = f"""Given this proposal and a list of research themes,
identify which themes are most related.

Proposal Summary: {grant.get("problem_statement", "")}
Available Themes: {json.dumps(theme_names_and_ids)}"""

        step1_result = None
        for attempt in range(2):
            try:
                response = call_gemini_with_retry(prompt_step1, system_instruction=sys_inst1)
                step1_result = safe_parse(response.text, required_keys=["selected_theme_ids", "reasoning"])
                break
            except Exception as e:
                if attempt == 1:
                    print(f"Agent6 Step 1 Groq failed: {e}")
                    raise
                    
        if not step1_result:
            raise ValueError("Step 1 failed to return parsed JSON")

        selected_theme_ids = step1_result.get("selected_theme_ids", [])
        
        # Step 2 — Paper-level scoring
        filtered_papers = []
        for t in tree.get("themes", []):
            if t.get("theme_id") in selected_theme_ids:
                filtered_papers.extend(t.get("papers", []))
                
        # Cap at 5 papers max
        filtered_papers = filtered_papers[:5]

        sys_inst2 = f"""You are an expert peer reviewer assessing research novelty.
Return ONLY valid JSON matching this schema:
{{
  "closest_papers": ["Paper Title A", "Paper Title B"],
  "similarity_reasoning": "specific similarities found",
  "novelty_score": 78,
  "score_justification": "why this score was given"
}}"""

        prompt_step2 = f"""
Proposal: {json.dumps(grant)}
Related Papers (selected themes only): {json.dumps(filtered_papers)}

Evaluate:
1. Which papers does this most closely resemble?
2. What makes this proposal meaningfully different?
3. Rate novelty 0 (fully replicated) to 100 (completely novel)"""

        for attempt in range(2):
            try:
                response = call_gemini_with_retry(prompt_step2, system_instruction=sys_inst2)
                return safe_parse(response.text, required_keys=["closest_papers", "similarity_reasoning", "novelty_score", "score_justification"])
            except Exception as e:
                if attempt == 1:
                    print(f"Agent6 Step 2 Groq failed: {e}")
                    raise

    except Exception as e:
        print(f"Agent6 failed: {e}")
        return fallback
