import logging
import os
from pprint import pprint
import shutil
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
REPO_PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.join(REPO_PATH, 'itemz'))
import itemz
import user_settings
assert itemz.WORK_PATH == user_settings.WORK_PATH


itemz.logger.setLevel(logging.DEBUG)


def remove_path(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


def makedirs(path):
    if not os.path.exists(path):
        os.makedirs(path)


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


class BatchTestCase(unittest.TestCase):
    def test_1(self):
        items = list(range(7))
        res = itemz.split_into_batches(items, 3)
        self.assertEqual(res, [[0, 1, 2], [3, 4, 5], [6]])


class ItemzTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(user_settings.WORK_PATH)
        makedirs(user_settings.WORK_PATH)

    def test_1(self):
        itemz.FEEDER_URLS = {
            '1337x.to': [
                'https://1337x.to/user/FitGirl/',
                # 'https://1337x.to/user/DODI/',
                # 'https://1337x.to/user/KaOsKrew/',
                'https://1337x.to/sort-search/monster%20hunter%20repack/time/desc/1/',
                # 'https://1337x.to/sort-search/battlefield%20repack/time/desc/1/',
                # 'https://1337x.to/sort-search/call%20of%20duty%20repack/time/desc/1/',
            ],
        }
        itemz.fetch_items()