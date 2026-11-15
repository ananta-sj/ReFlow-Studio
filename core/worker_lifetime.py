"""Stop an isolated model worker if its owning application process disappears."""
import os
import threading
import time

import psutil


def watch_parent():
    pid = os.environ.get('REFLOW_PARENT_PID')
    created = os.environ.get('REFLOW_PARENT_CREATED')
    if pid is None or created is None:
        return
    expected_pid, expected_created = int(pid), float(created)

    def monitor():
        while True:
            try:
                parent = psutil.Process(expected_pid)
                alive = parent.is_running() and abs(parent.create_time()-expected_created) < .01
            except psutil.NoSuchProcess:
                alive = False
            except psutil.AccessDenied:
                # A temporary inspection denial does not establish that the
                # known parent has exited.
                alive = True
            if not alive:
                for child in reversed(psutil.Process().children(recursive=True)):
                    try:
                        child.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                os._exit(1)
            time.sleep(1)

    threading.Thread(target=monitor, daemon=True).start()
