# VMARO — Implementation Planning

> Derived from `README.md` and `docs/VMARO_spec.md`.  
> Deadline: **March 10, 2026**

---

## Task Dependencies

- **Utilities** must be implemented before any agent code.
- **Agent order dependencies:**  
  Literature Agent → Tree Builder → Trend Agent → Gap Agent → Methodology Agent → Grant Agent → Novelty Agent
- The **Streamlit UI** depends on the orchestrator (`main.py`) being functional.
- **Testing** depends on all agents and utilities being implemented.

---

## Definition of Done

A phase is complete when:

- Code runs without errors
- Output matches the specified JSON schema (see `VMARO_spec.md` §4)
- Results are saved to `cache/`
- No uncaught exceptions occur

---

## Agent Interface Standard

Every agent module must expose a single entry-point function named `run`.
Agents may accept **stage-specific parameters** (e.g. `topic: str`, `tree: dict, trends: dict`), but must **always return a schema-compliant `dict`**.

```python
# Examples — signatures vary per agent, return type is always dict
def run(topic: str) -> dict:              # literature_agent
def run(papers: dict) -> dict:            # tree_agent
def run(tree: dict, trends: dict) -> dict: # gap_agent
```

- The returned `dict` must conform exactly to the schema defined in `VMARO_spec.md`.
- Agents must **never** return raw text — always parsed, validated JSON.
- On failure, agents return a fallback dict matching the schema with sensible defaults.

---

## Logging

Each agent should print a stage header when executed for easy debugging:

```
[Agent1]       Literature Mining
[TreeBuilder]  Building thematic tree
[QualityGate]  Post-literature check
[Agent2]       Trend Analysis
[Agent3]       Gap Identification
[QualityGate]  Post-gap check
[Agent4]       Methodology Design
[Agent5]       Grant Writing
[Agent6]       Novelty Scoring
```

---

## Phase 1 — Repo Scaffolding

**Goal:** Empty project structure, config files, and mock data so all team members can start in parallel.

### 1.1 Directory & file skeleton

