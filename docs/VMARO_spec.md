# VMARO — Vectorless Multi-Agent Research Orchestrator
## Build Spec

## Implementation Goals

1. Implement 6 agents using CrewAI
2. Enforce JSON schemas using Pydantic
3. Build a Streamlit dashboard
4. Add caching and retry logic
5. Support optional hybrid retrieval
---

## 1. What We're Building

A 6-agent sequential pipeline that takes a research topic and outputs a funded-ready grant proposal + novelty score — no vector DB, no embeddings, pure LLM-native tree navigation.

```
[User Topic]
    → Agent 1: Literature Mining    (Semantic Scholar + Gemini Flash)
    → Tree Builder                  (Gemini Flash) [architectural layer, above spec]
    → [Quality Gate 1]
    → Agent 2: Trend Analysis       (Gemini Flash)
    → Agent 3: Gap Identification   (Gemini Flash)
    → [Quality Gate 2]
    → Agent 4: Methodology Design   (Gemini Flash)
    → Agent 5: Grant Writing        (Gemini Flash)
    → Agent 6: Novelty Scoring      (Gemini Flash, 2-step)
    → [Streamlit Dashboard]
```

---

## 2. Repo Structure (scaffold this first)

```
vmaro/
├── agents/
│   ├── literature_agent.py     # Agent 1
│   ├── tree_agent.py           # Tree Builder
│   ├── trend_agent.py          # Agent 2
│   ├── gap_agent.py            # Agent 3
│   ├── methodology_agent.py    # Agent 4
│   ├── grant_agent.py          # Agent 5
│   └── novelty_agent.py        # Agent 6
├── utils/
│   ├── schema.py               # JSON validators + clean_json_response() + API key rotation
│   ├── cache.py                # Checkpoint cache (writes to cache/ after each agent)
│   └── quality_gate.py         # LLM quality gate (PASS / REVISE / FAIL)
├── mock_data/
│   ├── mock_papers.json        # Schema 1
│   ├── mock_tree.json          # Schema 2
│   ├── mock_gaps.json          # Schema 3
│   ├── mock_methodology.json   # Schema 4
│   ├── mock_grant.json         # Schema 5
│   └── mock_novelty.json       # Schema 6
├── cache/                      # Auto-created at runtime
├── main.py                     # CrewAI orchestrator
├── app.py                      # Streamlit UI
├── requirements.txt
├── .env
├── .env.example
└── README.md
```

---

## 3. Environment Setup

### `.env.example`
```
GEMINI_KEY_1=your_key_here
GEMINI_KEY_2=your_key_here
GEMINI_KEY_3=your_key_here
```

### `requirements.txt`
```
crewai==0.30.11         # PIN THIS — breaking changes between minor versions
google-generativeai
requests
streamlit
python-dotenv
```

### Free Tier Limits (Gemini Flash per key)
| Limit | Value |
|-------|-------|
| Requests/day | 1,500 |
| Requests/minute | 15 |
| Context window | 1M tokens |

With 3 keys: **4,500 req/day, 45 RPM** — more than enough for ~10 LLM calls per run.

---

## 4. Shared JSON Schemas

All inter-agent communication is plain JSON passed in memory (or cached to `cache/`).

### Schema 1 — Papers (Agent 1 output)
```json
{
  "topic": "Federated Learning in Healthcare",
  "papers": [
    {
      "title": "...",
      "year": 2024,
      "summary": "2-3 sentence summary",
      "contribution": "main contribution",
      "source": "https://doi.org/..."
    }
  ]
}
```

### Schema 2 — Tree (Tree Builder output → Agent 2 input)
```json
{
  "root": "Federated Learning in Healthcare",
  "themes": [
    {
      "theme_id": "T1",
      "theme_name": "Privacy-Preserving Methods",
      "papers": [ "...paper objects..." ]
    }
  ],
  "emerging_directions": ["...", "..."]
}
```

### Schema 3 — Trends & Gaps (Agents 2+3 output → Agent 4 input)
```json
{
  "dominant_clusters": ["...", "..."],
  "emerging_trends": ["...", "..."],
  "identified_gaps": [
    {
      "gap_id": "G1",
      "description": "...",
      "why_underexplored": "..."
    }
  ],
  "selected_gap": "G1"
}
```

### Schema 4 — Methodology (Agent 4 output → Agent 5 input)
```json
{
  "suggested_datasets": ["...", "..."],
  "evaluation_metrics": ["...", "..."],
  "baseline_models": ["...", "..."],
  "experimental_design": "step-by-step approach",
  "tools_and_frameworks": ["...", "..."]
}
```

