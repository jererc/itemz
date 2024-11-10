import argparse
from glob import glob
import hashlib
import inspect
import json
import logging
import os
import re
import shutil
import sys
import time

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from browser import Browser
from service import Daemon, Notifier, Task, get_file_mtime, setup_logging


FEEDER_URLS = {}
BROWSER_ID = 'chrome'
RUN_DELTA = 2 * 3600
FORCE_RUN_DELTA = 4 * 3600
NAME = os.path.splitext(os.path.basename(os.path.realpath(__file__)))[0]
WORK_PATH = os.path.join(os.path.expanduser('~'), f'.{NAME}')
ITEM_STORAGE_PATH = os.path.join(os.path.dirname(
    os.path.realpath(__file__)), 'items')
NOTIF_BATCH_SIZE = 5
STORAGE_RETENTION_DELTA = 7 * 24 * 3600

try:
    from user_settings import *
except ImportError:
    pass


def makedirs(x):
    if not os.path.exists(x):
        os.makedirs(x)


logger = logging.getLogger(__name__)
makedirs(WORK_PATH)
setup_logging(logger, path=WORK_PATH, name=NAME)

logging.getLogger('selenium').setLevel(logging.INFO)
logging.getLogger('urllib3').setLevel(logging.INFO)


def to_json(x):
    return json.dumps(x, indent=4, sort_keys=True)


def clean_item(item):
    res = re.sub(r'[\(][^\(]*$|[\[][^\[]*$', '', item).strip()
    return res or item


def split_into_batches(items, batch_size):
    return [items[i:i + batch_size]
        for i in range(0, len(items), batch_size)]


class ItemStorage:
    base_path = ITEM_STORAGE_PATH

    def __init__(self, url):
        self.url = url
        self.path = os.path.join(self.base_path, self._get_dirname(url))
        self.items = {}
        for file, items in self._iterate_files_items():
            if items:
                self.items.update(items)

    @classmethod
    def _get_dirname(cls, url):
        return hashlib.md5(url.encode('utf-8')).hexdigest()

    @classmethod
    def cleanup(cls, all_urls):
        dirnames = {cls._get_dirname(r) for r in all_urls}
        min_ts = time.time() - STORAGE_RETENTION_DELTA
        for path in glob(os.path.join(cls.base_path, '*')):
            if os.path.basename(path) in dirnames:
                continue
            mtimes = [get_file_mtime(r)
                for r in glob(os.path.join(path, '*'))]
            if not mtimes or max(mtimes) < min_ts:
                shutil.rmtree(path)
                logger.info(f'removed old storage path {path}')

    def _load_file_items(self, file):
        try:
            with open(file) as fd:
                return json.load(fd)
        except Exception:
            logger.exception(f'failed to load file {file}')
            return None

    def _iterate_files_items(self):
        for file in glob(os.path.join(self.path, '*.json')):
            yield file, self._load_file_items(file)

    def save(self, all_items, new_items):
        all_item_keys = set(all_items.keys())
        for file, items in self._iterate_files_items():
            if items and not set(items.keys()) & all_item_keys:
                os.remove(file)
                logger.debug(f'removed old file {file}')

        makedirs(self.path)
        file = os.path.join(self.path, f'{int(time.time() * 1000)}.json')
        with open(file, 'w') as fd:
            fd.write(to_json(new_items))
        logger.info(f'created items file {file} for {self.url}')


class Https1337xto(Browser):
    id = '1337x.to'

    def __init__(self):
        super().__init__(browser_id=BROWSER_ID, headless=True,
            page_load_strategy='none')

    def _wait_for_elements(self, url, poll_frequency=.5, timeout=10):
        self.driver.get(url)
        end_ts = time.time() + timeout
        while time.time() < end_ts:
            try:
                els = self.driver.find_elements(By.XPATH, '//table/tbody/tr')
                if not els:
                    raise NoSuchElementException()
                return els
            except NoSuchElementException:
                time.sleep(poll_frequency)
        raise Exception('timeout')

    def _get_name(self, text):
        return text.splitlines()[0].strip()

    def fetch(self, url):
        items = {}
        now_ts = int(time.time())
        for index, el in enumerate(self._wait_for_elements(url)):
            tds = el.find_elements(By.XPATH, './/td')
            items[self._get_name(tds[0].text)] = now_ts - index
        return items


class ItemFetcher:
    def __init__(self):
        self.feeders = self._list_feeders()

    def _list_feeders(self):
        res = {}
        module = sys.modules[__name__]
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ == module.__name__ \
                    and issubclass(obj, Browser) and obj.id:
                res[obj.id] = obj
        return res

    def _notify_new_items(self, feeder, items):
        title = f'{NAME} @{feeder.id}'
        names = [clean_item(n) for n, _ in sorted(items.items(),
            key=lambda x: x[1])]
        for batch in split_into_batches(names, NOTIF_BATCH_SIZE):
            Notifier().send(title=title, body=f'{", ".join(batch)}')

    def _fetch_url_items(self, feeder, url):
        ih = ItemStorage(url)
        all_items = feeder.fetch(url)
        new_items = {k: v for k, v in all_items.items() if k not in ih.items}
        if new_items:
            self._notify_new_items(feeder, new_items)
            ih.save(all_items, new_items)

    def _fetch_items(self, feeder_id, urls):
        feeder = self.feeders[feeder_id]()
        try:
            for url in urls:
                logger.debug(f'fetching items from {url}')
                try:
                    self._fetch_url_items(feeder, url)
                except Exception:
                    logger.exception(f'failed to process {url}')
                    Notifier().send(title=f'{NAME}',
                        body=f'failed to process {url}')
        finally:
            feeder.quit()

    def run(self):
        start_ts = time.time()
        all_urls = set()
        for feeder_id, urls in FEEDER_URLS.items():
            all_urls.update(set(urls))
            try:
                self._fetch_items(feeder_id, urls)
            except Exception:
                logger.exception(f'failed to process {feeder_id}')
                Notifier().send(title=f'{NAME}',
                    body=f'failed to process {feeder_id}')
        ItemStorage.cleanup(all_urls)
        logger.info(f'processed in {time.time() - start_ts:.02f} seconds')


def fetch_items():
    ItemFetcher().run()


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--daemon', action='store_true')
    parser.add_argument('--task', action='store_true')
    return parser.parse_args()


def main():
    args = _parse_args()
    if args.daemon:
        Daemon(
            callable=fetch_items,
            work_path=WORK_PATH,
            run_delta=RUN_DELTA,
            force_run_delta=FORCE_RUN_DELTA,
            run_file_path=os.path.join(WORK_PATH, 'daemon.run'),
            loop_delay=60,
        ).run()
    elif args.task:
        Task(
            callable=fetch_items,
            work_path=WORK_PATH,
            run_delta=RUN_DELTA,
            force_run_delta=FORCE_RUN_DELTA,
            run_file_path=os.path.join(WORK_PATH, 'task.run'),
        ).run()
    else:
        fetch_items()


if __name__ == '__main__':
    main()
