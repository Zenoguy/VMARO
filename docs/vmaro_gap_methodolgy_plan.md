# VMARO — Gap Selection UI + Parallel Methodology Agent
## Implementation Plan

---

## Overview

This plan covers two tightly coupled additions:

1. **User Gap Selection** — a UI interaction gate after Agent 3 where the user reviews identified gaps, selects one (or writes their own), and that selection drives Agent 4 onward
2. **Parallel Methodology Agent** — Agent 4 runs twice in parallel on the top two gaps (the user-selected gap plus the LLM-auto-selected gap as a challenger), a manager step picks the stronger output, and only the winner proceeds to Agent 5

These two features are sequenced deliberately: gap selection must exist before parallelization makes sense, because the parallel branch needs a clean "selected gap" as its primary input and a "challenger gap" as the secondary. Without explicit gap selection, you don't have a principled way to define which two gaps to branch on.

---

## Part 1 — User Gap Selection

### 1.1 What Changes Conceptually

Right now Agent 3 identifies multiple gaps and auto-selects one internally. The selected gap ID is buried in the JSON and `get_gap_desc()` in `main.py` just extracts it silently. The user never sees the other gaps at all.

The new flow:

```
Agent 3 runs → all gaps cached → pipeline PAUSES
                                        ↓
                             Streamlit shows all gaps
                             User reads, selects, or writes custom
                                        ↓
                             Selection written to cache
                                        ↓
                             Agent 4 resumes with selected gap
```

The pause is implemented via Streamlit session state — the UI renders the gap selector when `gaps` cache exists but `selected_gap` session key does not yet have a confirmed user choice.

---

### 1.2 Changes to Agent 3 Output (Schema 3)

No structural change to Schema 3 itself. Agent 3 already returns `identified_gaps` as a list and `selected_gap` as an auto-pick. The only change is that the auto-picked `selected_gap` field is now treated as a **suggestion**, not a final decision.

One small improvement worth making: ask Agent 3 to add a `priority_rank` (1 = highest) and a `feasibility_note` to each gap object. These two fields give the user enough signal to make an informed choice without reading the full gap description.

Updated gap object structure Agent 3 should return:

```
gap_id
description
supporting_evidence       (already exists)
priority_rank             NEW — integer 1-N, 1 = most impactful per LLM
feasibility_note          NEW — one sentence on why this gap is tractable
```

The Agent 3 prompt gets a small addition to its system instruction requesting these two fields. Everything else in Schema 3 stays the same.

---

### 1.3 Cache Changes

Two new cache entries:

| Key | Content | Written by |
|---|---|---|
| `user_gap_selection` | `{ "gap_id": "G2", "source": "user_selected" / "llm_suggested" / "user_custom", "description": "...", "is_custom": false }` | Streamlit UI on user confirm |
| `gaps` | unchanged — full Agent 3 output | Agent 3 (existing) |

The `source` field matters for the methodology prompt — if the gap is custom, Agent 4 gets a slightly different framing in its prompt (see 1.5).

The `user_gap_selection` cache key replaces the `get_gap_desc()` lambda in `main.py`. Agent 4 reads from `user_gap_selection["description"]` instead.

---

### 1.4 Streamlit UI — Gap Selection Widget

Position: between the Gaps tab and the Methodology tab. Shown only when `gaps` cache exists and `user_gap_selection` cache does not.

**Layout:**

```
┌─────────────────────────────────────────────────────┐
│  Research Gaps Identified                           │
│  Agent 3 found 4 gaps. Select one to develop.      │
│                                                     │
│  ○ [G1 ★★★] Lack of real-time federated models     │
│    Feasibility: Strong — several recent datasets    │
│    LLM recommended ← badge                         │
│                                                     │
│  ○ [G2 ★★☆] Insufficient privacy guarantees        │
│    Feasibility: Moderate — requires new crypto work │
│                                                     │
│  ○ [G3 ★☆☆] No cross-institutional benchmarks      │
│    Feasibility: Hard — coordination overhead high   │
│                                                     │
│  ○ [G4 ★★☆] Scalability on edge devices            │
│    Feasibility: Moderate — hardware constraints     │
│                                                     │
│  ─── Or define your own gap ───────────────────── │
│  ○ Custom gap                                       │
│  [ text area — describe your gap here ]             │
│                                                     │
│              [ Confirm Selection → ]                │
└─────────────────────────────────────────────────────┘
```

