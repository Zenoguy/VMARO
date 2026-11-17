"""Exploratory Cora replay.

Run PYTHONPATH=. python scripts/cora_replay.py /path/to/cora-files
from the repository root. Input is the pipe-delimited pyJedAI distribution.
All implementations receive the same rows in file order, without DOIs.
"""
import csv
import itertools
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

from utils.multi_api_fetcher import MultiAPIFetcher


def first_author(raw):
    field = re.sub(r"(?<=[^\W\d_]\.)(?=[^\W\d_]\.)", " ", raw).strip(" ,;.:")
    if not field:
        return "", "missing"
    first = re.split(r"\s*(?:;|\s+and\s+|&)\s*", field, maxsplit=1)[0].strip(" ,.:")
    chunks = [part.strip() for part in first.split(",")]
    tokens = chunks[0].split()
    initial = lambda word: bool(re.fullmatch(r"[^\W\d_]\.?", word))
    if len(tokens) == 1:
        if (len(chunks) > 1 and chunks[1].split()
                and (all(map(initial, chunks[1].split()))
                     or (";" in field and len(chunks) == 2
                         and re.fullmatch(r"[^\W\d_]{2,}", chunks[1])))):
            return ", ".join(chunks[:2]), "comma surname-first"
        return "", "ambiguous"
    if tokens[0]=="et" or "et al" in chunks[0] or not all(
        re.fullmatch(r"[^\W\d_]+(?:[-'][^\W\d_]+)*\.?", t) for t in tokens
    ):
        return "", "ambiguous"
    if all(map(initial, tokens[1:])) and not initial(tokens[0]):
        return f"{tokens[0]}, {' '.join(tokens[1:])}", "surname then initials"
    if initial(tokens[-1]):
        return "", "ambiguous"
    return chunks[0], "given-first"


def author_list(raw):
    """Keep the vetted first-author parse if any later entry is unclear."""
    first, _ = first_author(raw)
    if not first:
        return []
    names = []
    for segment in re.split(r";|\s+and\s+|&", raw):
        chunks = [chunk.strip() for chunk in segment.strip(" ,;:").split(",")]
        while chunks and chunks[0]:
            candidate, status = first_author(", ".join(chunks))
            if not candidate:
                return [first]
            names.append(candidate)
            del chunks[:2 if status == "comma surname-first" else 1]
    if not names or MultiAPIFetcher._author_parts(names[0]) != MultiAPIFetcher._author_parts(first):
        return [first]
    return names


def main(root):
    root = Path(root)
    rows = list(csv.DictReader((root / "cora.csv").open(), delimiter="|"))
    labels = {tuple(sorted(map(int, row))) for row in
              csv.reader((root / "cora_gt.csv").open(), delimiter="|")}
    records, audits, citations = {}, {}, {}
    for row in rows:
        i = int(row["Entity Id"])
        name, status = first_author(row["author"])
        records[i] = dict(id=i, title=row["title"], authors=author_list(row["author"]), doi="")
        audits[i] = status, row["author"], name
        citations[i] = (row["venue"], row["year"])
    print("Multi-author rosters:", sum(len(p["authors"]) > 1 for p in records.values()))
    print("Parsing:", Counter(a[0] for a in audits.values()))
    for status in sorted({a[0] for a in audits.values()}):
        sample = [(i, *a[1:]) for i, a in audits.items() if a[0] == status]
        print(status, random.Random(42).sample(sample, min(6, len(sample))))

    def at(rev):
        namespace = {}
        code = subprocess.check_output(["git", "show", f"{rev}:utils/multi_api_fetcher.py"])
        exec(code, namespace)
        return namespace["MultiAPIFetcher"]()

    def pairs(groups):
        return {tuple(sorted(pair)) for group in groups
                for pair in itertools.combinations(group, 2)}

    original, before = at("57cdb31"), at("8e0dc90")
    normalize = lambda title: " ".join(re.sub(r"[^\w\s]", "", title.lower()).split())
    buckets = defaultdict(list)
    for i, p in records.items():
        if p["title"].strip():
            buckets[normalize(p["title"])].append(i)
    winners = {p["id"] for p in original._deduplicate(list(records.values()))}
    assert winners == {group[0] for group in buckets.values()}
    old_pairs = pairs(buckets.values())

    def predict(matcher):
        return pairs([p["id"], *(d["id"] for d in p.get("duplicate_records", []))]
                     for p in matcher._deduplicate(list(records.values())))

    class OrderedRosters(MultiAPIFetcher):
        def _align_rosters(self, left, right):
            return zip(left, right)

    class OriginalGrouping(MultiAPIFetcher):
        def _roster_priority(self, papers, title_of):
            return {}

    class PriorMatcher(OrderedRosters, OriginalGrouping):
        pass

    class CoauthorOnly(PriorMatcher):
        def _abbreviations_share_full_name(self, left, right, anchors):
            return False

    class FirstAuthorOnly(CoauthorOnly):
        def _coauthors_support_match(self, left, right):
            return False

    before_pairs = predict(before)
    coauthor_pairs = predict(CoauthorOnly())
    first_author_pairs = predict(FirstAuthorOnly())
    prior_pairs = predict(PriorMatcher())
    after_pairs = predict(MultiAPIFetcher())
    for name, predictions in (
        ("original", old_pairs),
        ("main", before_pairs),
        ("first-author fix", first_author_pairs),
        ("parser fix only", coauthor_pairs),
        ("previous corroboration matcher", prior_pairs),
        ("roster priority only", predict(OrderedRosters())),
        ("reordered coauthors only", predict(OriginalGrouping())),
        ("both changes", after_pairs),
    ):
        tp, fp, fn = len(predictions & labels), len(predictions - labels), len(labels - predictions)
        print(name, tp, fp, fn, tp/(tp+fp), tp/(tp+fn), 2*tp/(2*tp+fp+fn))
    misses = defaultdict(list)
    for i, j in sorted((labels & old_pairs) - before_pairs):
        a, b = [before._first_author_parts(records[k]) for k in (i, j)]
        if not a or not b:
            reason = "missing/unparsed"
        elif a[0] != b[0]:
            reason = "different parsed surname"
        elif len(a[1]) != len(b[1]):
            reason = "different given token counts"
        elif not any(len(w) > 1 for w in a[1]+b[1]):
            reason = "both initial-only"
        elif not before._authors_match(a, b):
            reason = "incompatible given names"
        else:
            reason = "grouping"
        misses[reason].append((i, j))
    title_misses = labels - old_pairs
    print("Labelled pairs excluded by original title gate:", len(title_misses))
    for i, j in random.Random(42).sample(sorted(title_misses), min(3, len(title_misses))):
        print(i, j, records[i]["title"], records[j]["title"])
    for reason, entries in sorted(misses.items()):
        print(reason, len(entries))
        for i, j in random.Random(42).sample(entries, min(5, len(entries))):
            print(i, j, audits[i], audits[j], records[i]["title"])
    for name, entries in (
        ("new labelled links", (after_pairs - prior_pairs) & labels),
        ("lost labelled links", (prior_pairs - after_pairs) & labels),
        ("new unlabelled links", (after_pairs - prior_pairs) - labels),
    ):
        print(name, len(entries))
        for i, j in random.Random(42).sample(sorted(entries), min(5, len(entries))):
            print(i, j, audits[i], audits[j], records[i]["title"], citations[i], citations[j])


if __name__ == "__main__":
    main(sys.argv[1])
