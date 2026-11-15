"""Rebuild edited interface files using the existing source workspace tools."""
import os
from pathlib import Path
import shutil
import subprocess
import threading


class InterfaceWatcher:
    def __init__(self, root):
        self.process = None
        self.root = Path(root)
        self.vite = self.root/'frontend/node_modules/vite/bin/vite.js'
        self.node = shutil.which('node')
        self.stopped = threading.Event()
        self.thread = None
        if not self.node or not self.vite.is_file() or not (self.root/'frontend/src').is_dir():
            return
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stamp(self):
        frontend = self.root/'frontend'
        paths = [*frontend.joinpath('src').rglob('*'), frontend/'index.html',
                 frontend/'vite.config.ts', frontend/'package.json']
        return [(str(path), path.stat().st_mtime_ns, path.stat().st_size)
                for path in sorted(paths) if path.is_file()]

    def run(self):
        previous = []
        try:
            previous = self.stamp()
        except OSError:
            pass
        while not self.stopped.wait(1):
            try:
                current = self.stamp()
                if current == previous:
                    continue
                previous = current
                log = self.root/'temp/interface-build.log'
                log.parent.mkdir(parents=True, exist_ok=True)
                with log.open('ab') as stream:
                    # Each build exits. An app crash cannot leave a permanent
                    # development server or another watcher running.
                    self.process = subprocess.Popen(
                        [self.node, str(self.vite), 'build', '--emptyOutDir', 'false'],
                        cwd=self.root/'frontend', stdout=stream, stderr=subprocess.STDOUT,
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    while self.process.poll() is None and not self.stopped.wait(.2):
                        pass
                    if self.stopped.is_set():
                        self.stop_build()
            except OSError:
                continue

    def stop_build(self):
        if self.process is None or self.process.poll() is not None:
            return
        from core.render_context import _stop_process
        _stop_process(self.process)

    def close(self):
        self.stopped.set()
        if self.thread is not None:
            self.thread.join(12)
