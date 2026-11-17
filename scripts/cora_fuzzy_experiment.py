"""Offline experiment. Run with PYTHONPATH=. python scripts/cora_fuzzy_experiment.py work/cora-input."""
import csv
import itertools
import math
import random
import re
import sys
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

from scripts.cora_replay import author_list
from utils.multi_api_fetcher import MultiAPIFetcher

MATCHER = MultiAPIFetcher()


def normalize(value):
    return " ".join(re.sub(r"[^\w\s]", "", value.casefold()).split())


def read_cora(path):
    with (path / "cora.csv").open() as f:
        rows = {int(r["Entity Id"]): r for r in csv.DictReader(f, delimiter="|")}
    with (path / "cora_gt.csv").open() as f:
        labels = {tuple(sorted(map(int, row))) for row in csv.reader(f, delimiter="|")}
    return rows, labels


def work_split(rows, labels):
    groups = {i: {i} for i in rows}
    for i, j in sorted(labels):
        if groups[i] is not groups[j]:
            merged = groups[i] | groups[j]
            groups.update(dict.fromkeys(merged, merged))
    works = sorted({tuple(sorted(group)) for group in groups.values()})
    random.Random(42).shuffle(works)
    cut = len(works) // 2
    return [{i for work in side for i in work} for side in (works[:cut], works[cut:])]


def grams(value):
    return Counter(value[i:i+n] for n in (3, 4, 5) for i in range(len(value)-n+1))


def idf_model(titles):
    frequency = Counter()
    for title in titles:
        frequency.update(grams(title).keys())
    size = len(titles)

    @lru_cache(maxsize=None)
    def vector(title):
        weights = {g: count * (1 + math.log((size+1)/(frequency[g]+1)))
                   for g, count in grams(title).items()}
        length = math.sqrt(sum(w*w for w in weights.values()))
        return {g: w/length for g, w in weights.items()} if length else {}
    return vector


def publication(row):
    venue = " ".join(re.findall(r"\w+", row["venue"].casefold()))
    year = re.findall(r"\b(?:19|20)\d\d\b", row["year"])
    pages = re.fullmatch(r"\s*(?:pp?\.?|pages?)?\s*\(?\s*(\d+(?:\.\d+)?)"
                         r"\s*[-–—]+\s*(\d+(?:\.\d+)?)\s*\)?[.,]?\s*",
                         row["pages"], re.I)
    return (venue, year[0], pages.groups()) if venue and len(year) == 1 and pages else None


def signals(a, b):
    left, right = MATCHER._first_author_parts(a), MATCHER._first_author_parts(b)
    conflict = False
    if left and right:
        conflict = left[0] != right[0] or any(
            x != y and (min(len(x), len(y)) > 1 or x[0] != y[0])
            for x, y in zip(left[1], right[1])
        )
    authors = MATCHER._authors_match(left, right) or MATCHER._coauthors_support_match(a, b)
    pub = bool(a["publication"] and a["publication"] == b["publication"])
    return authors, pub, conflict


def candidates(ids, papers, vector):
    index = defaultdict(list)
    result = []
    for i in sorted(ids):
        similarity = defaultdict(float)
        weights = vector(papers[i]["norm"])
        for gram, weight in weights.items():
            for j, other_weight in index[gram]:
                similarity[j] += weight * other_weight
            index[gram].append((i, weight))
        for j, score in similarity.items():
            if score >= 0.5:
                result.append(((j, i), min(score, 1.0), *signals(papers[j], papers[i])))
    return result


def rank(items, params):
    threshold, author_bonus, publication_bonus, conflict_penalty = params
    accepted = {}
    for pair, cosine, author, pub, conflict in items:
        if conflict and conflict_penalty == math.inf:
            continue
        score = cosine + author_bonus * author + publication_bonus * pub
        if conflict:
            score -= conflict_penalty
        if score >= threshold:
            accepted[pair] = score
    return accepted


def complete_link(edges):
    """Only join groups when every cross-group pair was accepted."""
    groups = {}
    for i, j in sorted(edges, key=lambda pair: (-edges[pair], pair)):
        a, b = groups.get(i, {i}), groups.get(j, {j})
        if a is b:
            continue
        if all(tuple(sorted((x, y))) in edges for x in a for y in b):
            merged = a | b
            groups.update(dict.fromkeys(merged, merged))
    return {pair for group in {tuple(sorted(g)) for g in groups.values()}
            for pair in itertools.combinations(group, 2)}


def metrics(pred, gold):
    pred = set(pred)
    tp, fp, fn = len(pred & gold), len(pred - gold), len(gold - pred)
    return tp, fp, fn, tp/max(tp+fp,1), tp/max(tp+fn,1), 2*tp/max(2*tp+fp+fn,1)


def main(root):
    rows, labels = read_cora(Path(root))
    dev, test = work_split(rows, labels)
    papers = {i: dict(id=i, title=r["title"], doi="", norm=normalize(r["title"]),
                      authors=author_list(r["author"]), publication=publication(r))
              for i, r in rows.items()}
    vector = idf_model([papers[i]["norm"] for i in sorted(dev)])
    dev_items = candidates(dev, papers, vector)
    dev_gold = {pair for pair in labels if set(pair) <= dev}
    thresholds = [n / 100 for n in range(65, 100, 5)]
    title_configs = [(t, 0, 0, 0) for t in thresholds]
    evidence_configs = [(t,a,p,c) for t,a,p,c in itertools.product(
        thresholds, (0, .05, .10), (0, .05), (.06, .12, math.inf))]
    best_title = max(title_configs, key=lambda p: metrics(rank(dev_items,p),dev_gold)[-1])
    best_evidence = max(evidence_configs, key=lambda p: metrics(rank(dev_items,p),dev_gold)[-1])
    print("frozen params (threshold, author bonus, publication bonus, conflict penalty)",
          best_title, best_evidence, flush=True)
    for name, ids, items in [("dev", dev, dev_items), ("held-out", test, candidates(test,papers,vector))]:
        gold = {pair for pair in labels if set(pair) <= ids}
        exact = {pair for pair in itertools.combinations(sorted(ids),2)
                 if papers[pair[0]]["norm"] and papers[pair[0]]["norm"]==papers[pair[1]]["norm"]}
        current = {tuple(sorted(pair))
                   for group in MATCHER._deduplicate([papers[i] for i in sorted(ids)])
                   for pair in itertools.combinations([group["id"], *(
                       d["id"] for d in group.get("duplicate_records", []))],2)}
        print(name,"records",len(ids),"labelled",len(gold),"fuzzy candidates",len(items))
        for label, pred in [("exact-title",exact),("fuzzy candidate floor 0.50",{p for p,*_ in items}),
                            ("current matcher",current),
                            ("TF–IDF 0.80",rank(items,(.80,0,0,0)))]:
            print(label, metrics(pred,gold))
        for label, params in [("tuned title only",best_title),("tuned evidence",best_evidence)]:
            edges = rank(items,params)
            print(label,"direct",metrics(edges,gold),"grouped",metrics(complete_link(edges),gold))


if __name__ == "__main__":
    main(sys.argv[1])
