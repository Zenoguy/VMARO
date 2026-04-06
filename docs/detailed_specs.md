# VMARO — Detailed System Specifications

## Vectorless Multi-Agent Research Orchestrator

VMARO is an advanced, 8-stage academic research pipeline that bypasses traditional vector database limitations by using LLM-native structural synthesis. This document serves as the ground truth for the system's architecture, agent logic, and inter-agent communication.

---

## 1. System Goals & Design Philosophy

1. **Vectorless Navigation**: Replaces black-box semantic retrieval with direct semantic clustering, constructing a visual Thematic Tree from high-signal abstracts.
2. **Interpretable Synthesis**: Every stage generates human-readable JSON, allowing researchers to inspect the "why" behind every conclusion.
3. **Parallel Evaluation**: Implements a "Challenger" model to pit multiple methodologies against each other.
4. **Institutional Alignment**: Automatically adapts proposals to rigorous schemas (NIH, NSF, ERC).
5. **Stateful Resiliency**: Native checkpoint caching allows the pipeline to resume from the last successful stage.

---

## 2. Repository Structure

```text
vmaro/
├── agents/
│   ├── literature_agent.py      # Stage 01: Multi-API Fetch & Summarization
│   ├── tree_agent.py            # Stage 02: Hierarchical Thematic Clustering
│   ├── trend_agent.py           # Stage 03: Macro-Signal Identification
│   ├── gap_agent.py             # Stage 04: Target Research Discovery
│   ├── methodology_agent.py     # Stage 05a: Primary/Challenger methodology draft
│   ├── methodology_evaluator.py # Stage 05b: Win-loss evaluator between methods
│   ├── format_matcher.py        # Stage 06: Matching methods to grant schemas
│   ├── grant_agent.py           # Stage 07: Format-compliant proposal writing
│   └── novelty_agent.py         # Stage 08: Two-step novelty verification
├── utils/
│   ├── topic_normalizer.py      # Stage 00: Freeform input structuring
│   ├── multi_api_fetcher.py     # Scholar, PubMed, Arxiv multiplexer
│   ├── schema.py                # LLM cleanup, Key rotation, Pydantic-like safe_parse
│   ├── quality_gate.py          # LLM-as-a-Judge quality evaluator
│   ├── format_loader.py         # Loads JSON grant schemas from grant_formats/
│   └── latex_exporter.py        # PDF/LaTeX generation
├── grant_formats/               # NIH, NSF, ERC JSON schema definitions
├── app.py                       # Streamlit UI Dashboard
├── main.py                      # CrewAI Orchestrator Execution script
└── cache/                       # Stage-level JSON checkpoints
```

---

## 3. The 8-Stage Pipeline Reference

### Stage 00 — Topic Normalization

**Tool**: `utils/topic_normalizer.py`  
**Purpose**: Converts messy user input into a structured payload for high-precision retrieval.

- **Input**: Raw string (phrase or paragraph).
- **Logic**: Fast-path for short strings; LLM-parsing for complex descriptions.

- **Output Schema**:

```json
{
  "core_topic": "canonical label",
  "keywords": ["term1", "term2"],
  "domain": "biomedical|cs_ai|physics|...",
  "query_variants": ["variant1", "variant2"],
  "research_intent": "survey_gaps|propose_methodology|..."
}
```

### Stage 01 — Literature Mining

**Agent**: `literature_agent.py`  
**Purpose**: Multi-source retrieval and deduplication.

- **Interface**: Uses `MultiAPIFetcher` to fan out across arXiv, PubMed, Scholar, and CrossRef.

- **Output Schema**:

```json
{
  "topic": "raw input",
  "papers": [
    {
      "title": "...",
      "year": 2024,
      "summary": "2-3 sentence overview",
      "contribution": "most novel point",
      "api_source": "arXiv",
      "url": "..."
    }
  ]
}
```

### Stage 02 — Thematic Tree Builder

**Agent**: `tree_agent.py`  
**Purpose**: Synthesizes the corpus into a hierarchical index.

- **Input**: List of paper objects from Stage 01.
- **Quality Gate 1**: Validates that themes are distinct and papers correctly assigned.
- **Output Schema**:

```json
{
  "root": "topic name",
  "themes": [
    { "theme_id": "T1", "theme_name": "...", "papers": [...] }
  ],
  "emerging_directions": ["...", "..."]
}
```

