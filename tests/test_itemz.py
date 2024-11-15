import os
from pprint import pprint
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
REPO_PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.join(REPO_PATH, 'itemz'))
import itemz
import user_settings
assert itemz.WORK_PATH == user_settings.WORK_PATH


class CleanItemTestCase(unittest.TestCase):
    def test_1(self):
        item = 'L.A. Noire: The Complete Edition (v2675.1 + All DLCs, MULTi6) [FitGirl Repack]'
        self.assertEqual(itemz.clean_item(item), 'L.A. Noire: The Complete Edition')

    def test_2(self):
        item = 'L.A. Noire: The Complete Edition (v2675.1 + All DLCs, MULTi6) [FitGirl...'
        self.assertEqual(itemz.clean_item(item), 'L.A. Noire: The Complete Edition')

    def test_3(self):
        item = 'L.A. Noire: The Complete Edition (v2675.1 + All DLCs, ...'
        self.assertEqual(itemz.clean_item(item), 'L.A. Noire: The Complete Edition')

    def test_4(self):
        item = 'L.A. Noire (The Complete Edition) (v2675.1 + All DLCs, ...'
        self.assertEqual(itemz.clean_item(item), 'L.A. Noire (The Complete Edition)')

    def test_5(self):
        item = 'L.A. Noire [X] (v2675.1 + All DLCs, MULTi6) [FitGirl Repack]'
        self.assertEqual(itemz.clean_item(item), 'L.A. Noire [X]')

    def test_6(self):
        item = '[X] L.A. Noire (v2675.1 + All DLCs, MULTi6) [FitGirl Repack]'
        self.assertEqual(itemz.clean_item(item), '[X] L.A. Noire')


class URLIdTestCase(unittest.TestCase):
    def test_1(self):
        urls = [
            ('https://1337x.to/user/FitGirl/',
                '1337x.to FitGirl'),
            ('https://1337x.to/user/DODI/',
                '1337x.to DODI'),
            ('https://1337x.to/user/KaOsKrew/',
                '1337x.to KaOsKrew'),
            ('https://1337x.to/sort-search/monster%20hunter%20repack/time/desc/1/',
                '1337x.to monster hunter'),
            ('https://1337x.to/sort-search/battlefield%20repack/time/desc/1/',
                '1337x.to battlefield'),
        ]
        url_gen = itemz.URLIdGenerator([r for r, _ in urls])
        res = [(r, url_gen.shorten(r)) for r, _ in urls]
        pprint(res)
        self.assertEqual(res, urls)

    def test_2(self):
        urls = [
            ('https://1337x.to/user/FitGirl/',
                '1337x.to user FitGirl'),
            ('https://1337x.to/sort-search/battlefield%20repack/time/desc/1/',
                '1337x.to sort search battlefield repack time desc'),
        ]
        url_gen = itemz.URLIdGenerator([r for r, _ in urls])
        res = [(r, url_gen.shorten(r)) for r, _ in urls]
        pprint(res)
        self.assertEqual(res, urls)

    def test_3(self):
        url = 'https://1337x.to/sort-search/monster%20hunter%20repack/time/desc/1/'
        url_gen = itemz.URLIdGenerator([url])
        self.assertEqual(url_gen.shorten(url), '1337x.to')
