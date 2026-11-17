"""Offline MaDI-Bench grouping replay. Requires SciPy in the replay environment."""
import argparse
import csv
import itertools
import json
import re
from collections import defaultdict
from pathlib import Path

from scripts.cora_fuzzy_experiment import MATCHER, idf_model, normalize, read_cora, signals, work_split

FIELDS = {
    "dblp": ("publication_title", "author_list", "venue_name", "pub_year", "page_start", "page_finish"),
    "crossref": ("title_text", "contributor_names", "container_title", "issued_year", "page_first", "page_last"),
    "open_alex": ("display_title", "authors_list", "source_name", "year_published", "start_page", "end_page"),
}


def affirmative_evidence_view(paper):
    if paper["source"] != "dblp":
        return paper
    return dict(paper, authors=[
        re.sub(r"\s+[0-9]{4}$", "", name.strip()) if isinstance(name, str) else name
        for name in paper["authors"]
    ])


def publication_key(venue, year, first, last):
    if not isinstance(venue, str) or not all((year, first, last)):
        return None
    venue = normalize(venue)
    pages = tuple(str(page).strip().casefold() for page in (first, last))
    if not venue or not all(re.fullmatch(r"[a-z]?\d+(?:\.\d+)?", page) for page in pages):
        return None
    return venue, str(year), *pages


def affirmative_score(left, right, cosine):
    author, publication, conflict = signals(left, right)
    score = cosine + .10 * author
    if not conflict and (author or publication) and score >= .65 - 1e-12:
        return score, not author
    return None


def part_conflict(left_title, right_title):
    """Exploratory veto for conflicting explicit numbered parts."""
    def parts(title):
        return set(re.findall(r"\bpart\s+(\d+)\b", title, re.I))
    left, right = parts(left_title), parts(right_title)
    return bool(left and right and left.isdisjoint(right))


def title_candidates(records, vector):
    from scipy.sparse import csr_matrix

    words = defaultdict(list)
    for i, paper in enumerate(records):
        if paper["norm"] and not paper.get("doi"):
            words[paper["norm"]].append(i)
    vocab = {}
    indices, values, offsets = [], [], [0]
    for title in words:
        for gram, value in vector(title).items():
            indices.append(vocab.setdefault(gram, len(vocab)))
            values.append(value)
        offsets.append(len(values))
    matrix = csr_matrix((values, indices, offsets), shape=(len(words), len(vocab)))
    groups = list(words.values())
    transpose = matrix.T.tocsr()
    for start in range(0, len(groups), 128):
        similarities = (matrix[start:start + 128] @ transpose).tocoo()
        keep = (similarities.col >= start + similarities.row) & (similarities.data >= .55 - 1e-12)
        for r, col, cosine in zip(similarities.row[keep], similarities.col[keep], similarities.data[keep]):
            row = start + r
            if col == row:
                pairs = itertools.combinations(groups[row], 2)
            else:
                pairs = itertools.product(groups[row], groups[col])
            for i, j in pairs:
                yield (min(i, j), max(i, j)), min(cosine, 1.0)


def augmented_groups(records, seed_groups, scored_edges):
    """Preserve existing groups and require every new cross-group edge."""
    by_record = {i: group for group in seed_groups for i in group}
    for i, j in sorted(scored_edges, key=lambda pair: (-scored_edges[pair], pair)):
        a, b = by_record[i], by_record[j]
        if a is b or any(records[k].get("doi") for k in a | b):
            continue
        if all((min(x, y), max(x, y)) in scored_edges for x in a for y in b):
            merged = a | b
            by_record.update(dict.fromkeys(merged, merged))
    return {tuple(sorted(group)) for group in by_record.values()}


def seed_groups(records):
    # Exact titles are independent in the DOI-free benchmark. Run VMARO on
    # the full pool if identifiers are supplied so cross-title links survive.
    buckets = defaultdict(list)
    has_doi = any(p.get("doi") for p in records)
    for i, paper in enumerate(records):
        buckets["" if has_doi else paper["norm"]].append(dict(paper, replay_index=str(i)))
    return [
        {int(p["replay_index"]), *(int(d["replay_index"]) for d in p.get("duplicate_records", []))}
        for bucket in buckets.values() for p in MATCHER._deduplicate(bucket)
    ]


def predicted_pairs(groups):
    return {pair for group in groups for pair in itertools.combinations(sorted(group), 2)}


def report(name, pred, gold):
    tp = sum(gold[p] == 1 for p in pred & gold.keys())
    fp = sum(gold[p] == 0 for p in pred & gold.keys())
    fn = sum(gold.values()) - tp
    print(name, "TP FP FN", tp, fp, fn, "P R F1",
          tp / max(tp + fp, 1), tp / max(tp + fn, 1),
          2 * tp / max(2 * tp + fp + fn, 1),
          "unlabelled predictions", len(pred - gold.keys()))


