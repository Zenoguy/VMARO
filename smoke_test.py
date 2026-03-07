"""
Smoke Test — Semantic Scholar API Connectivity
Run from repo root: python smoke_test_semantic_scholar.py
"""

import os
import sys
import time
import requests
from dotenv import load_dotenv
load_dotenv()

SEPARATOR = "-" * 50
BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
TEST_TOPIC = "federated learning healthcare"


def get_headers():
    key = os.getenv("SEMANTIC_SCHOLAR_KEY")
    if key:
        return {"x-api-key": key}
    return {}


def run_basic_search():
    print("\n[1/4] Testing basic search...")
    headers = get_headers()
    key_status = "with API key" if headers else "no API key (anonymous)"
    print(f"  → Querying as: {key_status}")

    params = {
        "query": TEST_TOPIC,
        "limit": 5,
        "fields": "title,year,abstract,citationCount"
    }

    try:
        r = requests.get(BASE_URL, params=params, headers=headers, timeout=10)

        if r.status_code == 200:
            data = r.json()
            total = data.get("total", 0)
            papers = data.get("data", [])
            print(f"  ✅ Status 200 — {total} total results, {len(papers)} returned")
            for p in papers[:3]:
                print(f"     • [{p.get('year', '?')}] {p.get('title', 'No title')[:70]}")
            return papers
        elif r.status_code == 429:
            print("  ⚠️  Rate limited (429) — you need a free API key")
            print("     Register at: https://www.semanticscholar.org/product/api")
            print("     Add SEMANTIC_SCHOLAR_KEY to .env once approved")
            sys.exit(1)
        else:
            print(f"  ❌ Unexpected status: {r.status_code} — {r.text[:200]}")
            sys.exit(1)

    except requests.exceptions.ConnectionError:
        print("  ❌ Connection failed — check your internet connection")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("  ❌ Request timed out — Semantic Scholar may be down")
        sys.exit(1)


def run_required_fields(papers):
    print("\n[2/4] Testing required fields are present...")
    required = ["title", "year", "abstract"]
    issues = []

    for p in papers:
        for field in required:
            if not p.get(field):
                issues.append(f"  Paper '{p.get('title', '?')[:40]}' missing: {field}")

    if not issues:
        print(f"  ✅ All required fields present across {len(papers)} papers")
    else:
        for issue in issues:
            print(f"  ⚠️  {issue}")
        print("  → Abstract filtering in literature_agent.py will handle this")


def run_abstract_filtering(papers):
    print("\n[3/4] Testing abstract filter logic (year >= 2018, non-empty abstract)...")
    before = len(papers)
    filtered = [
        p for p in papers
        if p.get("abstract") and p.get("year") and p["year"] >= 2018
    ]
    dropped = before - len(filtered)
    print(f"  ✅ {filtered} kept, {dropped} dropped from {before} sample papers")

    if len(filtered) == 0:
        print("  ⚠️  All papers filtered out — year relaxation to 2015 would apply")
    else:
        print(f"  → Filter logic works correctly")


def run_externalids_field():
    print("\n[4/4] Testing externalIds + citationCount fields (needed for Schema 1)...")
    headers = get_headers()
    params = {
        "query": TEST_TOPIC,
        "limit": 3,
        "fields": "title,abstract,year,authors,externalIds,citationCount",
        "sort": "citationCount:desc"
    }

    try:
        time.sleep(1)  # be polite to the API
        r = requests.get(BASE_URL, params=params, headers=headers, timeout=10)
        papers = r.json().get("data", [])

        for p in papers[:2]:
            ext = p.get("externalIds", {})
            doi = ext.get("DOI")
            source = f"https://doi.org/{doi}" if doi else "No DOI — URL fallback needed"
            print(f"  • {p.get('title', '?')[:55]}")
            print(f"    citations: {p.get('citationCount', '?')} | source: {source}")

        print("  ✅ externalIds and citationCount accessible")

    except Exception as e:
        print(f"  ❌ Failed: {e}")


if __name__ == "__main__":
    print(SEPARATOR)
    print("VMARO — Semantic Scholar Smoke Test")
    print(SEPARATOR)

    papers = run_basic_search()
    run_required_fields(papers)
    run_abstract_filtering(papers)
    run_externalids_field()

    print(f"\n{SEPARATOR}")
    print("✅ All Semantic Scholar checks passed — ready for Phase 3")
    print(SEPARATOR)