# VMARO
### Vectorless Multi-Agent Research Orchestrator

> Feed it a research topic. Get back a grant proposal, a thematic literature tree, and a novelty score — no vector database, no embeddings, zero cost.

---

## What It Does

VMARO is a 6-agent sequential pipeline built with CrewAI and Groq. You give it a research topic; it intelligently retrieves real papers across multiple academic databases (Semantic Scholar, arXiv, CrossRef, OpenAlex, PubMed), auto-deduplicates them, clusters them into a thematic tree, identifies research gaps, designs a methodology, writes a funding-ready grant proposal, and scores how novel that proposal is against the existing literature.

The "vectorless" part is the point: instead of cosine similarity over embeddings, the pipeline uses an LLM-native hierarchical tree to navigate the literature. More interpretable, zero infrastructure.

```
[Research Topic]
      ↓
  Agent 1 — Literature Mining        Multi-API Fetcher + Groq
      ↓
  Tree Index Builder                 Groq  [above spec]
      ↓
  [Quality Gate]                     PASS / REVISE / FAIL
      ↓
  Agent 2 — Trend Analysis           Groq
      ↓
  Agent 3 — Gap Identification       Groq
      ↓
  [Quality Gate]                     PASS / REVISE / FAIL
      ↓
  Agent 4 — Methodology Design       Groq
      ↓
  Agent 5 — Grant Writing            Groq
      ↓
  Agent 6 — Novelty Scoring          Groq  (2-step)
      ↓
  [Streamlit Dashboard]
```

---

## Quickstart

### 1. Clone & install

```bash
git clone https://github.com/your-org/vmaro.git
cd vmaro
pip install -r requirements.txt
```

### 2. Set up API keys

```bash
cp .env.example .env
```

