import json
import os
import tempfile
import unittest
from itertools import permutations
from unittest.mock import Mock, patch

import requests

from utils.multi_api_fetcher import MultiAPIFetcher


def paper(title='A Research Paper', authors=None, doi='', source='arXiv', url='', **extra):
    return dict(title=title, authors=['Alice Smith', 'Bob Jones'] if authors is None else authors,
                doi=doi, source=source, url=url, abstract='Abstract', year=2023,
                citationCount=0, **extra)


class DeduplicationTests(unittest.TestCase):
    def setUp(self):
        self.fetcher = MultiAPIFetcher()

    def test_publication_preprint_both_orders_preserve_metadata(self):
        published = paper(doi='10.1234/abc', source='CrossRef', url='https://publisher.test/a')
        preprint = paper(title='A research paper!', url='https://arxiv.org/abs/123', extra_field='kept')
        for records in permutations([published, preprint]):
            with self.subTest(records=records):
                result = self.fetcher._deduplicate(records)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]['source'], 'CrossRef')
                self.assertEqual(result[0]['url'], published['url'])
                self.assertEqual(result[0]['extra_field'], 'kept')
                self.assertEqual(result[0]['duplicate_records'][0]['url'], preprint['url'])

    def test_author_format_variants_with_matching_title(self):
        for left, right in (
            ("A. Ehrenfeucht", "Ehrenfeucht, Andrzej"),
            ("Ehrenfeucht, A.", "Andrzej Ehrenfeucht"),
            ("Andrzej Ehrenfeucht", "EHRENFEUCHT,   ANDRZEJ"),
            ("Émilie O’Neil", "O'Neil, E\u0301milie"),
            ("Alice B. Smith", "Smith, Alice Beth"),
        ):
            publication = paper(authors=[left], doi="10.1234/a", url="publication")
            preprint = paper(authors=[right], url="preprint")
            for records in permutations([publication, preprint]):
                with self.subTest(left=left, right=right):
                    merged, = self.fetcher._deduplicate(records)
                    self.assertEqual(merged["url"], "publication")
                    self.assertEqual(merged["duplicate_records"][0]["authors"], [right])
                    self.assertEqual(merged["duplicate_records"][0]["url"], "preprint")

    def test_author_conflicts_and_ambiguous_names(self):
        for left, right in (
            (["Andrzej Ehrenfeucht"], ["Adam Ehrenfeucht"]),
            (["A. Ehrenfeucht"], ["Ehrenfeucht, A."]),
            (["Ehrenfeucht"], ["Ehrenfeucht"]),
            (["Alice B. Smith"], ["Alice C. Smith"]),
            (["Alice Smith"], ["Alice Smith, Bob Jones, Carol Doe"]),
            (["Alice Smith"], [None, "Alice Smith"]),
            (["Alice Smith"], "Alice Smith"),
            (["Alice Smith"], []),
        ):
            for records in permutations([paper(authors=left), paper(authors=right)]):
                with self.subTest(left=left, right=right):
                    self.assertEqual(len(self.fetcher._deduplicate(records)), 2)

    def test_initial_does_not_bridge_conflicting_full_names(self):
        a = paper(authors=["Andrzej Ehrenfeucht"])
        b = paper(authors=["Adam Ehrenfeucht"])
        initial = paper(authors=["Ehrenfeucht, A."])
        for order in permutations([a, b, initial]):
            self.assertEqual(len(self.fetcher._deduplicate(order)), 3)

    def test_compatible_author_format_cannot_override_distinct_dois(self):
        a = paper(authors=["Andrzej Ehrenfeucht"], doi="10.1234/a")
        b = paper(authors=["Ehrenfeucht, A."], doi="10.1234/b")
        for order in permutations([a, b]):
            self.assertEqual(len(self.fetcher._deduplicate(order)), 2)

    def test_cora_observed_middle_name_and_multi_initial_patterns(self):
        for left, right, expected in (
            ("Ronald L. Rivest", "R. Rivest", 1),
            ("David D. Lewis", "Lewis, D. D.", 1),
            ("M. J. Kearns", "Kearns, M. J.", 1),
            ("M. Kearns", "Kearns, M. J.", 2),
            ("Michael J. Kearns", "Michael R. Kearns", 2),
        ):
            for order in permutations([paper(authors=[left]), paper(authors=[right])]):
                with self.subTest(left=left, right=right):
                    self.assertEqual(len(self.fetcher._deduplicate(order)), expected)

    def test_omitted_middle_name_does_not_bridge_conflicting_middle_names(self):
        records = [paper(authors=[name]) for name in
                   ("Michael J. Kearns", "Michael Kearns", "Michael R. Kearns")]
        for order in permutations(records):
            self.assertEqual(len(self.fetcher._deduplicate(order)), 3)

    def test_ordered_coauthors_corroborate_abbreviated_first_author(self):
        a = paper(authors=["M. Kearns", "L. G. Valiant"], doi="10.1234/a", url="pub")
        b = paper(authors=["Kearns, M. J.", "Valiant, Leslie G."], url="preprint")
        for order in permutations([a, b]):
            merged, = self.fetcher._deduplicate(order)
            self.assertEqual(merged["duplicate_records"][0]["url"], "preprint")

        for other in (
            dict(b, doi="10.1234/b"),
            dict(b, title="A Different Paper"),
            dict(b, authors=["Kearns, M. J.", "Valiant, Robert G."]),
            dict(b, authors=["Kearns, M. J.", None]),
            dict(b, authors=["Valiant, Leslie G.", "Kearns, M. J."]),
            dict(b, authors=["Kearns, M. J."]),
        ):
            for order in permutations([a, other]):
                self.assertEqual(len(self.fetcher._deduplicate(order)), 2)

    def test_coauthor_evidence_cannot_bridge_conflicting_names(self):
        records = [paper(authors=[name, "L. Valiant"]) for name in
                   ("Michael J. Kearns", "M. Kearns", "Matthew Kearns")]
        for order in permutations(records):
            self.assertEqual(len(self.fetcher._deduplicate(order)), 3)

    def test_full_name_in_group_corroborates_compatible_initials(self):
        full = paper(authors=["Robert E. Schapire"])
        longer = paper(authors=["Schapire, R. E."])
        shorter = paper(authors=["R. Schapire"])
        for order in permutations([full, longer, shorter]):
            self.assertEqual(len(self.fetcher._deduplicate(order)), 1)
        for order in permutations([longer, shorter]):
            self.assertEqual(len(self.fetcher._deduplicate(order)), 2)

    def test_full_name_cannot_corroborate_conflicting_initials(self):
        full = paper(authors=["Robert Schapire"])
        e = paper(authors=["R. E. Schapire"])
        a = paper(authors=["R. A. Schapire"])
        for order in permutations([full, e, a]):
            self.assertEqual(len(self.fetcher._deduplicate(order)), 2)

    def test_reordered_coauthors_require_unique_compatible_names(self):
        a = paper(authors=["N. Cesa-Bianchi", "Y. Freund", "D. Haussler"])
        b = paper(authors=["Cesa-Bianchi, N.", "Haussler, David", "Freund, Yoav"])
        for order in permutations([a, b]):
            self.assertEqual(len(self.fetcher._deduplicate(order)), 1)
        for other in (
            dict(b, authors=["Cesa-Bianchi, N.", "Haussler, Michael", "Freund, Yoav"]),
            dict(b, authors=["Haussler, David", "Cesa-Bianchi, N.", "Freund, Yoav"]),
            dict(b, title="A different title"),
        ):
            for order in permutations([a, other]):
                self.assertEqual(len(self.fetcher._deduplicate(order)), 2)

    def test_normalized_same_doi_is_strong_signal(self):
        a = paper(doi=' HTTPS://DX.DOI.ORG/10.1234/ABC ', authors=[])
        b = paper(title='', doi='doi:10.1234/abc', authors=[])
        for records in permutations([a, b]):
            self.assertEqual(len(self.fetcher._deduplicate(records)), 1)

    def test_conflicts_and_insufficient_evidence_are_retained(self):
        a = paper(doi='10.1234/a')
        others = [paper(authors=['Carol White']), paper(authors=[]),
                  paper(title='A Research Paper Extended'), paper(doi='10.1234/b'),
                  paper(doi={'bad': 'value'}), paper(title=None, authors=None)]
        for b in others:
            for records in permutations([a, b]):
                with self.subTest(other=b, records=records):
                    self.assertEqual(len(self.fetcher._deduplicate(records)), 2)

    def test_crossref_direction_and_provenance_in_both_orders(self):
        preprint = paper(doi="https://doi.org/10.1234/PRE", source="CrossRef", url="pre")
        publication = paper(title="Revised title", doi="10.1234/pub", source="CrossRef",
                            url="pub", crossref_type="journal-article")
        for claimant, other, relation in (
            (preprint, publication, "is-preprint-of"),
            (publication, preprint, "has-preprint"),
        ):
            claimed = dict(claimant, crossref_relation={
                relation: [{"id-type": "doi", "id": other["doi"]}]
            })
            for records in permutations([claimed, other]):
                merged, = self.fetcher._deduplicate(records)
                self.assertEqual((merged["doi"], merged["url"]), ("10.1234/pub", "pub"))
                self.assertEqual(merged["duplicate_records"][0]["doi"], preprint["doi"])
                self.assertEqual(merged["duplicate_records"][0]["url"], "pre")

    def test_ambiguous_and_conflicting_crossref_claims(self):
        def claim(doi, target, kind="is-preprint-of", **extra):
            return paper(doi=doi, source="CrossRef", crossref_relation={
                kind: [{"id-type": "doi", "id": target}]
            }, **extra)

        a, b, c = ("10.1234/a", "10.1234/b", "10.1234/c")
        for records, count in (
            ([claim(a, b), claim(b, a)], 2),
            ([claim(a, b), claim(b, c), paper(doi=c)], 3),
            ([claim(a, b), claim(b, c, "has-preprint")], 2),
            ([claim(a, b), paper(doi=b, source="CrossRef", crossref_type="posted-content")], 2),
            ([claim(a, b), paper(doi=b), paper(doi=c), paper()], 3),
        ):
            for order in permutations(records):
                with self.subTest(order=order):
                    self.assertEqual(len(self.fetcher._deduplicate(order)), count)

    def test_crossref_malformed_relationships_are_ignored(self):
        for relation in (None, [], {"is-preprint-of": {}}, {"is-preprint-of": [
            None, {"id-type": "url", "id": "10.1234/b"}, {"id-type": "doi", "id": []}
        ]}):
            a = paper(doi="10.1234/a", source="CrossRef", crossref_relation=relation)
            b = paper(doi="10.1234/b")
            self.assertEqual(len(self.fetcher._deduplicate([a, b])), 2)

    def test_crossref_normalization_preserves_relationship(self):
        response = Mock()
        response.json.return_value = {"message": {"items": [
            {"DOI": "10.1234/pre", "abstract": "description " * 10,
             "type": "posted-content", "relation": {"is-preprint-of": [
                 {"id-type": "doi", "id": "10.1234/pub"}
             ]}},
        ]}}
        with patch("utils.multi_api_fetcher.requests.get", return_value=response) as get:
            preprint, = self.fetcher._fetch_crossref("query")
            publication = paper(doi="10.1234/pub")
            self.assertEqual(len(self.fetcher._deduplicate([preprint, publication])), 1)
            get.assert_called_once()

    def test_fetch_all_retains_distinct_dois_when_crossref_times_out(self):
        a, b = paper(doi="10.1234/a"), paper(doi="10.1234/b")
        payload = {"core_topic": "topic", "domain": "biomedical"}
        with (tempfile.TemporaryDirectory() as tmp,
            patch("utils.multi_api_fetcher.requests.get", side_effect=requests.Timeout),
            patch.object(self.fetcher, "_fetch_pubmed", return_value=[a, b]),
        ):
            old = os.getcwd()
            try:
                os.chdir(tmp)
                result = self.fetcher.fetch_all(payload)
            finally:
                os.chdir(old)
        self.assertEqual(len(result), 2)

    def test_ambiguous_bridge_never_joins_distinct_dois(self):
        a = paper(doi='10.1234/a')
        b = paper(doi='10.1234/b')
        bridge = paper()
        for records in permutations([a, b, bridge]):
            self.assertEqual(len(self.fetcher._deduplicate(records)), 3)

    def test_author_chain_cannot_join_conflicting_records(self):
        a = paper(doi='10.1234/a', authors=['Alice Smith'])
        b = paper(doi='10.1234/a', authors=['Carol White'])
        bridge = paper(authors=['Alice Smith'])
        for records in permutations([a, b, bridge]):
            self.assertEqual(len(self.fetcher._deduplicate(records)), 2)

    def test_missing_fields_are_retained(self):
        records = [{}, {'title': None, 'doi': None, 'authors': None},
                   {'title': ['bad'], 'doi': 42, 'authors': 'Alice'}]
        self.assertEqual(len(self.fetcher._deduplicate(records)), 3)

    def test_fetch_all_deduplicates_before_ranking_and_cap(self):
        first = paper(doi='10.1234/a', source='CrossRef', url='publisher')
        duplicate = paper(url='preprint')
        other = paper(title='Other', doi='10.1234/b', authors=['Other Author'])
        payload = {'core_topic': 'topic', 'domain': 'cs_ai', 'keywords': [], 'query_variants': ['q']}
        def fetch(source, query, keywords):
            return source, [first, duplicate, other] if source == 'semantic_scholar' else []
        with tempfile.TemporaryDirectory() as tmp, patch.object(self.fetcher, '_fetch_source', side_effect=fetch):
            old = os.getcwd()
            try:
                os.chdir(tmp)
                result = self.fetcher.fetch_all(payload, max_papers=1)
                with open('cache/paper_pool.json') as f:
                    pool = json.load(f)
            finally:
                os.chdir(old)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(pool), 2)
        self.assertEqual(pool[0]['duplicate_records'][0]['url'], 'preprint')
        self.assertIn('_relevance_score', pool[0])


if __name__ == '__main__':
    unittest.main()
