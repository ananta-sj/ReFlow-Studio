"""Real subprocess capture inside job-owned cancellation-aware execution."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.render_context import RenderContext, bind_job, run_process


class ProcessCaptureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=ROOT / 'temp')
        self.addCleanup(temporary.cleanup)
        self.job = RenderContext(Path(temporary.name))
        self.addCleanup(self.job.cleanup)

    def test_job_capture_keeps_stdout_and_stderr_separate(self):
        with bind_job(self.job):
            result = run_process([sys.executable, '-c',
                "import sys; print('video-info'); print('diagnostic',file=sys.stderr)"],
                capture_output=True, text=True, check=True, timeout=10)
        self.assertEqual(result.stdout.strip(), 'video-info')
        self.assertEqual(result.stderr.strip(), 'diagnostic')
        self.assertFalse(self.job.processes)

    def test_failed_job_capture_preserves_binary_diagnostics(self):
        with bind_job(self.job), self.assertRaises(subprocess.CalledProcessError) as caught:
            run_process([sys.executable, '-c',
                "import sys; print('partial'); print('failed',file=sys.stderr); sys.exit(7)"],
                capture_output=True, check=True, timeout=10)
        self.assertEqual(caught.exception.returncode, 7)
        self.assertEqual(caught.exception.stdout.strip(), b'partial')
        self.assertEqual(caught.exception.stderr.strip(), b'failed')
        self.assertFalse(self.job.processes)

    def test_conflicting_streams_fail_before_launch(self):
        for argument in ('stdout', 'stderr'):
            with self.subTest(argument=argument), bind_job(self.job), self.assertRaises(ValueError):
                run_process([sys.executable, '-c', 'pass'], capture_output=True,
                            **{argument: subprocess.PIPE})
            self.assertFalse(self.job.processes)

    def test_explicit_capture_false_preserves_stdout_option(self):
        with bind_job(self.job):
            result = run_process([sys.executable, '-c', "print('explicit')"],
                capture_output=False, stdout=subprocess.PIPE, text=True, check=True, timeout=10)
        self.assertEqual(result.stdout.strip(), 'explicit')


if __name__ == '__main__':
    unittest.main()
