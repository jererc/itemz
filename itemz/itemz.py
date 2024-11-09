from glob import glob
import inspect
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import subprocess
import sys
import time
import urllib.parse


import psutil
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from browser import Browser


FEEDER_URLS = {}
BROWSER_ID = 'chrome'
MAX_LOG_FILE_SIZE = 1000 * 1024
RUN_DELTA = 4 * 3600
NAME = os.path.splitext(os.path.basename(os.path.realpath(__file__)))[0]
WORK_PATH = os.path.join(os.path.expanduser('~'), f'.{NAME}')
ITEM_HISTORY_PATH = os.path.join(os.path.dirname(
    os.path.realpath(__file__)), 'items')

try:
    from user_settings import *
except ImportError:
    pass


def makedirs(x):
    if not os.path.exists(x):
        os.makedirs(x)


def setup_logging(logger, path):
    logging.basicConfig(level=logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')
    if sys.stdout and not sys.stdout.isatty():
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(formatter)
        stdout_handler.setLevel(logging.DEBUG)
        logger.addHandler(stdout_handler)
    makedirs(path)
    file_handler = RotatingFileHandler(
        os.path.join(path, f'{NAME}.log'),
        mode='a', maxBytes=MAX_LOG_FILE_SIZE, backupCount=0,
        encoding='utf-8', delay=0)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)


logger = logging.getLogger(__name__)
makedirs(WORK_PATH)
setup_logging(logger, WORK_PATH)


def is_idle():
    res = psutil.cpu_times_percent(interval=1).idle > 95
    if not res:
        logger.warning('not idle')
    return res


def get_file_mtime(x):
    return os.stat(x).st_mtime


def to_json(x):
    return json.dumps(x, indent=4, sort_keys=True)


class RunFile:
    def __init__(self, file):
        self.file = file

    def get_ts(self, default=0):
        if not os.path.exists(self.file):
            return default
        return get_file_mtime(self.file)

    def touch(self):
        with open(self.file, 'w'):
            pass


class Notifier:
    def _send_nt(self, title, body, on_click=None):
        from win11toast import notify
        notify(title=title, body=body, on_click=on_click)

    def _send_posix(self, title, body, on_click=None):
        env = os.environ.copy()
        env['DISPLAY'] = ':0'
        env['DBUS_SESSION_BUS_ADDRESS'] = \
            f'unix:path=/run/user/{os.getuid()}/bus'
        subprocess.check_call(['notify-send', title, body], env=env)

    def send(self, *args, **kwargs):
        try:
            {
                'nt': self._send_nt,
                'posix': self._send_posix,
            }[os.name](*args, **kwargs)
        except Exception:
            logger.exception('failed to send notification')


class ItemHistory:
    def __init__(self, url):
        self.url = url
        self.path = os.path.join(ITEM_HISTORY_PATH, self._get_dirname(url))
        self.items = {}
        for file, items in self._iterate_files_items():
            if items:
                self.items.update(items)

    def _get_dirname(self, url):
        return urllib.parse.quote(url, safe='')

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
            if not set(items.keys()) & all_item_keys:
                os.remove(file)
                logger.debug(f'removed old file {file}')

        makedirs(self.path)
        file = os.path.join(self.path, f'{int(time.time() * 1000)}.json')
        with open(file, 'w') as fd:
            fd.write(to_json(new_items))


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
    run_file = RunFile(os.path.join(WORK_PATH, f'{NAME}.run'))

    def __init__(self):
        self.feeders = self._list_feeders()

    def _must_run(self):
        return time.time() > self.run_file.get_ts() + RUN_DELTA and is_idle()

    def _list_feeders(self):
        res = {}
        module = sys.modules[__name__]
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ == module.__name__ \
                    and issubclass(obj, Browser) and obj.id:
                res[obj.id] = obj
        return res

    def _notify_new_items(self, items):
        logger.debug(to_json(items))
        names = [n for n, _ in sorted(items.items(), key=lambda x: x[1])]
        for name in names[-10:]:
            Notifier().send(title=f'{NAME}', body=name)

    def _fetch_url_items(self, feeder, url):
        ih = ItemHistory(url)
        all_items = feeder.fetch(url)
        new_items = {k: v for k, v in all_items.items() if k not in ih.items}
        if new_items:
            self._notify_new_items(new_items)
            ih.save(all_items, new_items)

    def _fetch_items(self, feeder_id, urls):
        feeder = self.feeders[feeder_id]()
        try:
            for url in urls:
                try:
                    self._fetch_url_items(feeder, url)
                except Exception:
                    logger.exception(f'failed to process {url}')
                    Notifier().send(title=f'{NAME}',
                        body=f'failed to process {url}')
        finally:
            feeder.quit()

    def run(self):
        if not self._must_run():
            return
        try:
            for feeder_id, urls in FEEDER_URLS.items():
                try:
                    self._fetch_items(feeder_id, urls)
                except Exception:
                    logger.exception(f'failed to process {feeder_id}')
                    Notifier().send(title=f'{NAME}',
                        body=f'failed to process {feeder_id}')
        finally:
            self.run_file.touch()


def main():
    ItemFetcher().run()


if __name__ == '__main__':
    main()