def main(cora_root, madi_root):
    cora, labels = read_cora(cora_root)
    dev, _ = work_split(cora, labels)
    vector = idf_model([normalize(cora[i]["title"]) for i in sorted(dev)])
    for source, label_source in (("crossref", "crossref"), ("open_alex", "openalex")):
        with (madi_root / f"dblp_{label_source}_test.csv").open() as f:
            reader = csv.reader(f)
            next(reader)
            pairs = {(a, b): int(label) for a, b, label in reader}
        ids = {i for pair in pairs for i in pair}
        records = []
        for origin in ("dblp", source):
            with (madi_root / f"{origin}.jsonl").open() as f:
                for line in f:
                    row = json.loads(line)
                    if row["id"] in ids:
                        title, authors, venue, year, first, last = (row[k] for k in FIELDS[origin])
                        records.append(dict(id=row["id"], title=title or "", source=origin,
                                            norm=normalize(title or ""), doi="",
                                            authors=authors or [],
                                            publication=publication_key(venue, year, first, last)))
        indexes = {p["id"]: i for i, p in enumerate(records)}
        gold = {tuple(sorted((indexes[a], indexes[b]))): label for (a, b), label in pairs.items()}
        seeds = seed_groups(records)
        base = predicted_pairs(seeds)
        edges = {}
        gated_edges = {}
        publication_only = set()
        adapted = [affirmative_evidence_view(p) for p in records]
        soft_conflicts = set()
        checked = 0
        for (i, j), cosine in title_candidates(records, vector):
            checked += 1
            author, _, conflict = signals(records[i], records[j])
            score = cosine + .10 * author
            if conflict and score - .06 >= .65:
                soft_conflicts.add((i, j))
            if not conflict and score >= .65 - 1e-12:
                edges[i, j] = score
            gated_result = affirmative_score(adapted[i], adapted[j], cosine)
            if gated_result is not None:
                gated_edges[i, j], uses_publication_only = gated_result
                if uses_publication_only:
                    publication_only.add((i, j))
        trial = predicted_pairs(augmented_groups(records, seeds, edges))
        gated = predicted_pairs(augmented_groups(records, seeds, gated_edges))
        part_edges = {
            (i, j): score for (i, j), score in gated_edges.items()
            if not part_conflict(records[i]["title"], records[j]["title"])
        }
        with_part_veto = predicted_pairs(augmented_groups(records, seeds, part_edges))
        print(source, "records", len(records), "labelled pairs", len(gold),
              "fuzzy candidates", checked, "soft-pass conflict pairs", len(soft_conflicts),
              flush=True)
        report("current grouped", base, gold)
        report("hard-veto direct", set(edges), gold)
        report("hard-veto hybrid grouped", trial, gold)
        print("new grouped labelled matches", sum(gold.get(p) == 1 for p in trial-base),
              "new grouped labelled disagreements", sum(gold.get(p) == 0 for p in trial-base))
        report("affirmative evidence hybrid grouped", gated, gold)
        print("affirmative new labelled matches", sum(gold.get(p) == 1 for p in gated-base),
              "affirmative new labelled disagreements", sum(gold.get(p) == 0 for p in gated-base),
              "affirmative new unlabelled links", len((gated-base) - gold.keys()),
              "prior new unlabelled links", len((trial-base) - gold.keys()),
              "publication-only gated edges", len(publication_only),
              "publication-only new grouped links", len((gated-base) & publication_only))
        report("affirmative hybrid with numbered-part veto", with_part_veto, gold)
        print("part veto removed labelled matches", sum(gold.get(p) == 1 for p in gated-with_part_veto),
              "removed unlabelled links", len((gated-with_part_veto) - gold.keys()))
        if source == "open_alex":
            probe = tuple(sorted((indexes["dblp-01090"], indexes["open_alex-27173"])))
            print("known questionable pair prior/gated", probe in trial, probe in gated,
                  "adapted signals", signals(*(adapted[i] for i in probe)))
        for i, j in sorted((gated-base) - gold.keys())[:3]:
            print("new unlabelled example", records[i]["id"], records[j]["id"],
                  records[i]["title"], "|", records[j]["title"], "|",
                  (records[i]["authors"][:2], records[j]["authors"][:2]))
        print(flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cora_root", type=Path)
    parser.add_argument("madi_root", type=Path)
    args = parser.parse_args()
    main(args.cora_root, args.madi_root)
