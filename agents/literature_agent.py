import os
import json
import requests
from utils.schema import safe_parse, call_gemini_with_retry

def run(topic: str) -> dict:
    print("[Agent1]       Literature Mining")
    
    # MOCK_MODE check
    if os.getenv("MOCK_MODE", "").lower() == "true":
        with open("mock_data/mock_papers.json") as f:
            return json.load(f)

    fallback = {
        "topic": topic,
        "papers": []
    }

    try:
        # Pass 1 - Semantic Scholar Retrieval
        headers = {}
        ss_key = os.getenv("SEMANTIC_SCHOLAR_KEY")
        if ss_key:
            headers["x-api-key"] = ss_key
            
        url = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
        params = {
            "query": topic,
            "fields": "title,abstract,year,authors,externalIds,citationCount",
            "year": "2018-",
            "limit": 20
        }
        
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        papers = data.get("data", [])
        
        # Filter papers
        filtered = [
            p for p in papers 
            if p.get("abstract") and p.get("abstract", "").strip()
        ]
        
        # Relax year filter if needed
        if len(filtered) < 8:
            params["year"] = "2015-"
            r = requests.get(url, params=params, headers=headers, timeout=15)
            r.raise_for_status()
            papers = r.json().get("data", [])
            filtered = [
                p for p in papers 
                if p.get("abstract") and p.get("abstract", "").strip()
            ]
            
        # Take top 12
        filtered = filtered[:12]
        
        if not filtered:
            return fallback

        # Pass 2 - Summarisation via Gemini
        sys_inst = f"""You are a research assistant.
Return ONLY valid JSON matching this schema:
{{
  "topic": "{topic}",
  "papers": [
    {{
      "title": "exact title from input",
      "year": 2024,
      "summary": "2-3 sentence summary",
      "contribution": "single most novel contribution",
      "source": "DOI or URL"
    }}
  ]
}}"""

        prompt = f"""Below are abstracts on "{topic}" from Semantic Scholar.
For each paper, write a 2–3 sentence plain-English summary and identify the single most
important contribution.

Papers: {json.dumps(filtered)}"""

        # Retry logic for JSON failure
        for attempt in range(2):
            try:
                response = call_gemini_with_retry(prompt, system_instruction=sys_inst)
                return safe_parse(response.text, required_keys=["topic", "papers"])
            except Exception as e:
                if attempt == 1:
                    print(f"Agent1 Gemini failed: {e}")
                    raise
    
    except Exception as e:
        print(f"Agent1 failed: {e}")
        return fallback
