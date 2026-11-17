Public Cora Bibliographic benchmark from the pyJedAI repository at
`data/der/cora/`. The records and supplied pair labels are pipe-delimited.

- [cora.csv](https://raw.githubusercontent.com/AI-team-UoA/pyJedAI/main/data/der/cora/cora.csv)
- [cora_gt.csv](https://raw.githubusercontent.com/AI-team-UoA/pyJedAI/main/data/der/cora/cora_gt.csv)

Run from the VMARO repository root:

```sh
PYTHONPATH=. python scripts/cora_replay.py work/cora-input
```

The CSV inputs and generated replay output are local files.
