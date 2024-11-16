import argparse
import os

from svcutils.service import Service
from test_svc.test_svc import WORK_PATH, main as target


CONFIG_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)),
    'user_settings.py')


parser = argparse.ArgumentParser()
parser.add_argument('--config-file', '-c', default=CONFIG_FILE)
args = parser.parse_args()
Service(
    target=target,
    args=(args.config_file,),
    work_path=WORK_PATH,
    run_delta=10,
).run_once()
