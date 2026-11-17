"""Replay the MaDI-Bench affirmative evidence gate on real Cora citations."""
import argparse
from pathlib import Path

from scripts.cora_fuzzy_experiment import (
    author_list, idf_model, metrics, normalize, publication, read_cora, work_split,
)
from scripts.madi_fuzzy_grouping import (
    affirmative_score, augmented_groups, predicted_pairs, seed_groups, title_candidates,
)


def main(root):
    rows, labels = read_cora(root)
    development, heldout = work_split(rows, labels)
    vector = idf_model([normalize(rows[i]["title"]) for i in sorted(development)])
    for name, ids in (("full Cora", rows.keys()), ("held-out Cora", heldout)):
        records = [
            dict(id=i, title=rows[i]["title"], norm=normalize(rows[i]["title"]), doi="",
                 authors=author_list(rows[i]["author"]), publication=publication(rows[i]))
            for i in sorted(ids)
        ]
        positions = {p["id"]: index for index, p in enumerate(records)}
        gold = {(positions[a], positions[b]) for a, b in labels if a in positions and b in positions}
        seeds = seed_groups(records)
        base = predicted_pairs(seeds)
        edges, publication_only = {}, set()
        for (i, j), cosine in title_candidates(records, vector):
            result = affirmative_score(records[i], records[j], cosine)
            if result is not None:
                edges[i, j], uses_publication_only = result
                if uses_publication_only:
                    publication_only.add((i, j))
        trial = predicted_pairs(augmented_groups(records, seeds, edges))
        print(name, "records", len(records), "labelled matches", len(gold))
        print("Columns: TP FP FN precision recall F1")
        print("current main", metrics(base, gold))
        print("affirmative direct", metrics(edges, gold))
        print("affirmative hybrid", metrics(trial, gold))
        print("New links: labelled", len((trial-base) & gold),
              "unlabelled", len((trial-base) - gold),
              "publication-only", len((trial-base) & publication_only))
        for i, j in sorted((trial-base) - gold)[:3]:
            a, b = records[i], records[j]
            print("label disagreement", a["id"], b["id"], repr(a["title"]), repr(b["title"]))
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cora_root", type=Path)
    main(parser.parse_args().cora_root)
