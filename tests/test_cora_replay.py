import unittest

from scripts.cora_replay import author_list, first_author


class CoraAdapterTests(unittest.TestCase):
    def test_citation_format_fixtures(self):
        cases = {
            "m.j. kearns and u.v. vazirani.": "m. j. kearns",
            "kearns, m. j., & vazirani, u. v.": "kearns, m. j",
            "drucker, harris; schapire, robert; and simard": "drucker, harris",
            "avrim blum, merrick furst, and michael kearns": "avrim blum",
            "freund y., schapire r.e.:": "freund, y.",
            "drucker, schapire and simard,": "",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(first_author(raw)[0], expected)

    def test_ordered_roster_formats(self):
        self.assertEqual(author_list("kearns, m. j., & vazirani, u. v."),
                         ["kearns, m. j", "vazirani, u. v"])
        self.assertEqual(author_list("m.j. kearns and u.v. vazirani."),
                         ["m. j. kearns", "u. v. vazirani"])
        self.assertEqual(author_list("m. kearns and others"), ["m. kearns"])

    def test_terminal_compact_initials_preserve_coauthor(self):
        self.assertEqual(author_list("kearns, m. & valiant, l.g."),
                         ["kearns, m", "valiant, l. g"])
