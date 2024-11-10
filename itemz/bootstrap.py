import os

from svcutils import Bootstrapper


Bootstrapper(
    script_path=os.path.join(os.path.dirname(os.path.realpath(__file__)),
        'itemz.py'),
    linux_args=['--task'],
    windows_args=['--daemon'],
).run()