### Schema 5 — Grant Proposal (Agent 5 output → UI)
```json
{
  "problem_statement": "...",
  "proposed_methodology": "...",
  "evaluation_plan": "...",
  "expected_contribution": "...",
  "timeline": "6-month phased plan",
  "budget_estimate": "..."
}
```

### Schema 6 — Novelty Score (Agent 6 output → UI)
```json
{
  "closest_theme_ids": ["T1", "T2"],
  "closest_papers": ["Paper Title A", "Paper Title B"],
  "similarity_reasoning": "...",
  "novelty_score": 78,
  "score_justification": "..."
}
```

### Quality Gate Schema (utils/quality_gate.py output)
```json
{
  "decision": "PASS",
  "confidence": 0.91,
  "reason": "Output meets schema and contains sufficient reasoning depth."
}
```

---

## 5. Utility Files (Build These First)

### `utils/schema.py` — Key rotation + JSON cleaning
```python
import itertools, os, json, re
from dotenv import load_dotenv
load_dotenv()

_keys = [k for k in [os.getenv(f"GEMINI_KEY_{i}") for i in range(1, 4)] if k]
_key_pool = itertools.cycle(_keys)

def get_api_key():
    return next(_key_pool)

def clean_json_response(text: str) -> str:
    """Strip markdown fences Gemini Flash occasionally wraps around JSON."""
    text = text.strip()
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'^```\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()

def safe_parse(text: str) -> dict:
    cleaned = clean_json_response(text)
    return json.loads(cleaned)
```

### `utils/cache.py` — Checkpoint persistence
```python
import json, os

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def save(stage: str, data: dict):
    with open(f"{CACHE_DIR}/{stage}.json", "w") as f:
        json.dump(data, f, indent=2)

def load(stage: str) -> dict | None:
    path = f"{CACHE_DIR}/{stage}.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None
```

### `utils/quality_gate.py` — LLM gate (reusable)
```python
import google.generativeai as genai
from utils.schema import get_api_key, safe_parse
import json

GATE_PROMPT = """
You are a quality control agent. Evaluate this JSON output from a research pipeline agent.
Stage: {stage}
Output: {output}

Return ONLY valid JSON:
{{
  "decision": "PASS" | "REVISE" | "FAIL",
  "confidence": 0.0-1.0,
  "reason": "brief explanation"
}}
"""

def evaluate_quality(stage_name: str, output_json: dict) -> dict:
    genai.configure(api_key=get_api_key())
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = GATE_PROMPT.format(stage=stage_name, output=json.dumps(output_json, indent=2))
    try:
        response = model.generate_content(prompt)
        result = safe_parse(response.text)
        # Demo mode: just log, never block
        print(f"[QualityGate:{stage_name}] {result['decision']} (confidence={result['confidence']}): {result['reason']}")
        return result
    except Exception as e:
        print(f"[QualityGate:{stage_name}] Gate failed silently: {e}")
        return {"decision": "PASS", "confidence": 0.5, "reason": "Gate error — defaulting to PASS"}
```

---

## 6. Agent Implementations

### Agent 1 — `agents/literature_agent.py`

**Two-pass design:**
1. Semantic Scholar API → raw papers (free, no key needed)
2. Gemini Flash → summarise + extract contribution

```python
# Pass 1 — retrieval
GET https://api.semanticscholar.org/graph/v1/paper/search
  ?query={topic}
  &limit=20
  &fields=title,abstract,year,authors,externalIds,citationCount
  &sort=citationCount:desc

# Filter:
# - Drop if abstract is None or ""
# - Drop if year < 2018 (relax to 2015 if fewer than 8 survive)
# - Take top 10-12 after filtering
```

**Pass 2 Prompt:**
```
You are a research assistant. Below are abstracts on "{topic}" from Semantic Scholar.
For each paper, write a 2–3 sentence plain-English summary and identify the single most
important contribution.

Papers: {semantic_scholar_results_json}

Return ONLY valid JSON:
{
  "topic": "{topic}",
  "papers": [
    {
      "title": "exact title from input",
      "year": <year>,
      "summary": "2-3 sentence summary",
      "contribution": "single most novel contribution",
      "source": "DOI or URL"
    }
  ]
}
No extra text. No markdown. JSON only.
```

**Fallback:** If malformed JSON → run `clean_json_response()` → retry once with correction prompt.

---

### Tree Builder — `agents/tree_agent.py`

**Prompt:**
```
You are a research taxonomist. Given these papers on "{topic}", cluster them into
3–5 high-level themes. Identify emerging directions not covered by existing papers.

Papers: {papers_json}

Return ONLY valid JSON:
{
  "root": "{topic}",
  "themes": [
    { "theme_id": "T1", "theme_name": "...", "papers": [...paper objects...] }
  ],
  "emerging_directions": ["...", "..."]
}
No extra text. JSON only.
```

---

### Agent 2 — `agents/trend_agent.py`

**Prompt:**
```
You are a research trend analyst. Analyze this hierarchical research tree and identify
dominant research clusters and emerging directions.

