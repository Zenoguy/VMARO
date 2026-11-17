"""
Multi-API Research Paper Fetcher
Fetches papers sequentially: Semantic Scholar → arXiv → CrossRef → OpenAlex → PubMed
Deduplicates by DOI, explicit preprint relationships, and exact normalized title
"""

import os
import re
import time
import json
import math
import unicodedata
import requests
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict


class MultiAPIFetcher:
    """Fetch research papers from multiple sources with deduplication"""
    
    def __init__(self):
        self.ss_key = os.getenv("SEMANTIC_SCHOLAR_KEY", "")
        self.core_key = os.getenv("CORE_API_KEY", "")
        self.user_email = os.getenv("API_EMAIL", "research@example.com")
    
    def _detect_subject_apis(self, domain: str) -> List[str]:
        """
        Select APIs based on the normalized domain from topic_normalizer.
        Uses a clean domain → sources mapping instead of fragile keyword scanning.
        """
        domain_map = {
            "biomedical":     ["semantic_scholar", "pubmed", "crossref"],
            "cs_ai":          ["semantic_scholar", "arxiv"],
            "engineering":    ["semantic_scholar", "crossref", "openalex"],
            "social_science": ["semantic_scholar", "crossref", "openalex"],
            "physics":        ["semantic_scholar", "arxiv"],
            "general":        ["semantic_scholar", "arxiv", "crossref", "openalex"],
        }
        sources = domain_map.get(domain, domain_map["general"])
        print(f"  └─ Domain '{domain}' → using: {', '.join(sources)}")
        return sources
    
    def fetch_all(self, topic_payload: dict, max_papers: int = 20) -> List[Dict]:
        """
        Fetch papers using the structured payload from topic_normalizer (Stage 00).

        Fans out over query_variants for richer corpus coverage, then deduplicates.
        The existing _deduplicate() cleanly handles cross-variant overlap.

        Args:
            topic_payload: Structured dict from normalize_topic() with keys:
                           core_topic, keywords, domain, query_variants, ...
            max_papers:    Maximum papers to return after global deduplication.

        Returns:
            List of deduplicated paper dicts with 'source', 'title', 'abstract', etc.
        """
        core_topic     = topic_payload["core_topic"]
        keywords       = topic_payload.get("keywords", [])
        domain         = topic_payload.get("domain", "general")
        query_variants = topic_payload.get("query_variants") or [core_topic]

        # Domain-driven API selection (no keyword scanning on raw text)
        sources = self._detect_subject_apis(domain)

        all_papers = []

        # Fan out: each query_variant runs across the full source pool
        for query in query_variants:
            print(f"\n  📚 Query: '{query}' across {len(sources)} source(s): {', '.join(sources)}")
            print(f"  {'─' * 70}")

            results_map: Dict[str, List[Dict]] = {}
            with ThreadPoolExecutor(max_workers=len(sources)) as executor:
                future_to_source = {
                    executor.submit(self._fetch_source, source, query, keywords): source
                    for source in sources
                }
                for future in as_completed(future_to_source):
                    source = future_to_source[future]
                    try:
                        _, papers = future.result()
                        results_map[source] = papers
                        print(f"  ✓ {source.upper()}: {len(papers)} papers")
                    except Exception as e:
                        print(f"  ❌ {source.upper()}: {str(e)[:60]}")
                        results_map[source] = []

            for source in sources:
                all_papers.extend(results_map.get(source, []))

        # ── Fallback: web scraping if all queries returned nothing ─────────
        if not all_papers:
            print(f"\n  ⚠️  All APIs returned 0 papers. Trying web scraping fallback...")
            all_papers = self._web_scrape_fallback(core_topic, limit=max_papers)

        print(f"\n  {'─' * 70}")
        print(f"  📊 Total fetched across {len(query_variants)} query variant(s): {len(all_papers)}")

        unique_papers = self._deduplicate(all_papers)
        print(f"  🔍 Unique after dedup: {len(unique_papers)} (removed {len(all_papers) - len(unique_papers)} duplicates)")

        # ── Relevance scoring — keyword/relation overlap + recency + citation ──
        for paper in unique_papers:
            paper["_relevance_score"] = self._score_relevance(paper, topic_payload)

        unique_papers.sort(key=lambda p: p["_relevance_score"], reverse=True)

        if unique_papers:
            scores = [p["_relevance_score"] for p in unique_papers]
            print(f"  🎯 Relevance scores — top: {scores[0]:.1f} | "
                  f"p50: {scores[len(scores)//2]:.1f} | "
                  f"bottom: {scores[-1]:.1f}")

        # ── Persist full ranked pool — downstream agents can re-slice freely ──
        os.makedirs("cache", exist_ok=True)
        pool_path = "cache/paper_pool.json"
        with open(pool_path, "w") as f:
            json.dump(unique_papers, f, indent=2)
        print(f"  💾 Full pool ({len(unique_papers)} papers) saved to {pool_path}")

        # Slice top-N for LLM summarisation (token budget constraint)
        final_papers = unique_papers[:max_papers]

        # Source distribution of final slice
        source_counts: Dict[str, int] = {}
        for p in final_papers:
            src = p.get('source', 'Unknown')
            source_counts[src] = source_counts.get(src, 0) + 1

        print(f"\n  📈 Final selection ({len(final_papers)} papers, ranked by relevance):")
        for src, cnt in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"     • {src}: {cnt} papers")

        if len(unique_papers) < max_papers:
            print(f"\n  ⚠️  Only {len(unique_papers)} unique papers available (requested {max_papers})")

        print(f"  {'─' * 70}\n")
        return final_papers

    def _score_relevance(self, paper: dict, topic_payload: dict) -> float:
        """
        Score a paper's relevance to the normalized topic payload.
        Pure keyword overlap — no embeddings, no extra API calls.

        Weights:
          title keyword match:    +3.0 per hit  (title is the strongest signal)
          abstract keyword match: +1.0 per hit
          relation phrase match:  +2.0 per hit  (relational phrases are specific)
          recency bonus:          +0.1 per year after 2020 (soft preference)
          citation bonus:         log(citations+1) * 0.5   (log-scaled, not dominant)
        """
        score = 0.0
        title    = paper.get("title", "").lower()
        abstract = paper.get("abstract", "").lower()
        keywords = [kw.lower() for kw in topic_payload.get("keywords", [])]
        relations = [r.lower() for r in topic_payload.get("relations", [])]

        for kw in keywords:
            if kw in title:
                score += 3.0
            if kw in abstract:
                score += 1.0

        for rel in relations:
            if rel in abstract:
                score += 2.0

        # Recency bonus — recent work preferred but not dominant
        year = paper.get("year", 0)
        if year > 2020:
            score += (year - 2020) * 0.1

        # Citation bonus — log-scaled so mega-cited papers don't crowd out niche ones
        citations = paper.get("citationCount", 0) or 0
        score += math.log(citations + 1) * 0.5

        return score

    def _fetch_source(self, source: str, query: str, keywords: List[str]):
        """
        Dispatch to the correct fetch method.
        Extracted from the old inline lambda so fetch_all stays readable.
        """
        source_limits = {
            'semantic_scholar': 25, 'arxiv': 15, 'pubmed': 15,
            'crossref': 12, 'openalex': 12, 'core': 10,
        }
        limit = source_limits.get(source, 10)

        if source == 'semantic_scholar':
            return source, self._fetch_semantic_scholar(query, limit=limit)
        elif source == 'arxiv':
            return source, self._fetch_arxiv(query, keywords=keywords, limit=limit)
        elif source == 'pubmed':
            return source, self._fetch_pubmed(query, limit=limit)
        elif source == 'crossref':
            return source, self._fetch_crossref(query, limit=limit)
        elif source == 'openalex':
            return source, self._fetch_openalex(query, limit=limit)
        elif source == 'core':
            return source, self._fetch_core(query, limit=limit)
        else:
            raise ValueError(f"Unknown source: {source}")
    
    # ──────────────────────────────────────────────────────────────────────
    # Web scraping fallback (used only when ALL APIs fail)
    # ──────────────────────────────────────────────────────────────────────

    def _web_scrape_fallback(self, topic: str, limit: int = 20) -> List[Dict]:
        """Fallback scraper: tries arXiv web, then Google Scholar (scholarly)"""
        papers = []

        # 1) arXiv search page
        print(f"  [FALLBACK 1/2] Scraping arXiv web...", end=" ")
        try:
            arxiv_papers = self._scrape_arxiv_web(topic, limit=limit)
            papers.extend(arxiv_papers)
            print(f"✓ Got {len(arxiv_papers)} papers")
        except ImportError as e:
            print(f"⚠️  {e}")
        except Exception as e:
            print(f"❌ {str(e)[:60]}")

        # 2) Google Scholar via scholarly (optional dependency)
        if len(papers) < limit:
            remaining = limit - len(papers)
            print(f"  [FALLBACK 2/2] Scraping Google Scholar (scholarly)...", end=" ")
            try:
                gs_papers = self._scrape_google_scholar(topic, limit=remaining)
                papers.extend(gs_papers)
                print(f"✓ Got {len(gs_papers)} papers")
            except ImportError:
                print(f"⚠️  scholarly not installed — run: pip install scholarly")
            except Exception as e:
                print(f"❌ {str(e)[:60]}")

        return papers

    def _scrape_arxiv_web(self, topic: str, limit: int = 20) -> List[Dict]:
        """Scrape arXiv search results page with BeautifulSoup"""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("beautifulsoup4 not installed — run: pip install beautifulsoup4")

        url = "https://arxiv.org/search/"
        params = {"query": topic, "searchtype": "all", "start": 0}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        r = requests.get(url, params=params, headers=headers, timeout=20)
        r.raise_for_status()

        soup = BeautifulSoup(r.content, "html.parser")
        results = soup.find_all("li", class_="arxiv-result")

        normalized = []
        for item in results[:limit * 2]:  # over-fetch to account for filtered items
            if len(normalized) >= limit:
                break
            try:
                title_elem = item.find("p", class_="title")
                title = title_elem.get_text(strip=True) if title_elem else ""

                # Prefer full abstract, fall back to short
                abstract_elem = (
                    item.find("span", class_="abstract-full")
                    or item.find("span", class_="abstract-short")
                )
                abstract = abstract_elem.get_text(strip=True) if abstract_elem else ""
                abstract = re.sub(r'[▽△]\s*(Less|More)', '', abstract).strip()

                if not abstract or len(abstract) < 50:
                    continue

                authors = []
                authors_elem = item.find("p", class_="authors")
                if authors_elem:
                    authors = [a.get_text(strip=True) for a in authors_elem.find_all("a")]

                year = 0
                date_elem = item.find("p", class_="is-size-7")
                if date_elem:
                    m = re.search(r'\b(20\d{2})\b', date_elem.get_text())
                    if m:
                        year = int(m.group(1))

                url_val = ""
                link_elem = item.find("p", class_="list-title")
                if link_elem:
                    a_tag = link_elem.find("a")
                    if a_tag:
                        url_val = a_tag.get("href", "")

                normalized.append({
                    "title": title,
                    "abstract": abstract,
                    "year": year,
                    "authors": authors,
                    "doi": "",
                    "citationCount": 0,
                    "source": "arXiv (web)",
                    "url": url_val
                })
            except Exception:
                continue

        return normalized

    def _scrape_google_scholar(self, topic: str, limit: int = 10) -> List[Dict]:
        """Scrape Google Scholar using the scholarly library"""
        from scholarly import scholarly

        normalized = []
        for i, result in enumerate(scholarly.search_pubs(topic)):
            if i >= limit:
                break
            bib = result.get("bib", {})
            title = bib.get("title", "")
            abstract = bib.get("abstract", "")

            if not abstract or len(abstract.strip()) < 50:
                continue

            year = 0
            try:
                year = int(bib.get("pub_year", 0))
            except (ValueError, TypeError):
                pass

            authors = bib.get("author", [])
            if isinstance(authors, str):
                authors = [a.strip() for a in authors.split(" and ")]

            normalized.append({
                "title": title,
                "abstract": abstract,
                "year": year,
                "authors": authors,
                "doi": "",
                "citationCount": result.get("num_citations", 0),
                "source": "Google Scholar",
                "url": result.get("pub_url", "")
            })

        return normalized

    # ──────────────────────────────────────────────────────────────────────
    # Primary API fetchers
    # ──────────────────────────────────────────────────────────────────────

    def _fetch_semantic_scholar(self, topic: str, limit: int = 25) -> List[Dict]:
        """Fetch from Semantic Scholar API with retry on rate limit"""
        headers = {}
        if self.ss_key:
            headers["x-api-key"] = self.ss_key
        
        # Use regular search endpoint (not bulk) for better limit control
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": topic,
            "fields": "title,abstract,year,authors,externalIds,citationCount",
            "year": "2018-",
            "limit": limit
        }
        
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        papers = data.get("data", [])
        
        # Normalize format and enforce limit
        normalized = []
        for p in papers:
            # Stop if we've reached the limit
            if len(normalized) >= limit:
                break
                
            if not p.get("abstract") or not p.get("abstract", "").strip():
                continue
            
            doi = p.get("externalIds", {}).get("DOI", "")
            normalized.append({
                "title": p.get("title", ""),
                "abstract": p.get("abstract", ""),
                "year": p.get("year", 0),
                "authors": [a.get("name", "") for a in p.get("authors", [])],
                "doi": doi,
                "citationCount": p.get("citationCount", 0),
                "source": "Semantic Scholar",
                "url": f"https://www.semanticscholar.org/paper/{p.get('paperId', '')}" if p.get('paperId') else ""
            })
        
        return normalized[:limit]  # Extra safety: enforce limit
    
    def _fetch_arxiv(self, topic: str, keywords: List[str] = None, limit: int = 15) -> List[Dict]:
        """
        Fetch from arXiv API.
        When keywords are provided (from topic_normalizer), use them for
        higher-precision multi-term AND matching. Falls back to naive
        word-split on the raw topic string for backward compatibility.
        """
        base_url = "http://export.arxiv.org/api/query"

        if keywords:
            # Use normalized keywords — much higher precision than splitting raw topic.
            # Cap at 6 terms to avoid over-constraining the arXiv AND chain.
            arxiv_query = ' AND '.join(
                [f'all:{kw.replace(" ", "+")}' for kw in keywords[:6]]
            )
        else:
            # Fallback: strip stopwords from raw topic string (old behaviour)
            query_terms = [
                w for w in topic.split()
                if w.lower() not in ('in', 'on', 'the', 'of', 'and', 'a', 'to', 'for', 'with', 'by')
            ]
            arxiv_query = ' AND '.join([f'all:{w}' for w in query_terms])
        
        # Do NOT use quote() here - requests handles URL encoding automatically
        # Using quote() causes double-encoding (%20 → %2520) which breaks the query
        params = {
            "search_query": arxiv_query,
            "max_results": limit,
            "sortBy": "submittedDate",
            "sortOrder": "descending"
        }
        
        r = requests.get(base_url, params=params, timeout=15)
        r.raise_for_status()
        
        # Parse XML response
        import xml.etree.ElementTree as ET
        root = ET.fromstring(r.content)
        
        ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}
        
        normalized = []
        for entry in root.findall('atom:entry', ns):
            title = entry.find('atom:title', ns)
            abstract = entry.find('atom:summary', ns)
            published = entry.find('atom:published', ns)
            doi = entry.find('arxiv:doi', ns)
            link = entry.find('atom:id', ns)
            
            if title is None or abstract is None:
                continue
            
            # Extract year
            year = 0
            if published is not None:
                year_match = re.search(r'(\d{4})', published.text)
                if year_match:
                    year = int(year_match.group(1))
            
            # Get authors
            authors = []
            for author in entry.findall('atom:author', ns):
                name = author.find('atom:name', ns)
                if name is not None:
                    authors.append(name.text)
            
            normalized.append({
                "title": title.text.strip(),
                "abstract": abstract.text.strip(),
                "year": year,
                "authors": authors,
                "doi": doi.text if doi is not None else "",
                "citationCount": 0,
                "source": "arXiv",
                "url": link.text if link is not None else ""
            })
        
        return normalized
    
    def _fetch_pubmed(self, topic: str, limit: int = 15) -> List[Dict]:
        """Fetch from PubMed API"""
        # Step 1: Search for PMIDs
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": topic,
            "retmax": limit,
            "retmode": "json",
            "sort": "relevance"
        }
        
        r = requests.get(search_url, params=search_params, timeout=15)
        r.raise_for_status()
        pmids = r.json().get("esearchresult", {}).get("idlist", [])
        
        if not pmids:
            return []
        
        # Step 2: Fetch details
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml"
        }
        
        time.sleep(0.34)  # PubMed rate limiting
        r = requests.get(fetch_url, params=fetch_params, timeout=15)
        r.raise_for_status()
        
        # Parse XML
        import xml.etree.ElementTree as ET
        root = ET.fromstring(r.content)
        
        normalized = []
        for article in root.findall('.//PubmedArticle'):
            try:
                title_elem = article.find('.//ArticleTitle')
                abstract_elem = article.find('.//AbstractText')
                year_elem = article.find('.//PubDate/Year')
                
                if title_elem is None or abstract_elem is None:
                    continue
                
                # Get authors
                authors = []
                for author in article.findall('.//Author'):
                    lastname = author.find('LastName')
                    forename = author.find('ForeName')
                    if lastname is not None:
                        name = lastname.text
                        if forename is not None:
                            name = f"{forename.text} {name}"
                        authors.append(name)
                
                # Get DOI
                doi = ""
                for article_id in article.findall('.//ArticleId'):
                    if article_id.get('IdType') == 'doi':
                        doi = article_id.text
                        break
                
                # Get PMID for URL
                pmid = article.find('.//PMID')
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid.text}/" if pmid is not None else ""
                
                normalized.append({
                    "title": title_elem.text.strip() if title_elem.text else "",
                    "abstract": abstract_elem.text.strip() if abstract_elem.text else "",
                    "year": int(year_elem.text) if year_elem is not None and year_elem.text else 0,
                    "authors": authors,
                    "doi": doi,
                    "citationCount": 0,
                    "source": "PubMed",
                    "url": url
                })
            except Exception:
                continue
        
        return normalized
    
    def _fetch_crossref(self, topic: str, limit: int = 12) -> List[Dict]:
        """Fetch from CrossRef API"""
        url = "https://api.crossref.org/works"
        params = {
            "query": topic,
            "rows": limit,
            "sort": "relevance",
            "filter": "has-abstract:true,from-pub-date:2018"
        }
        headers = {
            "User-Agent": f"VMARO Research Tool (mailto:{self.user_email})"
        }
        
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        payload = r.json()
        message = payload.get("message") if isinstance(payload, dict) else None
        items = message.get("items") if isinstance(message, dict) else None
        if not isinstance(items, list):
            return []
        
        normalized = []
        for item in items:
            if not isinstance(item, dict):
                continue
            abstract = item.get("abstract")
            if not isinstance(abstract, str) or len(abstract.strip()) < 50:
                continue
            
            # Get authors
            authors = []
            for author in item.get("author", []):
                given = author.get("given", "")
                family = author.get("family", "")
                name = f"{given} {family}".strip()
                if name:
                    authors.append(name)
            
            # Get year
            year = 0
            pub_date = item.get("published", {}) or item.get("published-print", {})
            if pub_date and "date-parts" in pub_date:
                date_parts = pub_date["date-parts"][0]
                if date_parts:
                    year = date_parts[0]
            
            normalized.append({
                "title": item.get("title", [""])[0] if item.get("title") else "",
                "abstract": abstract,
                "year": year,
                "authors": authors,
                "doi": item.get("DOI", ""),
                "citationCount": item.get("is-referenced-by-count", 0),
                "source": "CrossRef",
                "crossref_type": item.get("type"),
                "crossref_relation": item.get("relation"),
                "url": item.get("URL", "")
            })
        
        return normalized
    
    def _fetch_openalex(self, topic: str, limit: int = 12) -> List[Dict]:
        """Fetch from OpenAlex API"""
        url = "https://api.openalex.org/works"
        params = {
            "search": topic,
            "per_page": limit,
            "sort": "cited_by_count:desc",
            "filter": "from_publication_date:2018-01-01"
        }
        headers = {
            "User-Agent": f"mailto:{self.user_email}"
        }
        
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        results = r.json().get("results", [])
        
        normalized = []
        for item in results:
            # Get abstract from inverted index
            abstract = ""
            if item.get("abstract_inverted_index"):
                inv_index = item["abstract_inverted_index"]
                words = {}
                for word, positions in inv_index.items():
                    for pos in positions:
                        words[pos] = word
                abstract = " ".join([words[i] for i in sorted(words.keys())])
            
            if not abstract or len(abstract.strip()) < 50:
                continue
            
            # Get authors
            authors = []
            for authorship in item.get("authorships", []):
                author = authorship.get("author", {})
                name = author.get("display_name", "")
                if name:
                    authors.append(name)
            
            # Extract DOI
            doi = ""
            if item.get("doi"):
                doi = item["doi"].replace("https://doi.org/", "")
            
            normalized.append({
                "title": item.get("title", ""),
                "abstract": abstract,
                "year": item.get("publication_year", 0),
                "authors": authors,
                "doi": doi,
                "citationCount": item.get("cited_by_count", 0),
                "source": "OpenAlex",
                "url": item.get("doi", "")
            })
        
        return normalized
    
    def _fetch_core(self, topic: str, limit: int = 10) -> List[Dict]:
        """Fetch from CORE API"""
        if not self.core_key:
            return []
        
        url = "https://api.core.ac.uk/v3/search/works"
        headers = {
            "Authorization": f"Bearer {self.core_key}"
        }
        params = {
            "q": topic,
            "limit": limit
        }
        
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        results = r.json().get("results", [])
        
        normalized = []
        for item in results:
            abstract = item.get("abstract", "")
            if not abstract or len(abstract.strip()) < 50:
                continue
            
            authors = []
            for author in item.get("authors", []):
                name = author.get("name", "")
                if name:
                    authors.append(name)
            
            normalized.append({
                "title": item.get("title", ""),
                "abstract": abstract,
                "year": item.get("yearPublished", 0),
                "authors": authors,
                "doi": item.get("doi", ""),
                "citationCount": 0,
                "source": "CORE",
                "url": item.get("downloadUrl", "")
            })
        
        return normalized
    
    @staticmethod
    def _normalize_doi(value):
        if not isinstance(value, str):
            return ""
        value = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '',
                       value.strip(), flags=re.I).strip().casefold()
        return value if re.fullmatch(r'10\.\d{4,9}/\S+', value) else ""

    def _preprint_links(self, papers):
        """Return isolated, directed DOI pairs from Crossref deposits."""
        incident = defaultdict(set)
        work_types = defaultdict(set)
        for paper in papers:
            doi = self._normalize_doi(paper.get("doi"))
            if not doi or paper.get("source") != "CrossRef":
                continue
            work_type = paper.get("crossref_type")
            if isinstance(work_type, str):
                work_types[doi].add(work_type)
            relations = paper.get("crossref_relation")
            if not isinstance(relations, dict):
                continue
            for kind in ("is-preprint-of", "has-preprint"):
                entries = relations.get(kind)
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict) or entry.get("id-type") != "doi":
                        continue
                    target = self._normalize_doi(entry.get("id"))
                    if not target:
                        continue
                    edge = (doi, target) if kind == "is-preprint-of" else (target, doi)
                    incident[doi].add(edge)
                    incident[target].add(edge)

        # Include claims about unfetched DOIs in the conflict check. A reverse
        # claim, a chain, or multiple candidate partners makes a link ambiguous.
        publication_types = {"journal-article", "proceedings-article", "book-chapter"}
        return {
            preprint: publication
            for preprint, edges in incident.items()
            if len(edges) == 1
            for subject, publication in edges
            if subject == preprint and publication != preprint
            and len(incident[publication]) == 1
            and not work_types[preprint].intersection(publication_types)
            and "posted-content" not in work_types[publication]
        }

    @staticmethod
    def _first_author_parts(paper):
        """Read one author entry. Only a comma explicitly signals surname-first."""
        authors = paper.get("authors")
        if not isinstance(authors, (list, tuple)) or not authors:
            return None
        name = authors[0]
        if not isinstance(name, str):
            return None
        name = unicodedata.normalize("NFC", unicodedata.normalize("NFKC", name).casefold())
        name = name.translate(str.maketrans({"’": "'", "‐": "-", "‑": "-"}))
        parts = name.split(",")
        if len(parts) == 2:
            family, given = (part.strip() for part in parts)
        elif len(parts) == 1:
            tokens = name.split()
            if len(tokens) < 2:
                return None
            family, given = tokens[-1], " ".join(tokens[:-1])
        else:
            return None

        def name_word(word):
            # Retain accents and meaningful apostrophes and hyphens.
            return all(
                part and part[0].isalpha()
                and all(c.isalpha() or unicodedata.category(c).startswith("M") for c in part)
                for part in re.split(r"[-']", word)
            )

        given = tuple(token.removesuffix(".") if len(token) == 2 else token
                      for token in given.split())
        family = tuple(family.split())
        if (not given or not family or not all(map(name_word, given + family))
                or any(len(word) == 1 for word in family)):
            return None
        return family, given

    @staticmethod
    def _authors_match(left, right):
        if left is None or right is None:
            return False
        left_family, left_given = left
        right_family, right_given = right
        if left_family != right_family or len(left_given) != len(right_given):
            return False
        # An initial can abbreviate a compatible given name, but two
        # initial-only entries do not provide enough evidence on their own.
        if not any(len(word) > 1 for word in left_given + right_given):
            return False
        return all(
            a == b or (min(len(a), len(b)) == 1 and a[0] == b[0])
            for a, b in zip(left_given, right_given)
        )

    def _deduplicate(self, papers: List[Dict]) -> List[Dict]:
        """Group directly compatible records, retaining their provenance."""
        links = self._preprint_links(papers)
        publications = set(links.values())

        def doi_of(p):
            return self._normalize_doi(p.get("doi"))

        def title_of(p):
            value = p.get("title")
            if not isinstance(value, str):
                return ""
            return ' '.join(re.sub(r'[^\w\s]', '', value.casefold()).split())

        def compatible(a, b):
            da, db = doi_of(a), doi_of(b)
            if da and db:
                return da == db or links.get(da) == db or links.get(db) == da
            # An unparseable supplied DOI is not evidence of an absent DOI.
            if (a.get("doi") and not da) or (b.get("doi") and not db):
                return False
            title = title_of(a)
            return bool(title and title == title_of(b) and self._authors_match(
                self._first_author_parts(a), self._first_author_parts(b)
            ))

        # Resolve DOI groups first. Among DOI-free records, consider fuller
        # names first so an initial can be checked against competing names.
        def match_order(item):
            _, paper = item
            if doi_of(paper):
                return (0, 0)
            author = self._first_author_parts(paper)
            return (1, sum(len(word) == 1 for word in author[1]) if author else 0)

        groups = []
        ordered = sorted(enumerate(papers), key=match_order)
        for index, paper in ordered:
            matches = [group for group in groups
                       if all(compatible(paper, member) for _, member in group)]
            if len(matches) == 1:
                matches[0].append((index, paper))
            else:
                groups.append([(index, paper)])

        result = []
        for group in sorted(groups, key=lambda g: min(i for i, _ in g)):
            # Prefer the publication named by a verified relationship.
            group.sort(key=lambda item: (
                doi_of(item[1]) not in publications, not bool(doi_of(item[1])), item[0]
            ))
            primary = dict(group[0][1])
            if len(group) > 1:
                primary_doi = doi_of(primary)
                for _, other in group[1:]:
                    for key, value in other.items():
                        # These fields describe a particular version or source.
                        if doi_of(other) != primary_doi:
                            if key in ("crossref_type", "crossref_relation"):
                                continue
                            if primary_doi in publications and key in ("source", "url"):
                                continue
                        if key not in primary or primary[key] in (None, '', [], 0):
                            primary[key] = value
                primary["duplicate_records"] = [dict(p) for _, p in group[1:]]
            result.append(primary)
        return result
