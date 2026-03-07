# Phase 3: Agent Implementation

This document provides a summary of Phase 3 and the commands to run its associated tests.

## Overview
In Phase 3, we built the 7 core components (agents) of the VMARO orchestration pipeline. These agents are responsible for executing independent tasks sequentially to achieve the overarching goal of retrieving literature, understanding gaps, formulating a methodology, and evaluating grant novelty.

**The 7 Agents implemented are:**
1. **Literature Agent (`literature_agent.py`)**: Fetches papers from Semantic Scholar and summarizes them using Gemini.
2. **Tree Builder Agent (`tree_agent.py`)**: Clusters the retrieved literature into hierarchical thematic trees and identifies emerging directions.
3. **Trend Agent (`trend_agent.py`)**: Analyzes the tree to identify dominant clusters and trends.
4. **Gap Agent (`gap_agent.py`)**: Identifies unexplored intersections/research gaps based on the trends and the tree.
5. **Methodology Agent (`methodology_agent.py`)**: Proposes a concrete experimental methodology to solve the identified gap.
6. **Grant Agent (`grant_agent.py`)**: Generates a funding-ready grant proposal comprising the problem statement, timeline, budget, and evaluation plan.
7. **Novelty Agent (`novelty_agent.py`)**: A two-step agent that compares the grant proposal to related themes, scopes down to the most relevant papers, and outputs a novelty score.

## Fallbacks and Safety
All agents are equipped with fallback schemas generated locally and employ heavy `try/except` bounds to never crash the pipeline. Specifically, the agents parse answers leveraging the `clean_json_response()` utility to gracefully fix Markdown fences and request Gemini to retry generating valid JSON up to one additional time. 

Additionally, we leverage a `MOCK_MODE` environment variable. When set to `true`, `literature_agent` halts its API requests and returns offline mock papers, and the test suite natively hooks into `MOCK_MODE` to pass mock assertions sequentially without burning live API rates.

## How to Run Phase 3 Mocks

Phase 3 is built robustly to ensure the correct output structure matches the expected validation dictionaries.
To verify functionality, run the complete `pytest` validation suite against the mock data:

```bash
python -m pytest tests/test_agents_mock.py -v
```

**Expected Result:** You should see 8 passing checks across all agents, asserting that all top-level keys are successfully present in every fallback validation schema.