Tree: {tree_json}

Return ONLY valid JSON:
{
  "dominant_clusters": ["cluster 1", "cluster 2"],
  "emerging_trends": ["trend 1", "trend 2"]
}
No extra text. JSON only.
```

---

### Agent 3 — `agents/gap_agent.py`

**Prompt:**
```
You are a research gap analyst. Given this research tree and identified trends, find
underexplored intersections that represent meaningful research gaps.

Tree: {tree_json}
Identified Trends: {trends_json}

Return ONLY valid JSON:
{
  "identified_gaps": [
    { "gap_id": "G1", "description": "...", "why_underexplored": "..." }
  ],
  "selected_gap": "G1"
}
No extra text. JSON only.
```

---

### Agent 4 — `agents/methodology_agent.py`

**Prompt:**
```
You are a research methodology expert. Given this research gap, recommend a concrete
experimental methodology.

Research Gap: {gap_description}
Research Topic: {topic}

Return ONLY valid JSON:
{
  "suggested_datasets": ["dataset1", "dataset2"],
  "evaluation_metrics": ["metric1", "metric2"],
  "baseline_models": ["baseline1", "baseline2"],
  "experimental_design": "step-by-step methodology",
  "tools_and_frameworks": ["tool1", "tool2"]
}
No extra text. JSON only.
```

---

### Agent 5 — `agents/grant_agent.py`

**Prompt:**
```
You are a grant proposal writer. Using the identified research gap and proposed
methodology, generate a complete funding-ready grant proposal.

Research Topic: {topic}
Research Gap: {gap_description}
Methodology: {methodology_json}

Return ONLY valid JSON:
{
  "problem_statement": "2-3 paragraph problem description",
  "proposed_methodology": "detailed approach referencing the methodology",
  "evaluation_plan": "how results will be measured",
  "expected_contribution": "impact and novelty",
  "timeline": "phased 6-month plan",
  "budget_estimate": "cost breakdown with justification"
}
No extra text. JSON only.
```

---

### Agent 6 — `agents/novelty_agent.py` (two internal steps)

**Step 1 — Tree Navigation (fast, theme names only):**
```
You are a research evaluator. Given this proposal and a list of research themes,
identify which themes are most related.

Proposal Summary: {problem_statement}
Available Themes: {theme_names_and_ids}

Return ONLY valid JSON:
{
  "selected_theme_ids": ["T1", "T3"],
  "reasoning": "why these themes are most relevant"
}
No extra text. JSON only.
```

**Step 2 — Paper-level scoring (narrow context, 3–5 papers max):**
```
You are an expert peer reviewer assessing research novelty.

Proposal: {grant_json}
Related Papers (selected themes only): {filtered_papers}

Evaluate:
1. Which papers does this most closely resemble?
2. What makes this proposal meaningfully different?
3. Rate novelty 0 (fully replicated) to 100 (completely novel)

Return ONLY valid JSON:
{
  "closest_papers": ["Paper Title A", "Paper Title B"],
  "similarity_reasoning": "specific similarities found",
  "novelty_score": 78,
  "score_justification": "why this score was given"
}
No extra text. JSON only.
```

---

## 7. `main.py` — CrewAI Orchestrator (skeleton)

```python
from crewai import Agent, Task, Crew, Process
from agents.literature_agent import run as run_literature
from agents.tree_agent import run as run_tree
from agents.trend_agent import run as run_trend
from agents.gap_agent import run as run_gap
from agents.methodology_agent import run as run_methodology
from agents.grant_agent import run as run_grant
from agents.novelty_agent import run as run_novelty
from utils.cache import save, load
from utils.quality_gate import evaluate_quality

def run_pipeline(topic: str) -> dict:
    # Agent 1
    papers = load("papers") or run_literature(topic)
    save("papers", papers)

    # Tree Builder
    tree = load("tree") or run_tree(papers)
    save("tree", tree)

    # Quality Gate 1
    evaluate_quality("post_literature", tree)

    # Agent 2 + 3
    trends = load("trends") or run_trend(tree)
    save("trends", trends)
    gaps = load("gaps") or run_gap(tree, trends)
    save("gaps", gaps)

    # Quality Gate 2
    evaluate_quality("post_gap", gaps)

    # Agent 4
    methodology = load("methodology") or run_methodology(gaps)
    save("methodology", methodology)

    # Agent 5
    grant = load("grant") or run_grant(topic, gaps, methodology)
    save("grant", grant)

    # Agent 6
    novelty = load("novelty") or run_novelty(grant, tree)
    save("novelty", novelty)

    return {
        "papers": papers, "tree": tree, "gaps": gaps,
        "methodology": methodology, "grant": grant, "novelty": novelty
    }
