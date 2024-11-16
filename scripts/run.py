import argparse
import os

from svcutils.service import Service, load_config
from itemz.itemz import WORK_PATH, collect_items

CWD = os.path.dirname(os.path.realpath(__file__))
CONFIG = load_config(os.path.join(CWD, 'user_settings.py'))
RUN_DELTA = 2 * 3600
FORCE_RUN_DELTA = 4 * 3600
MIN_RUNTIME = 300
MAX_CPU_PERCENT = 10

if not CONFIG.ITEM_STORAGE_PATH:
    CONFIG.ITEM_STORAGE_PATH = os.path.join(CWD, 'items')

Service(
    target=collect_items,
    args=(CONFIG,),
    work_path=WORK_PATH,
    run_delta=RUN_DELTA,
    force_run_delta=FORCE_RUN_DELTA,
    min_runtime=MIN_RUNTIME,
    requires_online=True,
    max_cpu_percent=MAX_CPU_PERCENT,
).run_once()
