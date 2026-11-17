import os
import json
from utils.schema import safe_parse, call_gemini_with_retry

def _format_paper(paper: dict) -> dict:
    url = paper.get("url") or paper.get("source") or ""
    source = paper.get("source") or paper.get("url") or ""
    return {
        "title": paper.get("title", "Untitled Paper"),
        "year": paper.get("year", 2024),
        "summary": paper.get("summary", ""),
        "contribution": paper.get("contribution", ""),
        "url": url,
        "source": source,
        "api_source": paper.get("api_source", "Unknown")
    }

def run(papers: dict) -> dict:
    print("[TreeBuilder]  Building thematic tree")
    
    # MOCK_MODE check
    if os.getenv("MOCK_MODE", "").lower() == "true":
        with open("mock_data/mock_tree.json") as f:
            return json.load(f)

    # Safe parameter handling
    if isinstance(papers, dict):
        topic = papers.get("topic", "Unknown Topic")
        paper_list = papers.get("papers", [])
    elif isinstance(papers, list):
        topic = "Unknown Topic"
        paper_list = papers
    else:
        topic = "Unknown Topic"
        paper_list = []

    fallback = {
        "root": topic,
        "themes": [],
        "emerging_directions": []
    }

    if not paper_list:
        print("  ⚠️ No papers provided to TreeBuilder.")
        return fallback

    # Index raw papers for mapping
    paper_lookup = {}
    for idx, p in enumerate(paper_list):
        if isinstance(p, dict):
            title = p.get("title", "").strip()
            if title:
                paper_lookup[title.lower()] = p
                paper_lookup[str(idx + 1)] = p

    try:
        # Prepare compact papers for taxonomist clustering
        compact_papers = []
        for i, p in enumerate(paper_list):
            if isinstance(p, dict):
                compact_papers.append({
                    "id": i + 1,
                    "title": p.get("title", f"Paper {i+1}"),
                    "year": p.get("year", 2024),
                    "summary": (p.get("summary") or "")[:250],
                    "contribution": (p.get("contribution") or "")[:200]
                })

        sys_inst = f"""You are a research taxonomist.
Cluster the given research papers into 3 to 5 high-level thematic clusters.
Identify emerging research directions not adequately covered by existing papers.

Return ONLY a valid JSON object matching this schema:
{{
  "root": "{topic}",
  "themes": [
    {{
      "theme_id": "T1",
      "theme_name": "Concise Theme Name",
      "paper_ids": [1, 2]
    }}
  ],
  "emerging_directions": [
    "Emerging direction 1",
    "Emerging direction 2"
  ]
}}"""

        prompt = f"""Cluster these {len(compact_papers)} papers on "{topic}" into 3–5 themes.
Identify 2–4 emerging research directions.

Papers:
{json.dumps(compact_papers, indent=2)}"""

        parsed = None
        for attempt in range(2):
            try:
                response = call_gemini_with_retry(prompt, system_instruction=sys_inst)
                parsed = safe_parse(response.text, required_keys=["root", "themes", "emerging_directions"])
                break
            except Exception as e:
                if attempt == 1:
                    print(f"TreeBuilder Groq failed: {e}")
                    raise

        if not parsed:
            return fallback

        # Post-process: Reconstruct full paper objects in each theme
        themes_output = []
        assigned_titles = set()

        raw_themes = parsed.get("themes", [])
        if not isinstance(raw_themes, list):
            raw_themes = []

        for i, t in enumerate(raw_themes):
            if not isinstance(t, dict):
                continue
            theme_id = t.get("theme_id") or f"T{i+1}"
            theme_name = t.get("theme_name") or f"Theme {i+1}"
            
            theme_papers = []
            
            # Check paper_ids
            for pid in t.get("paper_ids", []):
                p_match = paper_lookup.get(str(pid))
                if p_match and p_match.get("title") not in assigned_titles:
                    theme_papers.append(_format_paper(p_match))
                    assigned_titles.add(p_match.get("title"))

            # Check paper_titles or papers list
            paper_refs = t.get("paper_titles") or t.get("papers") or []
            for ref in paper_refs:
                if isinstance(ref, str):
                    p_match = paper_lookup.get(ref.strip().lower())
                    if p_match and p_match.get("title") not in assigned_titles:
                        theme_papers.append(_format_paper(p_match))
                        assigned_titles.add(p_match.get("title"))
                    elif ref.strip() and ref not in assigned_titles:
                        theme_papers.append({
                            "title": ref.strip(),
                            "year": 2024,
                            "summary": "",
                            "contribution": "",
                            "url": "",
                            "source": "",
                            "api_source": "Unknown"
                        })
                        assigned_titles.add(ref)
                elif isinstance(ref, dict):
                    title = ref.get("title", "").strip()
                    p_match = paper_lookup.get(title.lower())
                    if p_match:
                        merged = dict(p_match)
                        merged.update(ref)
                        theme_papers.append(_format_paper(merged))
                    else:
                        theme_papers.append(_format_paper(ref))
                    if title:
                        assigned_titles.add(title)

            themes_output.append({
                "theme_id": theme_id,
                "theme_name": theme_name,
                "papers": theme_papers
            })

        # Ensure any unassigned papers are appended to themes so no papers are dropped
        unassigned = [p for p in paper_list if isinstance(p, dict) and p.get("title") not in assigned_titles]
        if unassigned:
            if themes_output:
                for p in unassigned:
                    themes_output[0]["papers"].append(_format_paper(p))
            else:
                themes_output.append({
                    "theme_id": "T1",
                    "theme_name": "General Synthesis",
                    "papers": [_format_paper(p) for p in unassigned]
                })

        directions = parsed.get("emerging_directions", [])
        if not isinstance(directions, list):
            directions = [str(directions)] if directions else []

        return {
            "root": parsed.get("root") or topic,
            "themes": themes_output,
            "emerging_directions": directions
        }

    except Exception as e:
        print(f"TreeBuilder failed: {e}")
        return fallback
