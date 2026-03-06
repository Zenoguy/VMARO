# Phase 1 & 2 Review Guide

This document summarizes the work completed for Phase 1 (Scaffolding) and Phase 2 (Utilities), and provides the exact commands you need to run to verify that everything is working perfectly before we move on to Phase 3 (Agents).

## 1. Phase 1 — Repo Scaffolding

**What was done:**
- Created the core directory structure (`agents/`, `utils/`, `mock_data/`, `cache/`).
- Created stub Python files for all 7 agents, each strictly adhering to the standard `run()` interface we defined.
- Created configuration files (`main.py`, `app.py`, `.env.example`, `.gitignore`, `requirements.txt`).
- Populated `mock_data/` with 6 distinct JSON files matching the strict schemas defined in `VMARO_spec.md`. We expanded this data to cover 9 realistic papers and 3 themes, so that the downstream agents (like Novelty scoring) have proper data to filter and evaluate.

**How to verify:**
You can review the directory structure and the mock data we generated directly in your terminal.

```bash
# View the tree structure of the repository
tree .

# Inspect the expanded mock data schemas (example: the papers)
cat mock_data/mock_papers.json
cat mock_data/mock_tree.json
```

## 2. Phase 2 — Utilities

**What was done:**
We fully implemented the shared foundational layer that all agents will rely on.
- **`utils/schema.py`**: Handles round-robin API key rotation via `itertools.cycle` and safely parses JSON by stripping out any Markdown fences (e.g., ` ```json `) that Gemini might mistakenly include in its output.
- **`utils/cache.py`**: Automates saving and loading JSON state to the `cache/` directory so the pipeline can resume where it left off on failure.
- **`utils/quality_gate.py`**: A reusable LLM quality gate that queries Gemini Flash to evaluate intermediate JSON outputs (`PASS`, `REVISE`, or `FAIL`). It securely falls back to `PASS` on API failures or when `DEMO_MODE=true` is set.

**How to verify:**
We wrote a comprehensive test suite (`tests/test_utils.py`) to verify all of these features. You can run the tests yourself inside the virtual environment we set up!

Run the following commands in your terminal:

```bash
# 1. Activate the virtual environment
source venv/bin/activate

# 2. Run the test suite for the utilities
python -m unittest tests/test_utils.py -v
```

**Expected Result:** You should see 9 highly specific tests running, ending with an `OK`, confirming that JSON parsing, key cycling, and caching all work exactly as planned.

---

## Next Steps
Once you are satisfied with the scaffolding and utility tests, we can move on to **Phase 3**, where we will start implementing the actual intelligence into the agent stubs inside the `agents/` directory, starting with `literature_agent.py`.
