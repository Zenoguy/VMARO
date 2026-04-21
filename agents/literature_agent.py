import os
import json
from utils.schema import safe_parse, call_gemini_with_retry
from utils.multi_api_fetcher import MultiAPIFetcher
from utils.topic_normalizer import normalize_topic

def run(topic: str) -> dict:
    # ── Stage 00: Normalize any freeform user input ───────────────────────
    print("[Stage 00]     Topic Normalization")
    topic_payload = normalize_topic(topic)
    core_topic = topic_payload["core_topic"]
    print(f"  ✓ core_topic:  {core_topic}")
    print(f"  ✓ domain:      {topic_payload['domain']}")
    print(f"  ✓ keywords:    {topic_payload['keywords']}")
    print(f"  ✓ variants:    {topic_payload['query_variants']}\n")

    print("[Agent 1]      Literature Mining")
    
    # MOCK_MODE check
    if os.getenv("MOCK_MODE", "").lower() == "true":
        with open("mock_data/mock_papers.json") as f:
            return json.load(f)

    fallback = {
        "topic": topic,        # raw user input — must match _topic.txt for cache validation
        "papers": []
    }

    try:
        # Pass 1 — Multi-API fan-out using structured payload
        # Fans out over query_variants × domain-selected APIs, then deduplicates
        print(f"  🔍 Starting multi-source retrieval for: '{core_topic}'")
        
        fetcher = MultiAPIFetcher()
        filtered = fetcher.fetch_all(topic_payload, max_papers=20)
        
        if not filtered:
            print("  ❌ No papers found from any source")
            return fallback
        
        print(f"  ✓ Retrieved {len(filtered)} unique papers after deduplication\n")
        
        # Prepare papers for LLM (rename 'source' to 'api_source' for clarity)
        papers_for_llm = []
        for paper in filtered:
            papers_for_llm.append({
                "title": paper.get("title", ""),
                "abstract": paper.get("abstract", ""),
                "year": paper.get("year", 0),
                "authors": paper.get("authors", []),
                "api_source": paper.get("source", "Unknown"),
                "url": paper.get("url", "")
            })
        
        # Pass 2 - Summarisation via Groq in chunks
        chunk_size = 5
        all_summarized_papers = []
        num_chunks = (len(papers_for_llm) + chunk_size - 1) // chunk_size

        print(f"  🧠 [Agent 1] Summarizing {len(papers_for_llm)} papers in {num_chunks} batches...")

        for i in range(0, len(papers_for_llm), chunk_size):
            chunk = papers_for_llm[i : i + chunk_size]
            current_batch = (i // chunk_size) + 1
            print(f"    └─ Batch {current_batch}/{num_chunks} ({len(chunk)} papers)...", end=" ", flush=True)

            sys_inst = f"""You are a research assistant.
Return ONLY valid JSON matching this schema:
{{
  "topic": "{core_topic}",
  "papers": [
    {{
      "title": "exact title from input",
      "year": 2024,
      "summary": "2-3 sentence summary",
      "contribution": "single most novel contribution",
      "api_source": "exact api_source from input",
      "url": "exact url from input"
    }}
  ]
}}"""

            prompt = f"""Write 2–3 sentence plain-English summaries for these papers on "{core_topic}".
Identify the single most important contribution for each.
Keep 'api_source' and 'url' EXACTLY as provided.

Papers: {json.dumps(chunk)}"""

            # Retry logic for JSON failure per chunk
            chunk_success = False
            for attempt in range(2):
                try:
                    response = call_gemini_with_retry(prompt, system_instruction=sys_inst)
                    chunk_result = safe_parse(response.text, required_keys=["papers"])
                    summarized_chunk = chunk_result.get("papers", [])

                    # Post-process: ensure api_source and url are preserved for this chunk
                    source_lookup = {p["title"]: {"api_source": p.get("api_source"), "url": p.get("url")} for p in chunk}

                    for paper in summarized_chunk:
                        title = paper.get("title", "")
                        if not paper.get("api_source") or paper.get("api_source") == "Unknown":
                            if title in source_lookup:
                                paper["api_source"] = source_lookup[title]["api_source"]
                                paper["url"] = source_lookup[title]["url"]
                        if not paper.get("url"):
                            if title in source_lookup:
                                paper["url"] = source_lookup[title]["url"]

                    all_summarized_papers.extend(summarized_chunk)
                    print("✓")
                    chunk_success = True
                    break
                except Exception as e:
                    if attempt == 1:
                        print(f"⚠️  Batch {current_batch} failed: {str(e)[:50]}")
                    else:
                        print("retrying...", end=" ", flush=True)
            
            if not chunk_success:
                # If a chunk fails, we just don't add those papers to the final set
                # but we continue to the next chunk to rescue as much as possible.
                continue

        # Force topic field to raw user input — cache.py validates
        # papers.json["topic"] against _topic.txt, which stores the original.
        return {
            "topic": topic,
            "papers": all_summarized_papers
        }

    except Exception as e:
        print(f"Agent1 failed: {e}")
        return fallback
