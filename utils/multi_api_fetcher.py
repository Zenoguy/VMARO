"""
Multi-API Research Paper Fetcher
Fetches papers sequentially: Semantic Scholar → arXiv → CrossRef → OpenAlex → PubMed
Includes automatic deduplication by DOI and title similarity
"""

import os
import re
import time
import requests
from typing import List, Dict


class MultiAPIFetcher:
    """Fetch research papers from multiple sources with deduplication"""
    
    def __init__(self):
        self.ss_key = os.getenv("SEMANTIC_SCHOLAR_KEY", "")
        self.core_key = os.getenv("CORE_API_KEY", "")
        self.user_email = os.getenv("API_EMAIL", "research@example.com")
    
    def _detect_subject_apis(self, topic: str) -> List[str]:
        """Intelligently select APIs based on topic keywords"""
        topic_lower = topic.lower()
        
        # Always include Semantic Scholar as primary source (fetched first)
        sources = ['semantic_scholar']
        
        # Medical/Biology/Healthcare topics
        medical_keywords = ['health', 'medical', 'clinical', 'patient', 'disease', 'cancer', 
                          'drug', 'hospital', 'therapy', 'diagnosis', 'biology', 'biomedical', 
                          'treatment', 'pathology', 'epidemiology']
        if any(kw in topic_lower for kw in medical_keywords):
            sources.extend(['pubmed', 'crossref'])
            print(f"  └─ Detected medical topic, adding PubMed + CrossRef")
        
        # Computer Science/AI/Physics/Math topics
        cs_keywords = ['learning', 'algorithm', 'neural', 'deep', 'machine', 'ai', 'computer',
                      'network', 'software', 'data', 'model', 'optimization', 'quantum', 'physics',
                      'programming', 'computational']
        if any(kw in topic_lower for kw in cs_keywords):
            sources.append('arxiv')
            print(f"  └─ Detected CS/AI topic, adding arXiv")
        
        # Engineering/Interdisciplinary topics
        engineering_keywords = ['engineering', 'system', 'control', 'robotics', 'sensor', 
                               'material', 'design', 'manufacturing', 'industrial']
        if any(kw in topic_lower for kw in engineering_keywords):
            if 'crossref' not in sources:
                sources.append('crossref')
            sources.append('openalex')
            print(f"  └─ Detected engineering topic, adding CrossRef + OpenAlex")
        
        # Social sciences/Economics
        social_keywords = ['social', 'economic', 'policy', 'education', 'psychology', 
                          'behavior', 'survey', 'qualitative', 'sociology']
        if any(kw in topic_lower for kw in social_keywords):
            if 'crossref' not in sources:
                sources.append('crossref')
            if 'openalex' not in sources:
                sources.append('openalex')
            print(f"  └─ Detected social science topic, adding CrossRef + OpenAlex")
        
        # If no specific domain detected, use general sources
        if len(sources) == 1:
            sources.extend(['arxiv', 'crossref', 'openalex'])
            print(f"  └─ General topic, using broad coverage")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_sources = []
        for s in sources:
            if s not in seen:
                seen.add(s)
                unique_sources.append(s)
        
        return unique_sources
    
    def fetch_all(self, topic: str, max_papers: int = 20, sources: List[str] = None, auto_select: bool = True) -> List[Dict]:
        """
        Fetch papers from multiple sources SEQUENTIALLY and deduplicate
        
        Fetching order: Semantic Scholar (25 papers) → arXiv (15) → CrossRef (12) → OpenAlex (12) → PubMed (15)
        
        Args:
            topic: Research topic/query
            max_papers: Maximum papers to return after deduplication
            sources: List of sources to use. If None and auto_select=False, uses default sources.
            auto_select: If True and sources=None, intelligently selects APIs based on topic
        
        Returns:
            List of deduplicated paper dictionaries with 'source', 'title', 'abstract', 'year', etc.
        """
        if sources is None:
            if auto_select:
                sources = self._detect_subject_apis(topic)
            else:
                sources = ['semantic_scholar', 'arxiv', 'crossref', 'openalex']
        
        print(f"\n  📚 Fetching papers from {len(sources)} source(s): {', '.join(sources)}")
        print(f"  {'─' * 70}")
        
        all_papers = []
        
        # Fetch from each source SEQUENTIALLY with sleep between calls
        for idx, source in enumerate(sources, 1):
            try:
                print(f"\n  [{idx}/{len(sources)}] Querying {source.upper()}...", end=" ")
                
                # Semantic Scholar gets priority with higher limit
                if source == 'semantic_scholar':
                    papers = self._fetch_semantic_scholar(topic, limit=25)
                elif source == 'arxiv':
                    papers = self._fetch_arxiv(topic, limit=15)
                elif source == 'pubmed':
                    papers = self._fetch_pubmed(topic, limit=15)
                elif source == 'crossref':
                    papers = self._fetch_crossref(topic, limit=12)
                elif source == 'openalex':
                    papers = self._fetch_openalex(topic, limit=12)
                elif source == 'core':
                    papers = self._fetch_core(topic, limit=10)
                else:
                    print(f"❌ Unknown source")
                    continue
                
                all_papers.extend(papers)
                print(f"✓ Retrieved {len(papers)} papers")
                
                # Rate limiting between API calls
                if idx < len(sources):
                    time.sleep(1.0)
                
            except Exception as e:
                print(f"❌ Failed: {str(e)[:60]}")
                continue
        
        # ── Fallback: web scraping if all APIs failed ─────────────────────
        if len(all_papers) == 0:
            print(f"\n  ⚠️  All APIs returned 0 papers. Trying web scraping fallback...")
            fallback = self._web_scrape_fallback(topic, limit=max_papers)
            all_papers.extend(fallback)

        print(f"\n  {'─' * 70}")
        print(f"  📊 Total papers fetched: {len(all_papers)}")
        
        # Deduplicate
        unique_papers = self._deduplicate(all_papers)
        duplicates_removed = len(all_papers) - len(unique_papers)
        print(f"  🔍 Unique papers after deduplication: {len(unique_papers)} (removed {duplicates_removed} duplicates)")
        
        # Sort by year (newest first) and citation count
        unique_papers.sort(key=lambda p: (p.get('year', 0), p.get('citationCount', 0)), reverse=True)
        
        # Limit to max_papers
        final_papers = unique_papers[:max_papers]
        
        # Source distribution of final papers
        source_counts = {}
        for p in final_papers:
            src = p.get('source', 'Unknown')
            source_counts[src] = source_counts.get(src, 0) + 1
        
        print(f"\n  📈 Final selection ({len(final_papers)} papers):")
        for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"     • {source}: {count} papers")
        
        if len(unique_papers) < max_papers:
            print(f"\n  ⚠️  Only {len(unique_papers)} unique papers available (requested {max_papers})")
        
        print(f"  {'─' * 70}\n")
        
        return final_papers
    
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
    
    def _fetch_arxiv(self, topic: str, limit: int = 15) -> List[Dict]:
        """Fetch from arXiv API"""
        base_url = "http://export.arxiv.org/api/query"
        
        # Extract meaningful keywords for arXiv's exact AND matching
        query_terms = [w for w in topic.split() if w.lower() not in ('in', 'on', 'the', 'of', 'and', 'a', 'to', 'for', 'with', 'by')]
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
        items = r.json().get("message", {}).get("items", [])
        
        normalized = []
        for item in items:
            abstract = item.get("abstract", "")
            if not abstract or len(abstract.strip()) < 50:
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
    
    def _deduplicate(self, papers: List[Dict]) -> List[Dict]:
        """Remove duplicates by DOI first, then by normalized title"""
        seen_dois = set()
        seen_titles = set()
        unique_papers = []
        
        for paper in papers:
            # DOI-based deduplication (most reliable)
            doi = paper.get("doi", "").strip()
            if doi:
                if doi in seen_dois:
                    continue
                seen_dois.add(doi)
                unique_papers.append(paper)
                continue
            
            # Title-based deduplication for papers without DOI
            title = paper.get("title", "").strip()
            if not title:
                continue
            
            # Normalize title: lowercase, remove punctuation, collapse whitespace
            normalized_title = re.sub(r'[^\w\s]', '', title.lower())
            normalized_title = re.sub(r'\s+', ' ', normalized_title).strip()
            
            if normalized_title in seen_titles:
                continue
            
            seen_titles.add(normalized_title)
            unique_papers.append(paper)
        
        return unique_papers
