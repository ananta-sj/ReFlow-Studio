"""Actual process reuse and cancellation, without AI model downloads."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from core.feature_session import FeatureSession
from core.render_context import RenderContext, RenderCancelled

WORKER = '''import json,os,sys,time
from pathlib import Path
def read_json(path):
 deadline=time.monotonic()+1
 while True:
  try: return json.loads(path.read_text(encoding='utf-8'))
  except PermissionError:
   if time.monotonic()>=deadline: raise
   time.sleep(.01)
request=read_json(Path(sys.argv[1]))
folder=Path(request['params']['session_dir'])
last=0
while not (folder/'stop').exists():
 for path in sorted(folder.glob('call-????????.json')):
  sequence=int(path.stem[5:])
  if sequence<=last: continue
  call=read_json(path)
  time.sleep(call.get('sleep',0))
  result={'ok':not call.get('fail'), 'error':'fixture failure','pid':os.getpid(),'sequence':sequence}
  if call.get('invalid'): result=[]
  pending=path.with_suffix('.response.tmp')
  pending.write_text(json.dumps(result),encoding='utf-8')
  os.replace(pending,path.with_suffix('.response.json'))
  last=sequence
 time.sleep(.01)
'''


class FeatureSessionTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.job = RenderContext(self.root.name)
        self.addCleanup(self.job.cleanup)
        worker = self.job.workspace / 'fixture_worker.py'
        worker.write_text(WORKER, encoding='utf-8')
        self.session = FeatureSession(self.job, sys.executable, {}, worker=worker)

    def test_requests_reuse_one_process_and_cleanup_stops_it(self):
        first, second = self.session.call({}), self.session.call({})
        self.assertEqual(first['pid'], second['pid'])
        self.assertEqual(second['sequence'], 2)
        self.assertTrue(self.job.processes)
        self.assertEqual(list(self.session.folder.glob('call-*')), [])
        self.job.cleanup()
        self.assertFalse(self.session.thread.is_alive())
        self.assertFalse(self.job.processes)
        self.assertFalse(self.job.workspace.exists())

    def test_failed_request_is_reported_and_session_can_close(self):
        with self.assertRaisesRegex(RuntimeError, 'fixture failure'):
            self.session.call({'fail': True})
        self.session.close()
        self.assertFalse(self.session.thread.is_alive())

    def test_slow_close_stops_only_owned_session_and_preserves_job(self):
        original = self.session.call({})
        worker = self.job.workspace / 'ignores_stop_worker.py'
        worker.write_text(WORKER.replace("while not (folder/'stop').exists():", 'while True:'), encoding='utf-8')
        slow = FeatureSession(self.job, sys.executable, {}, worker=worker)
        slow.call({})
        slow.close()
        self.assertFalse(slow.thread.is_alive())
        self.assertFalse(self.job.cancelled.is_set())
        self.assertEqual(self.session.call({})['pid'], original['pid'])
        self.assertEqual(len(self.job.processes), 1)

    def test_invalid_worker_response_is_reported(self):
        with self.assertRaisesRegex(RuntimeError, 'invalid response'):
            self.session.call({'invalid': True})

    def test_thread_start_failure_does_not_block_job_cleanup(self):
        with patch('core.feature_session.threading.Thread.start', side_effect=RuntimeError('thread unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'thread unavailable'):
                FeatureSession(self.job, sys.executable, {})
        self.job.cleanup()
        self.assertFalse(self.job.workspace.exists())

    def test_cancellation_interrupts_inflight_inference_and_drains_process(self):
        self.session.call({})
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.session.call, {'sleep': 30})
            deadline = time.monotonic() + 5
            while not list(self.session.folder.glob('call-*')) and time.monotonic() < deadline:
                time.sleep(.01)
            self.job.request_stop()
            with self.assertRaises(RenderCancelled):
                future.result(timeout=5)
        self.job.cleanup()
        self.assertFalse(self.session.thread.is_alive())
        self.assertFalse(self.job.processes)
        self.assertFalse(self.job.workspace.exists())

    def test_removed_inflight_request_fails_promptly_and_drains_owned_process(self):
        self.session.call({})
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.session.call, {'sleep':30})
            deadline = time.monotonic()+5
            request = self.session.folder/'call-00000002.json'
            while not request.exists() and time.monotonic()<deadline:
                time.sleep(.01)
            self.assertTrue(request.exists())
            # Windows briefly denies deletion while the worker reads JSON.
            # Still require removal and the same fail-fast shutdown behavior.
            while True:
                try:
                    request.unlink()
                    break
                except PermissionError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(.01)
            with self.assertRaisesRegex(RuntimeError,'workspace was removed or changed'):
                future.result(timeout=5)
        self.job.cleanup()
        self.assertFalse(self.session.thread.is_alive())
        self.assertFalse(self.job.processes)

    def test_global_cleanup_preserves_job_requests_and_clears_only_legacy_temp(self):
        from core.janitor import Janitor
        janitor = Janitor()
        janitor.root_dir = self.root.name
        janitor.temp_dir = str(self.job.root)
        # This fixture uses root==temp; add a proper nested legacy root so
        # the production containment check is exercised rather than bypassed.
        isolated = Path(self.root.name)/'legacy-temp'
        isolated.mkdir()
        job = RenderContext(isolated)
        try:
            pending = job.workspace/'request.json'
            pending.write_text('keep',encoding='utf-8')
            obsolete = isolated/'old.wav'
            obsolete.write_bytes(b'legacy')
            janitor.temp_dir = str(isolated)
            janitor.sweep()
            self.assertEqual(pending.read_text(encoding='utf-8'),'keep')
            self.assertFalse(obsolete.exists())
            self.assertTrue(self.session.request.is_file())
        finally:
            job.cleanup()


if __name__ == '__main__':
    unittest.main()
