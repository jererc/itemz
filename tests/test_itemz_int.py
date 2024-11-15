import logging
import os
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


class X1337xTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(user_settings.WORK_PATH)
        makedirs(user_settings.WORK_PATH)

    def test_no_result(self):
        itemz.URLS = {
            '1337x': [
                'https://1337x.to/search/sfsfsfsdfsd/1/',
            ],
        }
        itemz.collect_items()

    def test_1(self):
        itemz.URLS = {
            '1337x': [
                'https://1337x.to/user/FitGirl/',
                # 'https://1337x.to/user/DODI/',
                # 'https://1337x.to/sort-search/monster%20hunter%20repack/time/desc/1/',
                # 'https://1337x.to/sort-search/battlefield%20repack/time/desc/1/',
            ],
        }
        itemz.collect_items()


class RutrackerTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(user_settings.WORK_PATH)
        makedirs(user_settings.WORK_PATH)

    def test_1(self):
        itemz.URLS = {
            'rutracker': [
                'https://rutracker.org/forum/tracker.php?f=557',
            ],
        }
        itemz.collect_items()


class CollectorTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(user_settings.WORK_PATH)
        makedirs(user_settings.WORK_PATH)

    def test_1(self):
        itemz.URLS = {
            '1337x': [
                'https://1337x.to/user/FitGirl/',
            ],
            'rutracker': [
                'https://rutracker.org/forum/tracker.php?f=557',
            ],
        }
        itemz.collect_items()
