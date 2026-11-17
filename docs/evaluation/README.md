# Offline deduplication evaluation

The fuzzy methods in these scripts are experiments. The application uses
the author- and DOI-based matcher in `utils/multi_api_fetcher.py`.

## Inputs and replay

- [Cora Bibliographic from pyJedAI](../../work/cora-input/README.md), 1,295
  records and 17,184 supplied positive pairs. The original matcher was
  replayed at `57cdb319ffa411cbd8ad6b05f2a7d78e79655166`.
- [MaDI-Bench Scientific Papers](https://wbsg-uni-mannheim.github.io/MaDI-Bench/).
  At [revision 062058d](https://github.com/wbsg-uni-mannheim/MaDI-Bench/tree/062058d09c8abd97026e6d4e9908b433753f58d3/use%20cases/papers/base/input),
  download `dblp.jsonl`, `crossref.jsonl`, and `open_alex.jsonl` from
  `data/`, and `dblp_crossref_test.csv` and `dblp_openalex_test.csv` from
  `entitymatching/`. Place all five files in the directory passed below.
- SciPy is required by the two grouping replays. Install it in a separate
  replay environment with access to VMARO's Python dependencies.

From the repository root:

```sh
PYTHONPATH=. python scripts/cora_replay.py work/cora-input
PYTHONPATH=. python scripts/cora_fuzzy_experiment.py work/cora-input
PYTHONPATH=. python scripts/cora_affirmative_replay.py work/cora-input
PYTHONPATH=. python scripts/madi_fuzzy_grouping.py work/cora-input /path/to/madi-files
```

The fuzzy Cora experiment splits by labelled work and selects its settings
on the development side. The strict grouped replay uses a fixed 0.65 score
cutoff, a 0.10 compatible-author bonus, affirmative author or publication
evidence, and a veto for comparable first-author conflicts. It preserves
VMARO's existing groups, and the new merges apply only to DOI-free groups.

## Audit

[The audit CSV](madi-unlabelled-link-audit.csv) covers all 142 links added
by the evidence-gated hybrid outside MaDI-Bench's supplied labels.
Assessments other than the publisher-confirmed cases are metadata-based
triage. The three confirmed false links span copies of the same two works,
[Part 1](https://doi.org/10.1016/j.jcp.2019.02.049) and
[Part 2](https://doi.org/10.1016/j.jcp.2019.02.048). They do not represent
three independent failure modes. The numbered-part veto is a separate
offline ablation and can be replayed by the MaDI script.
