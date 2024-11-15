import argparse
from functools import reduce
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
from urllib.parse import urlparse, unquote_plus
from uuid import uuid4

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from svcutils import Notifier, Service, get_file_mtime, get_logger
from webutils import get_browser_driver


URLS = {}
BROWSER_ID = 'chrome'
RUN_DELTA = 2 * 3600
FORCE_RUN_DELTA = 4 * 3600
MIN_RUNTIME = 300
MAX_CPU_PERCENT = 10
NAME = os.path.splitext(os.path.basename(os.path.realpath(__file__)))[0]
WORK_PATH = os.path.join(os.path.expanduser('~'), f'.{NAME}')
ITEM_STORAGE_PATH = os.path.join(os.path.dirname(
    os.path.realpath(__file__)), 'items')
MAX_NOTIF_PER_URL = 4
MAX_NOTIF_BODY_SIZE = 500
STORAGE_RETENTION_DELTA = 7 * 24 * 3600

try:
    from user_settings import *
except ImportError:
    pass


def makedirs(x):
    if not os.path.exists(x):
        os.makedirs(x)


makedirs(WORK_PATH)
logger = get_logger(path=WORK_PATH, name=NAME)
logging.getLogger('selenium').setLevel(logging.INFO)
logging.getLogger('urllib3').setLevel(logging.INFO)


def to_json(x):
    return json.dumps(x, indent=4, sort_keys=True)


def clean_item(item):
    res = re.sub(r'\(.*?\)', '', item).strip()
    res = re.sub(r'\[.*?\]', '', res).strip()
    res = re.sub(r'[\(][^\(]*$|[\[][^\[]*$', '', res).strip()
    return res or item


class ItemStorage:
    base_path = ITEM_STORAGE_PATH

    def __init__(self, url):
        self.url = url
        self.path = os.path.join(self.base_path, self._get_dirname(url))
        self.items = {}
        for file, items in self._iterate_file_and_items():
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

    def _iterate_file_and_items(self):
        for file in glob(os.path.join(self.path, '*.json')):
            yield file, self._load_file_items(file)

    def _get_filename(self):
        return os.path.join(self.path, f'{uuid4().hex}.json')

    def save(self, all_items, new_items):
        all_item_keys = set(all_items.keys())
        for file, items in self._iterate_file_and_items():
            if items and not set(items.keys()) & all_item_keys:
                os.remove(file)
                logger.debug(f'removed old file {file}')

        makedirs(self.path)
        file = self._get_filename()
        with open(file, 'w') as fd:
            fd.write(to_json(new_items))


class URLIdGenerator:
    def __init__(self, urls):
        self.url_tokens = {u: self._get_tokens(u) for u in urls}

    def _get_tokens(self, url):
        parsed = urlparse(unquote_plus(url))
        words = re.findall(r'\b\w+\b', f'{parsed.path} {parsed.query}')
        return [r for r in words if len(r) > 1]

    def shorten(self, url):
        tokens = [v for k, v in self.url_tokens.items() if k != url]
        if tokens:
            tokens = set(reduce(lambda x, y: x + y, tokens))
            tokens = [r for r in self._get_tokens(url) if r not in tokens]
        else:
            tokens = []
        return ' '.join([urlparse(url).netloc] + tokens)


class Parser:
    id = None

    def __init__(self, headless=True):
        self.headless = headless

    def parse(self, url):
        raise NotImplementedError()

    def quit(self):
        pass


class BrowserParser(Parser):
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = get_browser_driver(browser_id=BROWSER_ID,
            headless=headless, page_load_strategy='none')

    def quit(self):
        self.driver.quit()


class X1337xParser(BrowserParser):
    id = '1337x'

    def _has_no_results(self):
        try:
            return bool(self.driver.find_element(By.XPATH,
                '//p[contains(text(), "No results were returned.")]'))
        except NoSuchElementException:
            return False

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
                if self._has_no_results():
                    logger.debug('no result')
                    return []
                time.sleep(poll_frequency)
        raise Exception('timeout')

    def _get_name(self, text):
        return text.splitlines()[0].strip()

    def parse(self, url):
        items = {}
        now_ts = int(time.time())
        for index, el in enumerate(self._wait_for_elements(url)):
            tds = el.find_elements(By.XPATH, './/td')
            items[self._get_name(tds[0].text)] = now_ts - index
        return items


