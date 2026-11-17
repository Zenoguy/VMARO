import json
import os
import tempfile
import unittest
from itertools import permutations
from unittest.mock import patch

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
