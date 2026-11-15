"""Read progress reported by owned separation workers during long stages."""
import re
import threading


class SeparationProgress:
    def __init__(self, job, report):
        self.job, self.report = job, report
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        previous = -1
        while not self.stopped.wait(2):
            try:
                for path in self.job.workspace.glob('demucs-*/worker.log'):
                    with path.open('rb') as stream:
                        stream.seek(0, 2)
                        stream.seek(max(0, stream.tell()-8192))
                        text = stream.read().decode('utf-8', errors='replace')
                    percentages = re.findall(r'(\d{1,3})%\|', text)
                    if percentages:
                        percent = min(100, int(percentages[-1]))
                        if percent > previous:
                            previous = percent
                            self.report(percent)
            except (OSError, RuntimeError):
                continue

    def close(self):
        self.stopped.set()
        self.thread.join(3)