**Interaction rules:**

- Radio button selects from Agent 3 gaps OR activates the custom text area
- Custom text area is disabled unless "Custom gap" radio is selected
- "Confirm Selection →" button is disabled if custom is selected but text area is empty
- On confirm: selection is written to `user_gap_selection` cache, pipeline resumes
- A "Change selection" link appears after confirmation that clears `user_gap_selection` cache and re-shows the selector (also clears `methodology`, `format_match`, `grant`, `novelty` since they all depend on gap choice)

**Gap card display fields:**

- Gap ID badge
- Priority stars (derived from `priority_rank` — 3 stars = rank 1, 2 stars = rank 2, 1 star = rank 3+)
- Description (full text, not truncated)
- Feasibility note in a muted caption
- "LLM recommended" badge on whichever gap matches Agent 3's `selected_gap` field

---

### 1.5 Changes to Agent 4 Prompt for Custom Gaps

If `user_gap_selection["source"] == "user_custom"`, Agent 4's prompt gets an additional framing sentence:

> "The research gap below was defined by the researcher directly rather than extracted from the literature. Treat it as authoritative — do not second-guess or reframe it. Design a methodology that addresses exactly what is stated."

This prevents Agent 4 from "correcting" the user's gap back toward something closer to what Agent 3 would have said, which is an LLM tendency when it sees a gap that doesn't match its prior outputs.

For `user_selected` and `llm_suggested` sources, the prompt is unchanged.

---

### 1.6 Changes to main.py

`get_gap_desc()` is replaced by a function that reads from `user_gap_selection`:

```
def get_confirmed_gap():
    selection = load("user_gap_selection")
    if not selection:
        raise RuntimeError("Gap selection not confirmed — pipeline should not have continued.")
    return selection["description"], selection.get("source", "user_selected"), selection.get("is_custom", False)
```

The pipeline halts if `user_gap_selection` is not cached — it does not auto-proceed with the Agent 3 suggestion. This is a deliberate break from the current auto-proceed behavior.

For CLI runs (`python main.py --topic "..."`), a `--gap` argument is added that accepts either a gap ID (e.g. `--gap G2`) or a free-text string that is treated as a custom gap. If `--gap` is not provided and there is no cached selection, the CLI prints all gaps and prompts for input interactively. This ensures the CLI remains fully functional without the Streamlit UI.

---

## Part 2 — Parallel Methodology Agent

### 2.1 Concept