class RutrackerParser(BrowserParser):
    id = 'rutracker'

    def _requires_login(self):
        try:
            return bool(self.driver.find_element(By.XPATH,
                '//input[@type="submit" and @name="login"]'))
        except NoSuchElementException:
            return False

    def _wait_for_elements(self, url, poll_frequency=.5, timeout=10):
        self.driver.get(url)
        end_ts = time.time() + timeout
        wait_for_login = False
        while time.time() < end_ts:
            try:
                els = self.driver.find_elements(By.XPATH,
                    '//div[contains(@class, "t-title")]')
                if not els:
                    raise NoSuchElementException()
                return els
            except NoSuchElementException:
                if self._requires_login() and not wait_for_login:
                    if self.headless:
                        raise Exception('requires login')
                    logger.info('waiting for user login...')
                    wait_for_login = True
                    end_ts += 120
                time.sleep(poll_frequency)
        raise Exception('timeout')

    def parse(self, url):
        items = {}
        now_ts = int(time.time())
        for index, el in enumerate(self._wait_for_elements(url)):
            link = el.find_element(By.XPATH, './/a')
            name = link.text.strip()
            items[name] = now_ts - index
        return items


class ItemCollector:
    def __init__(self, headless=True):
        self.headless = headless
        self.parsers = self._list_parsers()

    def _list_parsers(self):
        res = {}
        module = sys.modules[__name__]
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ == module.__name__ \
                    and issubclass(obj, Parser) and obj.id:
                res[obj.id] = obj
        return res

    def _notify_new_items(self, url_id, items):
        title = f'{NAME} {url_id}'
        names = [clean_item(n) for n, _ in sorted(items.items(),
            key=lambda x: x[1])]
        max_latest = MAX_NOTIF_PER_URL - 1
        latest_names = names[-max_latest:]
        older_names = names[:-max_latest]
        if older_names:
            body = ', '.join(reversed(older_names))
            if len(body) > MAX_NOTIF_BODY_SIZE:
                body = f'{body[:MAX_NOTIF_BODY_SIZE]}...'
            Notifier().send(title=title, body=f'{body}')
        for name in latest_names:
            Notifier().send(title=title, body=name)

    def _parse_url(self, parser, url, url_gen):
        item_storage = ItemStorage(url)
        all_items = parser.parse(url)
        logger.info(f'parsed {len(all_items)} items from {url}')
        new_items = {k: v for k, v in all_items.items()
            if k not in item_storage.items}
        if new_items:
            logger.info(f'new items from {url}:\n'
                f'{to_json(sorted(new_items.keys()))}')
            url_id = url_gen.shorten(url) or parser.id
            self._notify_new_items(url_id, new_items)
            item_storage.save(all_items, new_items)

    def _parse_urls(self, parser_id, urls):
        parser = self.parsers[parser_id](headless=self.headless)
        try:
            url_gen = URLIdGenerator(urls)
            for url in urls:
                logger.debug(f'parsing {url}')
                try:
                    self._parse_url(parser, url, url_gen)
                except Exception as exc:
                    logger.exception(f'failed to process {url}')
                    Notifier().send(title=f'{NAME} error',
                        body=f'failed to process {url}: {exc}')
        finally:
            parser.quit()

    def run(self):
        start_ts = time.time()
        all_urls = set()
        for parser_id, urls in URLS.items():
            all_urls.update(set(urls))
            try:
                self._parse_urls(parser_id, urls)
            except Exception:
                logger.exception(f'failed to process {parser_id}')
                Notifier().send(title=f'{NAME}',
                    body=f'failed to process {parser_id}')
        ItemStorage.cleanup(all_urls)
        logger.info(f'processed in {time.time() - start_ts:.02f} seconds')


def collect_items(headless=True):
    ItemCollector(headless=headless).run()


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--daemon', action='store_true')
    parser.add_argument('--task', action='store_true')
    parser.add_argument('--no-headless', action='store_true')
    return parser.parse_args()


def main():
    args = _parse_args()
    service = Service(
        target=collect_items,
        work_path=WORK_PATH,
        run_delta=RUN_DELTA,
        force_run_delta=FORCE_RUN_DELTA,
        min_runtime=MIN_RUNTIME,
        requires_online=True,
        max_cpu_percent=MAX_CPU_PERCENT,
        loop_delay=60,
    )
    if args.daemon:
        service.run()
    elif args.task:
        service.run_once()
    else:
        collect_items(headless=not args.no_headless)


if __name__ == '__main__':
    main()
