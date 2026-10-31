"""Separation cancellation and corrupt/missing stem failures with owned fixtures."""
from pathlib import Path
import io
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from core import audio_separator as separation
from core.render_context import RenderContext, bind_job, RenderCancelled

ROOT = Path(__file__).resolve().parents[1]


class AudioSeparatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'temp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'models/uvr').mkdir(parents=True)
        (self.root/'models/uvr/955717e8-8726e21a.th').write_bytes(b'fixture')
        self.job = RenderContext(self.root/'temp')
        self.addCleanup(self.job.cleanup)

    def execute(self, effect, outputs=True, decoder=None):
        with bind_job(self.job), patch.object(separation, 'project_root', return_value=self.root), \
             patch.object(separation, 'worker_python', return_value='fixture-python'), \
             patch('hashlib.sha256') as digest, \
             patch.object(separation, 'run_process', side_effect=effect), \
             patch.object(separation, 'load_playable_audio', side_effect=decoder) as decode:
            digest.return_value.hexdigest.return_value = separation.DEMUCS_SHA256
            engine = separation.AudioSeparator()
            if outputs:
                folder = Path(engine.work_dir)/'htdemucs/source'
                folder.mkdir(parents=True)
                for name in ('vocals.wav', 'no_vocals.wav'):
                    (folder/name).write_bytes(b'fixture')
            result = engine.separate('source.wav')
            return result, decode.call_count

    def test_worker_cancellation_preserves_exact_exception(self):
        error = RenderCancelled('stop at active worker')
        with self.assertRaises(RenderCancelled) as caught:
            self.execute(error)
        self.assertIs(caught.exception, error)

    def test_cancellation_during_output_validation_is_not_render_failure(self):
        error = RenderCancelled('stop while validating stems')
        with self.assertRaises(RenderCancelled) as caught:
            self.execute(None, decoder=error)
        self.assertIs(caught.exception, error)

    def test_missing_stems_still_fail(self):
        with self.assertRaisesRegex(RuntimeError, 'both required stems'):
            self.execute(None, outputs=False)

    def test_undecodable_stem_still_fails(self):
        with self.assertRaisesRegex(RuntimeError, 'Audio separation failed: invalid PCM'):
            self.execute(None, decoder=RuntimeError('invalid PCM'))

    def test_failed_worker_preserves_diagnostics(self):
        with self.assertRaisesRegex(RuntimeError, 'Demucs worker failed'):
            self.execute(subprocess.CalledProcessError(1, ['fixture-python']))

    def test_both_stems_are_validated_before_success(self):
        result, count = self.execute(None)
        self.assertEqual(count, 2)
        self.assertEqual([Path(path).name for path in result], ['vocals.wav', 'no_vocals.wav'])

    def test_ascii_filename_works_with_windows_legacy_output_encoding(self):
        stream = io.TextIOWrapper(io.BytesIO(), encoding='cp1252')
        try:
            with patch('sys.stdout', stream):
                self.execute(None)
                stream.flush()
        finally:
            stream.close()


if __name__ == '__main__':
    unittest.main()
