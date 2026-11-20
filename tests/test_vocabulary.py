"""Offline regression checks: run python3 -m unittest discover -s tests -p test_vocabulary.py."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

import main


class VocabularyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.provenance, cls.validation = main.build(main.ROOT / 'data/raw')

    def test_complete_and_unique(self):
        self.assertEqual(len(self.rows), 5965)
        self.assertEqual(len({r['ID'] for r in self.rows}), 5965)
        self.assertEqual(self.validation['zh']['matched'], 5965)
        self.assertEqual(self.validation['en']['matched'], 5965)

    def test_homographs_preserved(self):
        furniture = [r for r in self.rows if r['Korean'] == '가구']
        self.assertEqual({r['Hanja'] for r in furniture}, {'家口', '家具'})
        self.assertEqual(len({r['ID'] for r in furniture}), 2)
        self.assertEqual(len([r for r in self.rows if r['Korean'] == '가다']), 2)

    def test_origin_not_guessed(self):
        self.assertEqual(main.origin('')[1], '')
        self.assertEqual(main.origin('價格')[:2], ('價格', '汉字词'))
        self.assertEqual(main.origin('高速bus')[:2], ('高速', '混合词'))
        self.assertEqual(main.origin('可能-')[:2], ('可能', '混合词'))
        self.assertEqual(main.origin('&프restaurant')[1], '外来词')
        self.assertEqual(main.origin('&#29518;學金')[0], '獎學金')
        self.assertEqual(main.origin('沈&#40665;')[0], '沈黙')  # Preserve source variant, do not silently rewrite.
        self.assertTrue(all(not r['Pronunciation'] for r in self.rows))

    def test_official_only(self):
        rows, _, _ = main.build(main.ROOT / 'data/raw', official_only=True)
        self.assertEqual([r['ID'] for r in rows], [r['ID'] for r in self.rows])
        self.assertTrue(all(not r['Chinese'] and not r['English'] and not r['Example'] for r in rows))


if __name__ == '__main__':
    unittest.main()
