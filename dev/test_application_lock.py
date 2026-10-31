"""Actual process exclusion and abrupt-exit recovery for desktop state ownership."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.application_lock import ApplicationLock, AlreadyRunning

CHILD = """
import sys
sys.path.insert(0, sys.argv[1])
from core.application_lock import ApplicationLock, AlreadyRunning
try:
    with ApplicationLock(sys.argv[2]):
        print('locked', flush=True)
        if sys.argv[3] == 'hold':
            sys.stdin.read()
except AlreadyRunning:
    raise SystemExit(23)
"""


class ApplicationLockTests(unittest.TestCase):
    def child(self, folder, mode='once'):
        return subprocess.Popen([sys.executable, '-B', '-c', CHILD, str(ROOT), str(folder), mode],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

    def test_other_process_blocked_and_normal_close_releases(self):
        with tempfile.TemporaryDirectory() as folder:
            with ApplicationLock(folder):
                child = self.child(folder)
                out, err = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 23, err)
                self.assertNotIn('locked', out)
            child = self.child(folder)
            out, err = child.communicate(timeout=15)
            self.assertEqual(child.returncode, 0, err)
            self.assertIn('locked', out)

    def test_abrupt_process_exit_releases_without_deleting_marker(self):
        with tempfile.TemporaryDirectory() as folder:
            child = self.child(folder, 'hold')
            try:
                self.assertEqual(child.stdout.readline().strip(), 'locked')
                with self.assertRaises(AlreadyRunning):
                    with ApplicationLock(folder):
                        pass
                child.kill()
                child.communicate(timeout=15)
                self.assertTrue((Path(folder) / '.reflow-instance.lock').exists())
                with ApplicationLock(folder):
                    pass
            finally:
                if child.poll() is None:
                    child.kill()
                    child.communicate(timeout=15)

    def test_different_portable_folders_are_independent(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            with ApplicationLock(first), ApplicationLock(second):
                pass


if __name__ == '__main__':
    unittest.main()
