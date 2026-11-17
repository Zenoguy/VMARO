# VMARO independent validation, 17 November 2026

## Scope and provenance

Code: user's uploaded `VMARO-main (1).zip`; matcher file is verified identical to the GitHub default-branch blob on 17 November 2026 (Git blob SHA1 `39ea1c973f1d8f1a433a5e78b9d11b420bf0db08`). The uploaded source file SHA256 is `ee8af17ce650e825a813cd7081e4b47252a9885311499ecbd7ea215fc14943cf`. The ACL/arXiv corpus and MaDI audit are copied without modification from the paper and code uploads; see `data/`.

### New measurement: updated production matcher on ACL/arXiv

50 real records, 26 distinct works, 24 verified pairs. There are 624 cross-source candidate pairs (24 positive; 600 negative). `utils.multi_api_fetcher.MultiAPIFetcher._deduplicate` was run directly on the uploaded corpus, not reimplemented as a comparator. Set `authors` to the observed first author (single-item list) and `doi` to the ACL venue DOI and, depending on condition, either empty or the observed arXiv DOI. No Crossref relationship claims were invented.

| DOI projection | TP | FP | FN | Precision | Recall | F1 | Output representatives |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| arXiv DOI absent | 23 | 0 | 1 | 1.000 | 0.958 | 0.979 | 27 |
| both distinct DOIs supplied | 0 | 0 | 24 | undefined | 0 | 0 | 50 |

This is *not* proof the algorithm cannot match two DOIs: it requires explicit unambiguous Crossref relationship metadata, which this fixed input does not contain. No such relationship was injected from ground truth.

Across 1,000 shuffles per condition, the output pair sets were invariant: exactly one pattern for each condition. Under 1,000 independent deterministic order shuffles (seed `20261116`) and a 20-representative cap, the absent-arXiv-DOI condition recovered 19.753 distinct works on average; full numbers for caps 5,10,20 in `results/new_matcher_acl_results.json`.

### Unit tests

`python -m unittest -q tests.test_multi_api_fetcher tests.test_cora_replay` passed **26/26**. `python -m unittest discover -s tests -v` could not import `tests.test_agents_mock` and `tests.test_utils` because the `groq` SDK is unavailable in this runtime. These are two *unloaded modules*, not two failed assertions, so the full test suite is **not verified**. No real API integrations were exercised.

### Independent Cora reference computation

From pyJedAI `data/der/cora/cora.csv` and `cora_gt.csv` on GitHub, the exact normalized-title baseline was recalculated independently (JavaScript execution on fetched raw records; not execution of VMARO Python matcher): **1295 records, 112 labelled works, 17,184 positive pairs, 12,907 TP, 3,868 FP, 4,277 FN, F1=0.760152**. This cross-check reproduces the existing manuscript's exact-title baseline. It does **not** establish current-production matcher or fuzzy-gated scores on all Cora records. Raw Cora files were not available in the offline Python container, so the repository's full `scripts/cora_*` evaluations were not executed.

External data source: https://github.com/AI-team-UoA/pyJedAI/tree/main/data/der/cora

### Independent MaDI audit checking

142 previously classified unlabelled candidate links in the uploaded repository were read and **each pair** passed through the updated production matcher using the recorded title and author roster (DOIs absent). None was joined by that stricter path; all three publisher-confirmed false-merge *link records* are rejected. The experimental `part_conflict()` check flags those three, involving two distinct numbered-part works (and duplicates of the same DBLP record across two source comparisons). The 40 metadata-supported, 49 suspected nonduplicates, and 50 unresolved records are not authoritative ground truth. These audit checks are **not** the MaDI benchmark test-set accuracy scores.

The two MaDI labelled test pair files at the pinned benchmark revision each contain 6,666 labelled pairs (1,666 positive and 5,000 negative). Since complete source JSONL datasets were not accessible inside the Python runtime, the source's full `scripts/madi_fuzzy_grouping.py` benchmark was not executed.

MaDI source: https://github.com/wbsg-uni-mannheim/MaDI-Bench/tree/062058d09c8abd97026e6d4e9908b433753f58d3

### Reproduction in a compatible Python environment

Place the two data CSVs from this package alongside the scripts or update the paths in these three validator scripts to match your checkout; then run:

```bash
PYTHONPATH=/path/to/VMARO python scripts/validate_new_matcher.py
PYTHONPATH=/path/to/VMARO python scripts/validate_order_stability.py
PYTHONPATH=/path/to/VMARO python scripts/validate_madi_audit.py
```

For the full corpora, run the upstream scripts with their documented data inputs and exact source revision (requires the full original Git repository for `cora_replay.py`'s `git show` historical comparison):

```bash
PYTHONPATH=. python scripts/cora_fuzzy_experiment.py work/cora-input
PYTHONPATH=. python scripts/cora_affirmative_replay.py work/cora-input
PYTHONPATH=. python scripts/madi_fuzzy_grouping.py work/cora-input /path/to/madi-files
```

### Research-validity constraints

No new Cora current-matcher F1, MaDI test-set F1, dense retrieval comparison, end-to-end research-output quality, or live API usage has been measured here. Do not add such scores to the manuscript. `score=0` with no predicted positives has undefined precision, not zero precision. The comparison of archived and current code should use source-version labels and shared projections.
