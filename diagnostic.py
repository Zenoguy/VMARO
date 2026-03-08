#!/usr/bin/env python3
"""
VMARO Diagnostic Script
-----------------------
Tests the Semantic Scholar API and shows exactly what data flows into Groq.
No Groq calls are made — this only tests the retrieval + filtering step.

Usage:
    python diagnostic.py "Your Research Topic"
    python diagnostic.py                          # defaults to "Reinforcement Learning in Deep Learning"
"""

import sys
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

topic = sys.argv[1] if len(sys.argv) > 1 else "Reinforcement Learning in Deep Learning"

print("=" * 70)
print(f"  VMARO DIAGNOSTIC — Literature Pipeline Debug")
print(f"  Topic: {topic}")
print("=" * 70)

# ── Step 0: Environment Check ────────────────────────────────────────────
print("\n── STEP 0: Environment Check ──")
mock_mode = os.getenv("MOCK_MODE", "").lower()
demo_mode = os.getenv("DEMO_MODE", "").lower()
ss_key = os.getenv("SEMANTIC_SCHOLAR_KEY", "")
groq_keys = [os.getenv(f"GROQ_API_KEY_{i}", "") for i in (1, 2, 3)]
groq_keys_present = sum(1 for k in groq_keys if k)

print(f"  MOCK_MODE     = '{mock_mode}' {'⚠️  MOCK ON — literature_agent will return mock_papers.json!' if mock_mode == 'true' else '✅'}")
print(f"  DEMO_MODE     = '{demo_mode}'")
print(f"  SS_KEY        = {'set' if ss_key else 'not set (using anonymous access)'}")
print(f"  GROQ_API_KEY_*  = {groq_keys_present}/3 keys configured")

if mock_mode == "true":
    print("\n  ⚠️  MOCK_MODE is true — literature_agent.py will NOT call Semantic Scholar.")
    print("     It will return mock_data/mock_papers.json regardless of topic.")
    print("     Set MOCK_MODE=false in .env and restart to use real APIs.")

# ── Step 1: Raw Semantic Scholar Call ────────────────────────────────────
print("\n── STEP 1: Semantic Scholar API Call (year ≥ 2018) ──")
url = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
headers = {}
if ss_key:
    headers["x-api-key"] = ss_key

params = {
    "query": topic,
    "fields": "title,abstract,year,authors,externalIds,citationCount",
    "year": "2018-",
    "limit": 20
}

print(f"  URL: {url}")
print(f"  Query: {params['query']}")
print(f"  Year filter: {params['year']}")
print(f"  Limit: {params['limit']}")

try:
    r = requests.get(url, params=params, headers=headers, timeout=15)
    print(f"  HTTP Status: {r.status_code}")
    
    if r.status_code != 200:
        print(f"  ❌ API Error: {r.text[:500]}")
        sys.exit(1)
    
    data = r.json()
    papers_raw = data.get("data", [])
    total_results = data.get("total", 0)
    print(f"  Total matches in Semantic Scholar: {total_results:,}")
    print(f"  Papers returned in this page: {len(papers_raw)}")
    
except Exception as e:
    print(f"  ❌ Request failed: {e}")
    sys.exit(1)

# ── Step 2: Filtering ───────────────────────────────────────────────────
print("\n── STEP 2: Filtering (remove empty abstracts) ──")
filtered = [
    p for p in papers_raw 
    if p.get("abstract") and p.get("abstract", "").strip()
]
print(f"  Before filter: {len(papers_raw)} papers")
print(f"  After filter:  {len(filtered)} papers (removed {len(papers_raw) - len(filtered)} with empty abstracts)")

# Check if year relaxation would be needed
if len(filtered) < 8:
    print(f"\n  ⚠️  Only {len(filtered)} papers — would relax year to 2015")
    params["year"] = "2015-"
    try:
        r2 = requests.get(url, params=params, headers=headers, timeout=15)
        data2 = r2.json()
        papers_raw2 = data2.get("data", [])
        filtered = [p for p in papers_raw2 if p.get("abstract") and p.get("abstract", "").strip()]
        print(f"  After relaxation: {len(filtered)} papers (year ≥ 2015)")
    except Exception as e:
        print(f"  ❌ Relaxed query failed: {e}")

# Take top 12
filtered = filtered[:12]
print(f"  After top-12 cap: {len(filtered)} papers")

# ── Step 3: Paper Details ───────────────────────────────────────────────
print("\n── STEP 3: Papers That Would Be Sent to Groq ──")
for i, p in enumerate(filtered):
    title = p.get("title", "?")
    year = p.get("year", "?")
    cites = p.get("citationCount", 0)
    abstract_len = len(p.get("abstract", ""))
    authors = [a.get("name", "?") for a in p.get("authors", [])[:3]]
    author_str = ", ".join(authors)
    if len(p.get("authors", [])) > 3:
        author_str += f" +{len(p['authors'])-3} more"
    
    print(f"\n  [{i+1}] {title}")
    print(f"      Year: {year} | Citations: {cites} | Abstract: {abstract_len} chars")
    print(f"      Authors: {author_str}")

# ── Step 4: Groq Prompt Preview ────────────────────────────────────────
print("\n\n── STEP 4: What Gets Sent to Groq ──")

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

print(f"  System instruction length: {len(sys_inst)} chars")
print(f"  Prompt length: {len(prompt)} chars")
print(f"  Approximate tokens: ~{(len(sys_inst) + len(prompt)) // 4}")

# ── Step 5: Size Summary ────────────────────────────────────────────────
print("\n\n── STEP 5: Summary ──")
total_chars = sum(len(p.get("abstract", "")) for p in filtered)
print(f"  Papers to summarize: {len(filtered)}")
print(f"  Total abstract chars: {total_chars:,}")
print(f"  Avg abstract length: {total_chars // max(len(filtered), 1)} chars")
print(f"  Payload to Groq: {len(prompt):,} chars (~{len(prompt)//4} tokens)")
print()

if len(filtered) == 0:
    print("  ❌ NO PAPERS SURVIVED FILTERING — Groq will get an empty list!")
    print("     Try a broader topic or check your network connection.")
elif len(filtered) < 8:
    print(f"  ⚠️  Only {len(filtered)} papers — results may be thin. Consider a broader topic.")
else:
    print(f"  ✅ {len(filtered)} papers ready for Groq summarization.")
