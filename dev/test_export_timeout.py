import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from core.render_context import RenderContext, bind_job, run_process


class ExportTimeoutTests(unittest.TestCase):
    def run_command(self, args, diagnostic=True):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryFile() as log:
            job = RenderContext(folder)
            process = Mock(returncode=0)
            process.communicate.return_value = (None, None)
            process._reflow_children = []
            try:
                with bind_job(job), patch('core.render_context.subprocess.Popen', return_value=process), patch('core.render_context.psutil.Process') as owner, patch('core.render_context._stop_process'), patch('core.render_context.time.monotonic', side_effect=[0, 0, 1801, 1801, 1801]):
                    owner.return_value.children.return_value = []
                    return run_process(args, timeout=1800, stderr=log if diagnostic else None)
            finally:
                job.cleanup()

    def test_logged_video_encode_can_finish_after_thirty_minutes(self):
        result = self.run_command(['ffmpeg', '-c:v', 'libx264', 'output.mp4'])
        self.assertEqual(result.returncode, 0)

    def test_other_commands_keep_their_deadline(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            self.run_command(['ffprobe', 'input.mp4'])

    def test_encode_without_activity_log_keeps_its_deadline(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            self.run_command(['ffmpeg', '-c:v', 'libx264', 'output.mp4'], diagnostic=False)