Edit `.env` and add your Groq API keys. All three are free — create accounts at [Groq Console](https://console.groq.com):

```
GROQ_API_KEY_1=your_first_key
GROQ_API_KEY_2=your_second_key
GROQ_API_KEY_3=your_third_key
```

You do not need API keys for the academic databases for standard use.

### 3. Run the pipeline (CLI)

```bash
python main.py --topic "Federated Learning in Healthcare"
```

All agent outputs are saved to `cache/` after each step. If a run fails mid-pipeline, re-running resumes from the last successful checkpoint — no wasted API credits.

### 4. Run the UI

```bash
streamlit run app.py
```

Open `http://localhost:8501`, enter a topic, and click **Run Analysis**.

---

## Architecture

### The 6 Agents

| # | Agent | Input | Output |
|---|-------|-------|--------|
| 1 | Literature Mining | Research topic string | Schema 1 — papers JSON |
| 2 | Trend Analysis | Schema 2 — tree | Dominant clusters + emerging trends |
| 3 | Gap Identification | Schema 2 + trends | Schema 3 — gaps JSON |
| 4 | Methodology Design | Selected gap | Schema 4 — methodology JSON |
| 5 | Grant Writing | Gap + methodology | Schema 5 — grant proposal JSON |
| 6 | Novelty Scoring | Grant + tree | Schema 6 — novelty score JSON |

### Above-Spec Additions

**Tree Index Builder** sits between Agent 1 and Agent 2. Rather than passing Agent 2 a flat list of papers, the Tree Builder first clusters them into 3–5 thematic groups using Groq's Moonshot model. Agent 2 then operates on a structured hierarchy instead of a raw list — producing more coherent trend analysis and better-scoped gap identification downstream.

**LLM Quality Gates** run after Agent 1 and after Agent 3 — the two stages most likely to produce shallow output that silently degrades everything downstream. Each gate makes a single Groq API call and returns `PASS`, `REVISE`, or `FAIL` with a confidence score. In demo mode the gate logs its decision to the terminal and does not block the pipeline, keeping runtime fast while remaining visible as a talking point.

### Why Vectorless?

Traditional RAG pipelines need FAISS or ChromaDB, embedding models, and infrastructure to keep indexes fresh. The Tree Index Builder replaces similarity search with LLM-native hierarchical navigation: Groq's Moonshot reads the papers and constructs the theme tree directly. The result is more interpretable (you can read the tree), requires zero infrastructure, and runs entirely within Groq's free tier.

### Agent 1 — Two-Pass Design

Literature Mining is split into two distinct passes to prevent LLM hallucination of paper metadata (a known failure mode of prompt-based retrieval):

- **Pass 1 — Retrieval:** A Multi-API Fetcher intelligently routes queries to Semantic Scholar, arXiv, CrossRef, OpenAlex, and PubMed based on topic keywords. It fetches real papers with real metadata and auto-deduplicates them. No LLM involved.
- **Pass 2 — Intelligence:** Groq's Moonshot reads the abstracts and writes summaries + extracts contributions. No retrieval involved.

Separating these responsibilities means the pipeline never invents papers that don't exist.

### Agent 6 — Two-Step Novelty Scoring

Novelty scoring runs in two internally-chained steps to keep each API call well-scoped:

- **Step 1 — Tree Navigation:** The model reads only the theme names and identifies which themes are most relevant to the grant proposal. Fast, low-token.
- **Step 2 — Paper Comparison:** The model reads the full grant proposal against only the papers from the selected themes (3–5 papers maximum). Rates novelty 0–100 with justification.

This mirrors how human peer reviewers assess novelty: coarse pass first, deep read second.

---

## API & Cost

| Task | API | Notes |
|------|-----|-------|
| Paper retrieval | Semantic Scholar, arXiv, PubMed, CrossRef, OpenAlex | Free, automatic topic-based routing, automatic deduplication |
| All LLM tasks | Groq Moonshot (`moonshotai/kimi-k2-instruct-0905`) | Free tier |

The pipeline makes approximately 10 LLM calls per run. With 3 Groq keys (one per team member), the API limits are sufficient for development and demo use.

Key rotation is handled automatically in `utils/schema.py` via a round-robin pool.

---

## Repo Structure

```
vmaro/
├── agents/
│   ├── literature_agent.py     # Agent 1 — Multi-API Fetcher + Groq
│   ├── tree_agent.py           # Tree Index Builder (above spec)
│   ├── trend_agent.py          # Agent 2
│   ├── gap_agent.py            # Agent 3
│   ├── methodology_agent.py    # Agent 4
│   ├── grant_agent.py          # Agent 5
│   └── novelty_agent.py        # Agent 6 (two-step)
├── utils/
│   ├── multi_api_fetcher.py    # Cross-database paper fetching & deduplication
│   ├── schema.py               # JSON validators + clean_json_response() + key rotation
│   ├── cache.py                # Checkpoint cache (writes to cache/ after each agent)
│   └── quality_gate.py         # Reusable LLM quality gate
├── mock_data/                  # Static JSON fixtures for all 6 schemas
├── cache/                      # Runtime checkpoints (auto-created, gitignored)
├── main.py                     # CrewAI orchestrator
├── app.py                      # Streamlit dashboard
├── requirements.txt
├── .env.example
└── README.md
```

---

## Stability

- Paper corpus is capped at **8–15 papers per run** to prevent token overflow
- Every API call is wrapped in `try/except` — the pipeline returns a fallback response and never crashes
- Groq occasionally wraps JSON output in markdown fences — `clean_json_response()` in `utils/schema.py` strips these before every parse, with one automatic retry on malformed output
- CrewAI is pinned to a specific version in `requirements.txt` — it has frequent breaking changes between minor versions

---

## Limitations & Future Work

**Automated gap selection.** The Gap Identification Agent currently auto-selects a gap. A natural UI extension would let the user review all identified gaps and choose which one to build the methodology and proposal around — making VMARO interactive rather than fully automated.

---

## Team

| Person | Owns |
|--------|------|
| Person A | Agent 1 · Tree Index Builder · `utils/` · `main.py` · mock data |
| Person B | Agent 2 · Agent 3 · Agent 4 |
| Person C | Agent 5 · Agent 6 · Streamlit UI |

---

## License

MIT
# VMARO
# VMARO
# VMARO
# VMARO
# VMARO
# VMARO
# VMARO