Agent 4 currently runs once on the user-selected gap. The parallel version runs Agent 4 **twice simultaneously** — once on the primary gap (user-selected) and once on a challenger gap (the highest-priority unselected gap from Agent 3's list). A lightweight **Methodology Evaluator** then reads both outputs and picks the stronger one based on feasibility, scope fit, and alignment with the research topic.

Why bother running a challenger? Two reasons:

- It forces Agent 4 to produce two distinct methodology approaches, which gives the evaluator something real to compare rather than trivially similar outputs
- The winning methodology is empirically better than a single run — you are doing one round of selection pressure on the output quality
- It makes CrewAI's `Process.hierarchical` actually earn its place in the architecture

The user does not pick between the two methodologies — that would add another interaction gate and slow the pipeline. The evaluator picks automatically and its reasoning is shown in the UI as a transparency note.

---

### 2.2 Identifying the Challenger Gap

The challenger gap is always the **highest-priority gap that is not the user-selected gap**, taken from Agent 3's `identified_gaps` list sorted by `priority_rank`.

Logic:

```
all_gaps = agent3_output["identified_gaps"]
primary_gap_id = user_gap_selection["gap_id"]

if source == "user_custom":
    # No gap_id to exclude — use Agent 3's top-ranked gap as challenger
    challenger = all_gaps sorted by priority_rank, take first

else:
    # Exclude the user-selected gap
    challenger = all_gaps sorted by priority_rank, excluding primary_gap_id, take first
```

If Agent 3 only identified one gap, or if all gaps are ranked equally, skip the parallel run and proceed with a single methodology. This edge case must be handled gracefully — the evaluator step is bypassed and the single methodology is used directly.

---

### 2.3 Pipeline Structure Change

Current:
```
[user_gap_selection] → Agent 4 (methodology) → Agent 5
```

New:
```
[user_gap_selection]
        ↓
  ┌─────────────────────────────────────┐
  │  Parallel branch (CrewAI parallel)  │
  │                                     │
  │  Agent 4-A (primary gap)            │
  │  Agent 4-B (challenger gap)         │
  └─────────────────────────────────────┘
        ↓
  Methodology Evaluator (manager step)
        ↓
  [winning_methodology] → FormatMatcher → Agent 5
```

---

### 2.4 CrewAI Implementation Strategy

This is where CrewAI finally does real work.

Switch the Crew process from `Process.sequential` to `Process.hierarchical` for the methodology branch only. The rest of the pipeline remains sequential.

Structure:

- **Manager agent:** "Methodology Quality Evaluator" — given both methodology outputs, selects the winner
- **Worker agent A:** runs `run_methodology(primary_gap_description, topic)` 
- **Worker agent B:** runs `run_methodology(challenger_gap_description, topic)`

In `Process.hierarchical`, the manager agent decomposes the task and assigns subtasks to workers. In practice for our use case, we pre-define both worker tasks and the manager task — we are not relying on the manager to dynamically plan. The manager's only job is to read both outputs and return a decision.

The manager agent receives both methodology JSONs and returns:
```
{
  "winner": "A" | "B",
  "reasoning": "Agent 4-A produced a more coherent experimental design with clearer phase separation...",
  "winning_methodology": { ...full Schema 4 dict of the winner... }
}
```

This decision is cached under `methodology_eval` and the `winning_methodology` field becomes the input to FormatMatcher and Agent 5.

---

### 2.5 New Agent: Methodology Evaluator

**File:** `agents/methodology_evaluator.py`  
**Position:** After both parallel Agent 4 runs complete

**Inputs:**
- `methodology_a` — Schema 4 output for primary gap
- `methodology_b` — Schema 4 output for challenger gap
- `topic` — research topic string
- `primary_gap_description` — description of the user-selected gap
- `challenger_gap_description` — description of the challenger gap

**Evaluation criteria in the prompt:**
- Scientific coherence — does the methodology follow logically from the gap?
- Scope appropriateness — is the scope realistic for a single grant cycle?
- Methodological novelty — does it go beyond obvious approaches?
- Phase clarity — are the research phases clearly defined with distinct deliverables?
- Gap fit — how tightly does the methodology address the specific gap stated?

**Output (cache key: `methodology_eval`):**
```
{
  "winner": "A",
  "methodology_a_score": 0.0-1.0,
  "methodology_b_score": 0.0-1.0,
  "reasoning": "...",
  "winning_methodology": { ...Schema 4... },
  "winning_gap_description": "...",
  "parallel_was_run": true | false
}
```

The `parallel_was_run` flag allows the UI to conditionally show the comparison reasoning — if only one methodology was run (edge case), the evaluator is bypassed and this flag is false.

---

### 2.6 Cache Changes

Two new cache entries:

| Key | Content | Written by |
|---|---|---|
| `methodology_a` | Schema 4 — primary gap methodology | Agent 4-A |
| `methodology_b` | Schema 4 — challenger gap methodology | Agent 4-B |
| `methodology_eval` | Evaluator output including winner and reasoning | Methodology Evaluator |

The existing `methodology` cache key is replaced by `methodology_eval["winning_methodology"]` as the canonical methodology going forward. All downstream references to `load("methodology")` in main.py are updated to `load("methodology_eval")["winning_methodology"]`.

---

### 2.7 Streamlit UI Changes for Parallel Methodology

After the Methodology tab content, add a collapsible "Parallel evaluation" expander:

```
┌──────────────────────────────────────────────────────┐
│  ▼ Methodology Evaluation (parallel run)             │
│                                                      │
│  Two methodologies were generated in parallel.       │
│  The stronger one was selected automatically.        │
│                                                      │
│  Primary gap methodology      score: 0.81  ✓ WINNER │
│  [gap A description]                                 │
│                                                      │
│  Challenger gap methodology   score: 0.67           │
│  [gap B description]                                 │
│                                                      │
│  Evaluator reasoning:                                │
│  "Primary gap methodology showed clearer phase       │
│   separation and more tractable milestones..."       │
│                                                      │
│  [Override — use challenger instead]  ← small link  │
└──────────────────────────────────────────────────────┘
```

The "Override" link is an escape hatch — it writes `methodology_b` as the canonical methodology, clears `format_match`, `grant`, and `novelty` caches, and re-runs from FormatMatcher. This gives the researcher full control without making the override the primary flow.

If `parallel_was_run` is false (only one methodology generated), the expander is hidden and a caption reads "Single methodology generated — parallel run skipped (insufficient distinct gaps)."

---

### 2.8 Changes to main.py

The methodology section of the pipeline task list changes from one task to three:

```
t5-A   → Agent 4-A: methodology for primary gap
t5-B   → Agent 4-B: methodology for challenger gap   (may be skipped)
t5-Ev  → Methodology Evaluator: pick winner
```

These three tasks replace the single `t5` task currently in the list.

The Crew instantiation for this section uses `Process.hierarchical` with the Evaluator as manager and Agent 4-A/B as workers. The surrounding pipeline remains `Process.sequential`.

One practical implementation note: CrewAI's `Process.hierarchical` requires the manager agent to have an LLM assigned. Since we are using the mock OpenAI key trick for the rest of the pipeline, the manager agent for this section will need a real Groq key passed as its LLM. The evaluator's Groq call is already handled by `call_gemini_with_retry` the same way every other agent works — the CrewAI manager wrapper just needs to not crash on initialization, which is handled by assigning it the same dummy LLM config the other agents use.

---

### 2.9 CLI Changes

Add `--no-parallel` flag to `main.py` for situations where the user wants to skip the parallel run (e.g. debugging, rate limit conservation):

```
python main.py --topic "Federated Learning" --gap G2 --no-parallel
```

With `--no-parallel`, the methodology section runs Agent 4 once on the selected gap only, the evaluator is skipped, and `methodology_eval` is written with `parallel_was_run: false` and the single result as `winning_methodology`.

---

## Part 3 — Implementation Order

```
Step 1 — Update Agent 3 prompt
  Add priority_rank and feasibility_note to gap object schema in Agent 3 system instruction.
  Update mock_gaps.json to include these fields on all gap objects.
  Test: run Agent 3 in mock mode, verify all gaps have priority_rank and feasibility_note.

Step 2 — user_gap_selection cache structure
  Define the cache dict structure.
  Add load/save wrappers in utils/cache.py if needed (probably just uses existing save/load).
  No new files — just agree on the dict shape.

Step 3 — CLI gap selection
  Add --gap argument to main.py argparse.
  Implement get_confirmed_gap() replacing get_gap_desc().
  Implement interactive CLI fallback when --gap not provided.
  Test: CLI run with --gap G1, verify correct gap description reaches Agent 4.
  Test: CLI run without --gap, verify interactive prompt works.

Step 4 — Streamlit gap selection widget
  Implement gap card rendering from Agent 3 output.
  Implement radio button + custom text area interaction.
  Implement Confirm button writing to user_gap_selection cache.
  Implement "Change selection" clearing downstream caches.
  Test: full UI run, select each gap type, verify downstream tabs update.
  Test: custom gap input, verify Agent 4 receives custom text.

Step 5 — Challenger gap identification logic
  Implement get_challenger_gap() function in main.py or utils/.
  Handle edge cases: single gap, tied ranks, custom primary gap.
  Test: various Agent 3 outputs with different gap counts and ranks.

Step 6 — Agent 4-A and Agent 4-B tasks
  Agent 4 code itself does not change — it is called twice with different gap inputs.
  Add methodology_a and methodology_b as separate cache keys.
  Implement in main.py as two tasks with distinct cache keys.
  Test: both methodology JSONs appear in cache/ after run.

Step 7 — Methodology Evaluator agent
  Create agents/methodology_evaluator.py.
  Implement evaluation prompt with five scoring criteria.
  Implement parallel_was_run: false edge case handling.
  Cache output under methodology_eval.
  Test: evaluator correctly picks winner from two mock methodology JSONs.
  Test: evaluator handles single-methodology edge case.

Step 8 — CrewAI hierarchical process for methodology branch
  Wrap Agent 4-A, 4-B, and Evaluator tasks in Process.hierarchical sub-crew.
  Verify existing sequential pipeline is not disrupted.
  Test: full CLI run with parallel branch, verify no CrewAI auth errors block execution.

Step 9 — Update downstream references
  All references to load("methodology") → load("methodology_eval")["winning_methodology"].
  Update FormatMatcher, Agent 5, Agent 6 inputs in main.py.
  Test: full end-to-end run, verify grant and novelty outputs use winning methodology.

Step 10 — Streamlit parallel evaluation expander
  Implement the evaluation expander in app.py.
  Implement override link with cache clearing.
  Test: override correctly swaps methodology and re-runs downstream.
  Test: parallel_was_run: false correctly hides the expander.
```

---

## Part 4 — Testing Checklist

### Gap Selection
- [ ] Agent 3 output includes `priority_rank` and `feasibility_note` on all gap objects
- [ ] Gap cards render correctly in Streamlit with priority stars and feasibility caption
- [ ] LLM recommended badge appears on correct gap
- [ ] Selecting a gap and confirming writes `user_gap_selection` to cache
- [ ] Custom gap text is passed to Agent 4 with the custom-gap framing sentence
- [ ] Custom gap with empty text area does not allow confirmation
- [ ] "Change selection" clears `user_gap_selection`, `methodology_eval`, `format_match`, `grant`, `novelty`
- [ ] CLI `--gap G2` correctly bypasses interactive prompt
- [ ] CLI without `--gap` shows interactive gap list and accepts input

### Parallel Methodology
- [ ] Two distinct methodology JSONs appear in cache as `methodology_a` and `methodology_b`
- [ ] Evaluator returns `winner`, scores, and `winning_methodology`
- [ ] `methodology_eval["winning_methodology"]` reaches Agent 5 correctly
- [ ] Single-gap edge case: `parallel_was_run: false`, evaluator skipped, single methodology used
- [ ] UI expander shows both scores and evaluator reasoning
- [ ] Override link correctly swaps to challenger methodology and clears downstream caches
- [ ] `--no-parallel` flag skips Agent 4-B and evaluator
- [ ] Full end-to-end run produces a coherent grant proposal using winning methodology

---

## Part 5 — What This Unlocks for the Report

**Gap selection** closes the limitation explicitly called out in the README. You can now say: "VMARO surfaces all identified research gaps with priority ranking and feasibility annotations, and allows the researcher to exercise judgment over which direction the proposal takes — including defining a novel gap not present in the literature."

**Custom gap input** is the stronger claim. It means VMARO is not a closed system that imposes its own framing on the researcher — it accepts the researcher's domain knowledge as a first-class input. The custom gap framing sentence in Agent 4's prompt is the implementation detail that makes this real rather than cosmetic.

**Parallel methodology** is the answer to the CrewAI question. You can now say: "CrewAI's `Process.hierarchical` is used for the methodology generation step, where two methodology candidates are generated in parallel on competing research gaps, and a manager agent selects the stronger output. This is the only part of the pipeline where parallelism adds genuine quality value — the remaining steps are inherently sequential."

These three things together — user gap selection, custom gap input, and parallel methodology with evaluator — represent a coherent upgrade from "automated pipeline" to "researcher-in-the-loop pipeline." That framing is worth using explicitly in the report.
