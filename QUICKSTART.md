# VMARO — Quick Start Guide

## Prerequisites

- Python 3.10+
- At least 1 Gemini API key ([get one free](https://aistudio.google.com/apikey))

---

## 1. Setup

```bash
# Clone / navigate to the project
cd VAMRO

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure your API keys
cp .env.example .env
```

Edit `.env` and paste your Gemini keys:

```
GEMINI_KEY_1=AIzaSy...your-first-key
GEMINI_KEY_2=AIzaSy...your-second-key    # optional, reduces rate-limiting
GEMINI_KEY_3=AIzaSy...your-third-key     # optional
SEMANTIC_SCHOLAR_KEY=                     # optional, works without it
DEMO_MODE=true                            # recommended: gates won't block the pipeline
MOCK_MODE=false                           # must be false for real API calls
```

> **Tip:** With 3 keys the pipeline runs in ~2 minutes. With 1 key it may take ~10 minutes due to rate-limit retries.

---

## 2. Run the Pipeline (CLI)

```bash
python main.py --topic "Federated Learning in Healthcare"
```

You'll see the agents execute in sequence:

```
Starting pipeline for topic: 'Federated Learning in Healthcare'

[Agent1]       Literature Mining
Cooling down for 2s to allow rotating keys to reset limits...
[TreeBuilder]  Building thematic tree
Cooling down for 2s to allow rotating keys to reset limits...
[QualityGate:post_literature] PASS (confidence=0.9): ...
...
[Agent6]       Novelty Scoring
Cooling down for 2s to allow rotating keys to reset limits...

Pipeline execution complete. Results saved to cache/ directory.
```

Results are saved to `cache/` as individual JSON files:

| File | Contents |
|------|----------|
| `papers.json` | Retrieved literature + summaries |
| `tree.json` | Thematic clustering of papers |
| `trends.json` | Dominant clusters + emerging trends |
| `gaps.json` | Research gaps + selected gap |
| `methodology.json` | Experimental design + tools |
| `grant.json` | Full funding-ready grant proposal |
| `novelty.json` | Novelty score (0–100) + justification |

### Cache-Resume

If the pipeline crashes mid-run (e.g. API quota exhaustion), **just re-run the same command**. It automatically skips completed stages and resumes from where it left off.

To start fresh, delete the cache:

```bash
rm -rf cache/
python main.py --topic "Your New Topic"
```

---

## 3. Run the Streamlit Dashboard (UI)

```bash
streamlit run app.py
```

This opens a browser at `http://localhost:8501` with:

1. **Sidebar** — Enter your research topic and click **▶ Run Analysis**
2. **📚 Literature** — Cards for each retrieved paper (title, year, summary, source link)
3. **📊 Tree Index** — Expandable thematic clusters with paper lists
4. **📈 Trends & Gaps** — Two-column layout: trends on the left, gap cards on the right
5. **🧪 Methodology** — Datasets, metrics, baselines, experimental design, tools
6. **📝 Grant Proposal** — Full rendered proposal with a **Download JSON** button
7. **⭐ Novelty Score** — Color-coded score: 🔴 < 40, 🟡 < 70, 🟢 ≥ 70

> The UI runs the full pipeline behind the scenes. If cache already exists for the same topic, it loads instantly.

### Changing Topics

The UI automatically clears the cache when you enter a new topic and click Run.

---

## 4. Run Tests (Mock Mode)

```bash
# Unit tests (no API calls needed)
PYTHONPATH=. MOCK_MODE=true DEMO_MODE=true GEMINI_KEY_1=mock pytest tests/test_utils.py -v

# Agent mock tests (literature_agent uses mock data; other agents need real keys)
PYTHONPATH=. pytest tests/test_agents_mock.py -v
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `429 — waiting Xs before retry` | Normal rate-limiting. The pipeline retries automatically. Add more keys to `.env` to reduce waits. |
| `Invalid API Key — swapping to next key` | One of your keys is wrong or expired. The pipeline auto-rotates to the next valid key. |
| `503 Unavailable` | Gemini servers are busy. Auto-retries after 15s. |
| `Max retries exceeded` | All retries exhausted. Wait a few minutes and re-run — cache-resume will pick up where it left off. |
| Pipeline is slow with 1 key | Get 2-3 free keys from [AI Studio](https://aistudio.google.com/apikey) — each key has its own rate limit. |
