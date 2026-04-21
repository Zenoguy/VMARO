# 🔬 VMARO: Vectorless Multi-Agent Research Orchestrator

> Feed it a research topic -> Get back a comprehensive thematic tree, parallel methodology evaluations, and a structured, funding-ready grant proposal evaluated for novelty. All without a vector database or embeddings layer.

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg">
  <img src="https://img.shields.io/badge/Agents-CrewAI-orange.svg">
  <img src="https://img.shields.io/badge/Powered%20By-Gemini%20%26%20Groq-purple.svg">
  <img src="https://img.shields.io/badge/UI-Streamlit-red.svg">
</div>

---

## Overview

VMARO is an advanced **8-stage, multi-agent AI pipeline** orchestrating academic research and grant writing. Instead of the traditional, generic RAG mechanism (chunking texts and vector similarity), VMARO utilizes LLM-native structural synthesis to construct an interpretable "**Thematic Tree**" directly from multiple live academic sources.

The multi-model engine sequentially analyzes literature, detects emerging macro-trends, isolates critical research gaps, pits multiple methodologies against each other in a parallel "challenger" phase, formats the outcomes to specific institutional guidelines (e.g., NIH, NSF, ERC), and finally generates the full-bodied proposal with a quantified novelty score and PDF/LaTeX exports.

<p align="center">
  <img src="image/architechture.png" alt="System Architecture" width="800">
</p>

---

## Key Features & Architecture Improvements

- **Vectorless Navigation**: No FAISS, no ChromaDB. Replaces black-box semantic retrieval with direct semantic clustering, constructing a visual Thematic Tree directly from high-signal abstracts and metadata.
- **Intelligent Quality Gates**: Built-in "LLM-as-a-Judge" layers validate outputs iteratively between stages. If data is shallow or hallucinatory, the gate will flag it (`PASS`, `REVISE`, `FAIL`).
- **Parallel Methodology Evaluation**: VMARO doesn't just pick the first idea. It drafts a primary methodology, constructs a challenger counter-approach, and objectively evaluates which design has stronger statistical power and feasibility.
- **Intent-Aware Preprocessing**: Raw user input — whether a phrase or a paragraph — is normalized into a structured payload with domain classification, query variants, and explicit research intent (`survey_gaps`, `propose_methodology`) before retrieval begins. Prevents garbage-in-garbage-out at the pipeline root.

- **Institutional Format Matching**: Automatically restructures and tunes rhetorical tone to align with rigorous schemas (e.g., NSF, NIH, ERC) using a dedicated Format Matcher. You can upload custom JSON format templates as well.
- **Stateful Resiliency**: All outputs cache natively via `utils/cache.py`. Process interrupted? The pipeline resumes immediately from the last checkpoint to save API credits.

---

## The 8-Stage Pipeline

```text
[Research Topic]
       ↓
 0️⃣  Topic Normalization       (Intent classification + query variant generation)
       ↓
 1️⃣  Literature Mining         (Multi-API Fetcher: arXiv, PubMed, Scholar + LLM)
       ↓
 2️⃣  Thematic Tree Builder     (Clusters into hierarchical themes) → 🛡️ [Quality Gate 1]
       ↓
 3️⃣  Trend Analysis            (Detects dominant/emerging signals)
       ↓
 4️⃣  Gap Identification        (Auto-detects and ranks multiple research gaps) → 🛡️ [Quality Gate 2]
       ↓
     [User Intervenes: Selects Gap or Defines Custom]
       ↓
 5️⃣  Methodology Evaluator     (Drafts Primary vs Challenger Methodologies -> Selects Winner)
       ↓
 6️⃣  Format Selection          (Matches winning approach to grant styles + User Override)
       ↓
 7️⃣  Grant Writing             (Detailed content generation constrained by format schema)
       ↓
 8️⃣  Novelty Scoring           (Coarse tree pass → Deep paper comparison → 0-100 Score)
       ↓
[Streamlit Dashboard / LaTeX PDF Export]
```

### Dashboard Workflows in Action

