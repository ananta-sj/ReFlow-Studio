"""Bounded publication retries, cancellation races and actual Windows locks."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import render_context as context
from dev.windows_lock_fixture import deny_delete

ROOT = Path(__file__).resolve().parents[1]


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'temp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.job = context.RenderContext(self.root / 'temp')
        self.addCleanup(self.job.cleanup)
        self.pending, self.destination = self.job.workspace / 'pending', self.root / 'published'

    def error(self, code=5):
        error = PermissionError('fixture Windows sharing denial')
        error.winerror = code
        return error

    def filesystem(self, replace, platform='nt'):
        return patch.object(context, 'os', SimpleNamespace(name=platform, path=os.path, replace=replace))

    def files(self):
        self.pending.write_bytes(b'new')
        self.destination.write_bytes(b'old')

    def test_transient_lock_retries_atomic_replace_and_preserves_old_until_success(self):
        self.files()
        error = self.error()
        calls = []
        def replace(pending, destination):
            calls.append(1)
            self.assertEqual(self.destination.read_bytes(), b'old')
            if len(calls) < 3:
                raise error
            os.replace(pending, destination)
        with self.filesystem(replace), patch.object(self.job.cancelled, 'wait', return_value=False) as wait:
            self.job.publish(self.pending, self.destination)
        self.assertEqual(self.destination.read_bytes(), b'new')
        self.assertEqual([call.args[0] for call in wait.call_args_list], [.05, .1])

    def test_persistent_lock_propagates_original_error_after_bounded_attempts(self):
        self.files()
        error = self.error(32)
        replace = Mock(side_effect=error)
        with self.filesystem(replace), patch.object(self.job.cancelled, 'wait', return_value=False) as wait:
            with self.assertRaises(PermissionError) as caught:
                self.job.publish(self.pending, self.destination)
        self.assertIs(caught.exception, error)
        self.assertEqual(replace.call_count, 4)
        self.assertEqual([call.args[0] for call in wait.call_args_list], [.05, .1, .2])
        self.assertEqual(self.destination.read_bytes(), b'old')
        self.assertEqual(self.pending.read_bytes(), b'new')

    def test_unknown_errors_and_other_platforms_are_not_retried(self):
        self.files()
        for platform, error in (('posix', self.error()), ('nt', self.error(87)), ('nt', OSError('disk failure'))):
            replace = Mock(side_effect=error)
            with self.filesystem(replace, platform), patch.object(self.job.cancelled, 'wait') as wait:
                with self.assertRaises(type(error)):
                    self.job.publish(self.pending, self.destination)
            self.assertEqual(replace.call_count, 1)
            wait.assert_not_called()
        self.assertEqual(self.destination.read_bytes(), b'old')

    def test_existing_directory_conflict_is_not_retried_or_modified(self):
        self.pending.mkdir()
        self.destination.mkdir()
        (self.destination / 'keep').write_bytes(b'old')
        replace = Mock(side_effect=self.error())
        with self.filesystem(replace), patch.object(self.job.cancelled, 'wait') as wait:
            with self.assertRaises(PermissionError):
                self.job.publish(self.pending, self.destination)
        self.assertEqual(replace.call_count, 1)
        wait.assert_not_called()
        self.assertEqual((self.destination / 'keep').read_bytes(), b'old')

    def test_file_cannot_replace_an_existing_directory(self):
        self.pending.write_bytes(b'new')
        self.destination.mkdir()
        replace = Mock(side_effect=self.error())
        with self.filesystem(replace), patch.object(self.job.cancelled, 'wait') as wait:
            with self.assertRaises(PermissionError):
                self.job.publish(self.pending, self.destination)
        self.assertEqual(replace.call_count, 1)
        wait.assert_not_called()
        self.assertEqual(self.pending.read_bytes(), b'new')

    def test_stop_from_another_thread_during_backoff_prevents_publication(self):
        self.files()
        replace = Mock(side_effect=self.error())
        def wait(seconds):
            with ThreadPoolExecutor(1) as pool:
                pool.submit(self.job.request_stop).result(timeout=1)
            return True
        with self.filesystem(replace), patch.object(self.job.cancelled, 'wait', side_effect=wait):
            with self.assertRaises(context.RenderCancelled):
                self.job.publish(self.pending, self.destination)
        self.assertEqual(replace.call_count, 1)
        self.assertEqual(self.destination.read_bytes(), b'old')

    def real_released_lock(self, directory=False, destination_lock=False):
        if directory:
            self.pending.mkdir()
            (self.pending / 'review.json').write_bytes(b'new')
            locked = self.pending / 'review.json'
        else:
            self.files()
            locked = self.destination if destination_lock else self.pending
        observed = threading.Event()
        original = os.replace
        def replace(*args):
            try:
                return original(*args)
            except PermissionError:
                observed.set()
                raise
        with ThreadPoolExecutor(1) as pool, patch.object(context.os, 'replace', side_effect=replace):
            with deny_delete(locked):
                future = pool.submit(self.job.publish, self.pending, self.destination)
                self.assertTrue(observed.wait(2), 'A genuine sharing denial was not observed')
                if not directory:
                    self.assertEqual(self.destination.read_bytes(), b'old')
            future.result(timeout=2)
        published = self.destination / 'review.json' if directory else self.destination
        self.assertEqual(published.read_bytes(), b'new')

    @unittest.skipUnless(os.name == 'nt', 'Actual Windows filesystem handles required')
    def test_real_locked_child_directory_publishes_after_handle_release(self):
        self.real_released_lock(directory=True)

    @unittest.skipUnless(os.name == 'nt', 'Actual Windows filesystem handles required')
    def test_real_locked_pending_file_publishes_after_handle_release(self):
        self.real_released_lock()

    @unittest.skipUnless(os.name == 'nt', 'Actual Windows filesystem handles required')
    def test_real_locked_destination_publishes_after_handle_release(self):
        self.real_released_lock(destination_lock=True)

    @unittest.skipUnless(os.name == 'nt', 'Actual Windows filesystem handles required')
    def test_real_persistent_lock_keeps_old_result_and_pending_file(self):
        self.files()
        with deny_delete(self.destination), self.assertRaises(PermissionError):
            self.job.publish(self.pending, self.destination)
        self.assertEqual(self.destination.read_bytes(), b'old')
        self.assertEqual(self.pending.read_bytes(), b'new')


if __name__ == '__main__':
    unittest.main()