```
vmaro/
├── agents/
│   ├── __init__.py
│   ├── literature_agent.py
│   ├── tree_agent.py
│   ├── trend_agent.py
│   ├── gap_agent.py
│   ├── methodology_agent.py
│   ├── grant_agent.py
│   └── novelty_agent.py
├── utils/
│   ├── __init__.py
│   ├── schema.py
│   ├── cache.py
│   └── quality_gate.py
├── mock_data/
│   ├── mock_papers.json
│   ├── mock_tree.json
│   ├── mock_gaps.json
│   ├── mock_methodology.json
│   ├── mock_grant.json
│   └── mock_novelty.json
├── cache/                  # gitignored, auto-created at runtime
├── main.py
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

**Tasks:**

- [ ] Create all directories (`agents/`, `utils/`, `mock_data/`, `cache/`)
- [ ] Create `__init__.py` files for `agents/` and `utils/`
- [ ] Create stub files for every agent and utility module
- [ ] Create `.gitignore` (include `cache/`, `.env`, `__pycache__/`, `*.pyc`)

### 1.2 Config files

- [ ] `requirements.txt` — pin `crewai==0.30.11`, add `google-generativeai`, `requests`, `streamlit`, `python-dotenv`
- [ ] `.env.example` — placeholder keys `GEMINI_KEY_1`, `GEMINI_KEY_2`, `GEMINI_KEY_3`

### 1.3 Mock data fixtures

Populate each mock JSON with realistic sample data matching the spec schemas:

- [ ] `mock_papers.json` — Schema 1 (topic + array of paper objects)
- [ ] `mock_tree.json` — Schema 2 (root + themes with paper refs + emerging directions)
- [ ] `mock_gaps.json` — Schema 3 (dominant clusters, emerging trends, identified gaps, selected gap)
- [ ] `mock_methodology.json` — Schema 4 (datasets, metrics, baselines, experimental design, tools)
- [ ] `mock_grant.json` — Schema 5 (problem statement, methodology, eval plan, contribution, timeline, budget)
- [ ] `mock_novelty.json` — Schema 6 (closest themes, closest papers, similarity reasoning, novelty score, justification)

> **Unblocking:** Mock data lets Person B (trend/gap agents) and Person C (grant/novelty/UI) start immediately without live API calls.

---

## Phase 2 — Utilities

**Goal:** Shared helpers that every agent depends on. Build and test these before any agent code.

### 2.1 `utils/schema.py` — Key rotation + JSON cleaning

- [ ] Load `GEMINI_KEY_1..3` from `.env` using `python-dotenv`
- [ ] Create a round-robin `itertools.cycle` key pool
- [ ] `get_api_key() → str` — returns next key from pool
- [ ] `clean_json_response(text) → str` — strips markdown fences (```` ```json ... ``` ````) that Gemini Flash sometimes wraps around output
- [ ] `safe_parse(text) → dict` — calls `clean_json_response()` then `json.loads()`

### 2.2 `utils/cache.py` — Checkpoint persistence

- [ ] Auto-create `cache/` directory on import
- [ ] `save(stage: str, data: dict)` — writes `cache/{stage}.json`
- [ ] `load(stage: str) → dict | None` — reads from cache if file exists, else `None`

### 2.3 `utils/quality_gate.py` — Reusable LLM gate

- [ ] `GATE_PROMPT` template requesting `PASS` / `REVISE` / `FAIL` + confidence (0–1) + reason
- [ ] `evaluate_quality(stage_name, output_json) → dict`
  - Configure Gemini Flash with rotated key
  - Send prompt, parse response with `safe_parse()`
  - On error: return `{"decision": "PASS", "confidence": 0.5, "reason": "Gate error — defaulting to PASS"}`
  - **Demo mode**: only `print()` the gate result, never block the pipeline

---

## Phase 3 — Agent Implementations

Each agent exposes a `run(...)` function returning a schema-conformant `dict`.

### 3.1 Agent 1 — Literature Mining (`agents/literature_agent.py`)

**Two-pass design:**

- [ ] **Pass 1 — Retrieval:** Call Semantic Scholar API
  - `GET /graph/v1/paper/search?query={topic}&limit=20&fields=title,abstract,year,authors,externalIds,citationCount&sort=citationCount:desc`
  - Filter: drop papers with `None`/empty abstract, drop `year < 2018` (relax to 2015 if < 8 survive), keep top 10–12
- [ ] **Pass 2 — Summarisation:** Gemini Flash prompt
  - Input: filtered paper abstracts
  - Output: Schema 1 JSON (topic, papers with title/year/summary/contribution/source)
- [ ] **Fallback:** On malformed JSON → `clean_json_response()` → retry once with correction prompt
- [ ] Wrap all API calls in `try/except`, return sensible fallback on failure

### 3.2 Tree Index Builder (`agents/tree_agent.py`)

- [ ] Prompt Gemini Flash to cluster papers into 3–5 thematic groups
- [ ] Output: Schema 2 JSON (root, themes with `theme_id`/`theme_name`/papers, emerging_directions)
- [ ] Error handling: `try/except` + fallback

### 3.3 Agent 2 — Trend Analysis (`agents/trend_agent.py`)

- [ ] Input: tree JSON (Schema 2)
- [ ] Prompt Gemini Flash to identify dominant clusters and emerging trends
- [ ] Output: `{ "dominant_clusters": [...], "emerging_trends": [...] }`
- [ ] Error handling

### 3.4 Agent 3 — Gap Identification (`agents/gap_agent.py`)

- [ ] Input: tree JSON + trends JSON
- [ ] Prompt Gemini Flash to find underexplored intersections
- [ ] Output: Schema 3 JSON (identified_gaps + selected_gap)
- [ ] Error handling

### 3.5 Agent 4 — Methodology Design (`agents/methodology_agent.py`)

- [ ] Input: selected gap description + topic
- [ ] Prompt Gemini Flash for experimental methodology
- [ ] Output: Schema 4 JSON (datasets, metrics, baselines, experimental design, tools)
- [ ] Error handling

### 3.6 Agent 5 — Grant Writing (`agents/grant_agent.py`)

- [ ] Input: topic + gap description + methodology JSON
- [ ] Prompt Gemini Flash to write a funding-ready proposal
- [ ] Output: Schema 5 JSON (problem_statement, proposed_methodology, eval_plan, contribution, timeline, budget)
- [ ] Error handling

### 3.7 Agent 6 — Novelty Scoring (`agents/novelty_agent.py`)

**Two-step internal chain:**

- [ ] **Step 1 — Theme selection:** Gemini Flash identifies which themes are most relevant to the grant proposal (fast, uses theme names only)
- [ ] **Step 2 — Paper-level scoring:** Gemini Flash compares the proposal against papers from selected themes (3–5 papers max), scores novelty 0–100
- [ ] Output: Schema 6 JSON (closest_papers, similarity_reasoning, novelty_score, score_justification)
- [ ] Error handling

---

## Phase 4 — Orchestrator (`main.py`)

**Goal:** Wire all agents into a sequential CrewAI pipeline with caching and quality gates.

- [ ] Import all agent `run()` functions + `cache.save`/`cache.load` + `evaluate_quality`
- [ ] Implement `run_pipeline(topic: str) → dict`:
  1. Agent 1: `papers = load("papers") or run_literature(topic)` → `save("papers", papers)`
  2. Tree Builder: `tree = load("tree") or run_tree(papers)` → `save("tree", tree)`
  3. **Quality Gate 1** — `evaluate_quality("post_literature", tree)`
  4. Agent 2: `trends = load("trends") or run_trend(tree)` → `save("trends", trends)`
  5. Agent 3: `gaps = load("gaps") or run_gap(tree, trends)` → `save("gaps", gaps)`
  6. **Quality Gate 2** — `evaluate_quality("post_gap", gaps)`
  7. Agent 4: `methodology = load("methodology") or run_methodology(gaps)` → save
  8. Agent 5: `grant = load("grant") or run_grant(topic, gaps, methodology)` → save
  9. Agent 6: `novelty = load("novelty") or run_novelty(grant, tree)` → save
  10. Return full results dict
- [ ] Add CLI entry point: `argparse` with `--topic` argument
- [ ] Ensure cache-resume: re-running after a mid-pipeline failure skips completed stages

---

## Phase 5 — Streamlit UI (`app.py`)

**Goal:** Interactive dashboard that runs the pipeline and renders all results.

- [ ] **Input section:** `st.text_input("Research Topic")` + `st.button("▶ Run Analysis")` with `st.spinner`
- [ ] **Section 1 — Papers:** `st.header("📚 Retrieved Literature")` — card per paper (title, year, summary, source link)
- [ ] **Section 2 — Tree:** `st.header("📊 Thematic Tree Index")` — expandable themes with paper lists
- [ ] **Section 3 — Trends & Gaps:** Two-column layout — trends in col1, gap cards in col2
- [ ] **Section 4 — Methodology:** Datasets, metrics, baselines, experimental design, tools/frameworks
- [ ] **Section 5 — Grant Proposal:** Rendered markdown sections for each proposal field
- [ ] **Section 6 — Novelty Score:** `st.metric` with color-coded emoji (🔴 < 40, 🟡 < 70, 🟢 ≥ 70) + justification
- [ ] **Download button:** `st.download_button` to export grant proposal as JSON

---

## Phase 6 — Testing & Verification

### 6.1 Unit tests (utilities)

- [ ] Test `clean_json_response()` with plain JSON, ` ```json` fenced, ` ``` ` fenced, and whitespace-padded inputs
- [ ] Test `safe_parse()` returns correct dict
- [ ] Test `get_api_key()` cycles through keys
- [ ] Test `cache.save()` / `cache.load()` round-trip
- [ ] Test `cache.load()` returns `None` for missing stage

### 6.2 Integration tests (mock pipeline)

- [ ] Run `run_pipeline()` using mock data (no real API calls) — verify all schemas pass through correctly
- [ ] Confirm cache files are written after each stage
- [ ] Confirm cache-resume works by deleting mid-pipeline cache files and re-running

### 6.3 Live end-to-end tests

- [ ] Run full pipeline with **3 different topics** before demo:
  1. `"Federated Learning in Healthcare"`
  2. `"Transformer Architectures for Climate Modeling"`
  3. `"LLM-Based Automated Code Review"`
- [ ] Verify each run produces valid JSON at every stage
- [ ] Verify Streamlit UI renders all sections without errors

### 6.4 Stability checks

- [ ] Confirm paper limit stays within 8–15 range
- [ ] Confirm `year < 2018` filter works (and relaxes to 2015 when needed)
- [ ] Trigger deliberate API failure — verify `try/except` fallback, no crash
- [ ] Test Gemini response with markdown fences — verify `clean_json_response()` handles it

### 6.5 Pre-demo

- [ ] Record demo video as backup (Day 4)
- [ ] Verify all team members can explain the 7 viva talking points

---

## Ownership Summary

| Phase | Owner | Day |
|-------|-------|-----|
| 1 — Scaffolding + mock data | Person A | 1 |
| 2 — Utilities | Person A | 1 |
| 3.1 — Literature Agent | Person A | 2 |
| 3.2 — Tree Builder | Person A | 3 |
| 3.3 — Trend Agent | Person B | 2 |
| 3.4 — Gap Agent | Person B | 2 |
| 3.5 — Methodology Agent | Person B | 3 |
| 3.6 — Grant Agent | Person C | 2 |
| 3.7 — Novelty Agent | Person C | 3 |
| 4 — Orchestrator | Person A | 4 |
| 5 — Streamlit UI | Person C | 1 (skeleton) → 4 (live) |
| 6 — Testing | All | 4 |

---

## Stability Rules (Non-Negotiable)

| Rule | Detail |
|------|--------|
| Paper limit | 8–15 papers max per run |
| API failures | `try/except` on every call — return fallback, never crash |
| Year filter | Drop < 2018; relax to 2015 if < 8 papers survive |
| JSON failures | `clean_json_response()` first, then retry once |
| API retry | Retry once with exponential backoff before falling back |
| CrewAI version | `crewai==0.30.11` pinned |
| Quality gates | Demo mode: `print()` only, never block |
| Pre-demo | 3 topics tested before demo day |
| Backup | Demo video recorded on Day 4 |

---

## Demo Mode

Controlled by `DEMO_MODE=true` in `.env`.

When enabled:

- Quality gates **log** their decision but **do not block** the pipeline
- Fallback outputs are accepted without raising errors
- Errors are caught and printed — the pipeline **never halts**

This keeps the system presentation-safe while still surfacing diagnostics in the terminal.