<details>
<summary><b>1. Command Center / Overview Dashboard</b></summary>
<br>
<img src="image/usecase_overview.png" alt="Command Center Overview">
</details>

<details>
<summary><b>2. Literature Mining & Corpus Generation</b></summary>
<br>
<img src="image/usecase1_literature_corpus.png" alt="Literature Mining">
</details>

<details>
<summary><b>3. Thematic Tree Synthesis</b></summary>
<br>
<img src="image/usecase1_thematicTree.png" alt="Thematic Tree">
</details>

<details>
<summary><b>4. Gap Identification & Selection</b></summary>
<br>
<img src="image/usecase1_GAPSELECTION.png" alt="Gap Selection">
</details>

<details>
<summary><b>5. Parallel Methodology Evaluation</b></summary>
<br>
<img src="image/usecase1_methodology.png" alt="Methodology Evaluation">
</details>

<details>
<summary><b>6. Generated Proposal & Novelty Scoring</b></summary>
<br>
<img src="image/usecase1_GRANTPROPSAL.png" alt="Grant Proposal">
<img src="image/usecase1_Novelty.png" alt="Novelty Score">
</details>

---

## Quickstart

### 1. Clone & Environment

```bash
git clone https://github.com/your-org/vmaro.git
cd vmaro

# Create and sync virtual environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure API Keys

```bash
cp .env.example .env
```

Edit the `.env` to map your respective accounts. VMARO leverages multiple providers (Gemini / Groq / AWS) dynamically, handling round-robin request pools to bypass restrictive free-tier rate limits.

```ini
# Foundational LLMs
GROQ_API_KEY_1=your_key
GEMINI_4_AWS_KEY_1=your_key

# External sources (optional, standard use bypasses these if not provided)
SEMANTIC_SCHOLAR_KEY=
```

### 3. Run via CLI

To let the automated orchestrator handle everything programmatically:

```bash
python main.py --topic "Federated Learning in Bioinformatics"
```

*Want to bypass the parallel methodology evaluation? Add the `--no-parallel` flag.*

### 4. Interactive UI Mode (Recommended)

To utilize the dynamic visualizer (Agraph), manual gap selection intervention, and one-click Format/PDF generation:

```bash
streamlit run app.py
```

Open **`http://localhost:8501`** in your browser.

---

## Repository Structure

```text
vmaro/
├── agents/
│   ├── literature_agent.py      # Agent 1: Multi-API Fetch & Consolidate
│   ├── tree_agent.py            # Agent 2: Hierarchical Clustinger
│   ├── trend_agent.py           # Agent 3: Macro-Signals Identification
│   ├── gap_agent.py             # Agent 4: Target Discovery
│   ├── methodology_agent.py     # Agent 5a: Method generation
│   ├── methodology_evaluator.py # Agent 5b: Primary vs Challenger eval
│   ├── format_matcher.py        # Agent 6: Matching proposal formats
│   ├── grant_agent.py           # Agent 7: Format-compliant Grant Writing
│   └── novelty_agent.py         # Agent 8: Score validation
├── utils/
│   ├── multi_api_fetcher.py     # Scholar, PubMed, Arxiv, CrossRef multiplexer
│   ├── schema.py                # Pydantic-like validations, LLM cleanup & Key rotation
│   ├── quality_gate.py          # Quality evaluator middleware
│   ├── format_loader.py         # Loads and registers JSON schemas for Grants
│   └── latex_exporter.py        # Converts generated outputs to PDF / Tex
├── app.py                       # Modern Streamlit UI application
├── main.py                      # CrewAI Orchestrator Execution script
└── ...
```

---

## 📫 Capabilities vs Limitations

**Capabilities**:

- **Deduplication**: Multi-API fetches eliminate cross-source duplicates.
- **Robust Fail-Safes**: All keys are iterated cyclically. `clean_json_response()` parses markdown-polluted LLM responses flawlessly.

**Future Items**:

- Paper count is intentionally bounded at 20 to optimize token efficiency and maintain coherent thematic clustering — larger corpora dilute signal without improving output quality at current LLM context limits.
- Deeper automated web-searching in the Methodology generation phase for specific up-to-date Python/R package implementations.