```

> **Speedrun tip:** The cache means you only re-run changed agents during development. Comment out `load()` calls for the agent you're actively editing.

---

## 8. `app.py` — Streamlit UI Layout

```python
st.title("🔬 VMARO — Research Orchestrator")
topic = st.text_input("Research Topic")
if st.button("▶ Run Analysis"):
    with st.spinner("Agents working..."):
        results = run_pipeline(topic)

# Section 1 — Papers
st.header("📚 Retrieved Literature")
# st.card per paper: title, year, summary, source link

# Section 2 — Tree
st.header("📊 Thematic Tree Index")
for theme in results["tree"]["themes"]:
    with st.expander(theme["theme_name"]):
        for p in theme["papers"]: st.write(p["title"])

# Section 3 — Trends & Gaps
st.header("🔍 Research Trends & Gaps")
col1, col2 = st.columns(2)
# trends in col1, gap cards in col2

# Section 4 — Methodology
st.header("🧪 Recommended Methodology")
# Datasets | Metrics | Baselines | Experimental Design

# Section 5 — Grant Proposal
st.header("💰 Grant Proposal")
# Rendered markdown sections

# Section 6 — Novelty Score
st.header("📏 Novelty Score")
score = results["novelty"]["novelty_score"]
color = "🔴" if score < 40 else "🟡" if score < 70 else "🟢"
st.metric(f"{color} Novelty Score", f"{score}/100")
st.write(results["novelty"]["score_justification"])

st.download_button("⬇ Download Grant Proposal", data=..., file_name="grant.json")
```

---

## 9. Mock Data (Unblock teammates immediately)

Commit these on Day 1 so Person B and C can start without waiting for real API calls.

| File | Unblocks |
|------|----------|
| `mock_papers.json` | Person B (trend agent input) |
| `mock_tree.json` | Person B (trend/gap agents) |
| `mock_gaps.json` | Person C (grant agent input) |
| `mock_methodology.json` | Person C (grant agent input) |
| `mock_grant.json` | Person C (novelty agent input + UI render) |
| `mock_novelty.json` | Person C (UI render) |

---

## 10. Stability Rules (Non-Negotiable)

| Rule | Implementation |
|------|---------------|
| Paper limit | 8–15 papers max — prevents token overflow |
| API failures | `try/except` on every call — return fallback, never crash |
| Year filter | Drop < 2018; relax to 2015 if < 8 papers survive |
| JSON failures | `clean_json_response()` first, then retry once with correction prompt |
| CrewAI version | `crewai==0.30.11` pinned in requirements.txt |
| Quality gate (demo) | Only `print()` the decision — never block during live demo |
| Pre-demo testing | 3 different topics before demo day |
| Backup | Record demo video on Day 4 |

---

## 11. 4-Day Execution Plan

| Day | Person A | Person B | Person C |
|-----|----------|----------|----------|
| **1** | Repo + mock JSONs + utils/ | Pull mocks, `.env` setup | Full Streamlit skeleton (static mocks) |
| **2** | `literature_agent.py` | `trend_agent.py` + `gap_agent.py` | `grant_agent.py` + render in UI |
| **3** | `tree_agent.py` + A→B pipeline test | `methodology_agent.py` | `novelty_agent.py` (both steps) |
| **4** | Full `main.py` integration | Swap all mocks for real outputs | Connect UI to live pipeline + demo test |

---

## 12. Viva Cheat Sheet (All 3 Must Know)

1. **6 agents:** Literature → Trend → Gap → Methodology → Grant → Novelty
2. **Why vectorless?** Tree Builder replaces cosine similarity with LLM-native hierarchical navigation — interpretable, zero infra
3. **Why Flash + Semantic Scholar?** Two-pass design separates retrieval from intelligence. Semantic Scholar = real papers, no hallucination. Flash = free, 1M context, sufficient for 10–15 paper corpus
4. **Two-step novelty:** Step 1 prunes themes (fast), Step 2 compares papers in selected themes only (focused). Coarse-to-fine — how humans review
5. **Quality gates:** After Agent 1 and Agent 3. Returns PASS/REVISE/FAIL + confidence. Prevents silent error propagation
6. **Above spec:** Tree Index Builder + 2 quality gates are extras, not replacements for the 6 required agents
7. **Limitations:** Scoped to 10–15 papers. At scale: hybrid vector pruning before Tree Builder (but that contradicts "vectorless" — so it's explicitly Future Work)

---

*VMARO Speedrun Spec | Deadline March 10, 2026*