### Stage 03 — Trend Analysis

**Agent**: `trend_agent.py`  
**Purpose**: Detects dominant clusters and emerging macro-signals.

- **Logic**: Analyzes the Thematic Tree structure to find areas of high vs. low concentration.
- **Output Schema**:

```json
{
  "dominant_clusters": ["cluster A", "cluster B"],
  "emerging_trends": ["trend X", "trend Y"]
}
```

### Stage 04 — Gap Identification

**Agent**: `gap_agent.py`  
**Purpose**: Isolates underexplored intersections.

- **Quality Gate 2**: Validates that gaps are actually supported by the missing literature in the tree.
- **Output Schema**:

```json
{
  "identified_gaps": [
    { "gap_id": "G1", "description": "...", "priority_rank": 1 }
  ],
  "selected_gap": "G1"
}
```

### Stage 05 — Methodology Evaluator

**Agents**: `methodology_agent.py` + `methodology_evaluator.py`  
**Purpose**: Pits a "Primary" methodology against a "Challenger" (alternative gap/method).

- **Logic**: Generates two distinct approaches and evaluates them based on feasibility, novelty, and coherence.
- **Output Schema**:

```json
{
  "winner": "A | B",
  "winning_methodology": { "experimental_design": "...", "tools": [...] },
  "winning_gap_description": "...",
  "reasoning": "Scientific justification for choice"
}
```

### Stage 06 — Format Selection

**Agent**: `format_matcher.py`  
**Purpose**: Matches research intent to funding agency schemas.

- **Logic**: Compares `domain` and `methodology` against agency constraints (e.g., career stage, budget scope).
- **Output**: Selected JSON template (e.g., `nsf_cise.json`).

### Stage 07 — Grant Writing

**Agent**: `grant_agent.py`  
**Purpose**: Generates full-bodied, format-compliant proposal content.

- **Logic**: Constrained by the specific section names and word counts defined in the Stage 06 format.
- **Output Schema**:

```json
{
  "title": "...",
  "problem_statement": "...",
  "sections": {
    "Intellectual Merit": "...",
    "Broader Impacts": "..."
  }
}
```

### Stage 08 — Novelty Scoring

**Agent**: `novelty_agent.py`  
**Purpose**: Final verification of the proposal's originality.

- **Process**:
  1. **Theme Pruning**: Identifies most relevant themes in the tree.
  2. **Deep Comparison**: Cross-references proposal against the 5 closest papers in those themes.

- **Output Schema**:

```json
{
  "novelty_score": 0-100,
  "closest_papers": ["Paper X", "Paper Y"],
  "score_justification": "Detailed reasoning"
}
```

---

## 4. Utility Components

### `utils/multi_api_fetcher.py`
- **Multiplexing**: Dynamic selection of APIs based on `domain` (CS → arXiv, Biomed → PubMed).
- **Deduplication**: Multi-pass deduplication logic using Title-Fuzzy-Match and DOI.
- **Rate-Limiting**: Built-in 2s delay between major fetches to prevent IP bans.

### `utils/quality_gate.py`

- **Logic**: Uses a lightweight LLM (Gemini Flash) as a judge.
- **Decision Matrix**: `PASS` (proceed), `REVISE` (redo with feedback), `FAIL` (abort or use fallback).
- **Status**: Currently runs in "Diagnostic Mode" (logs but does not block pipeline).

### `utils/schema.py`

- **Key Rotation**: Rounds-robin through available `GROQ_API_KEY_N` entries to bypass free-tier RPM limits.
- **JSON Sanitization**: `clean_json_response()` ensures the pipeline never breaks on markdown-wrapped LLM text.

---

## 5. Stability & Compliance Rules

1. **Paper Constraints**: Maximum 15-20 papers per run to stay within context window constraints and maintain synthesis quality.
2. **Date Filtering**: Strict `year >= 2018` filter by default, relaxing to 2015 if the initial pool is too small.
3. **JSON Enforcement**: Every agent call MUST use `safe_parse()`. No raw text strings are permitted in inter-agent communication.
4. **Mock Mode**: Setting `MOCK_MODE=True` in `.env` triggers static response injection for immediate testing.

### Project Metadata
