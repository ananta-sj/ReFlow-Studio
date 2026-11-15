from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from core.batch_intelligibility import verify
from core.speech_timing import dialogue_end


class ReadbackTests(unittest.TestCase):
    def test_long_pause_does_not_become_a_speech_window(self):
        cue = dict(start=10, end=12)
        self.assertAlmostEqual(dialogue_end(cue, 200), 12.35)
        self.assertAlmostEqual(dialogue_end(cue, 12.1), 12.1)
        self.assertEqual(dialogue_end(cue), 12)

    def test_one_readback_failure_does_not_discard_other_lines(self):
        from pydub import AudioSegment
        from core.render_context import RenderContext, bind_job
        with tempfile.TemporaryDirectory() as folder:
            job = RenderContext(folder)
            provider = Mock()
            durations = []
            def recognize(paths, language):
                if len(paths) > 1:
                    raise ValueError('Batch contains an unreliable take')
                durations.append(len(AudioSegment.from_wav(paths[0])))
                if len(durations) == 1:
                    raise ValueError('Unreliable recognition timestamps')
                return [[dict(start=0, end=1, text='hello')]]
            provider.transcribe_takes.side_effect = recognize
            try:
                with bind_job(job):
                    report = verify(AudioSegment.silent(duration=130000), [
                        dict(start=1, end=2, text='hello', cue_id='A'),
                        dict(start=100, end=101, text='hello', cue_id='B')], provider, 'en', {}, None)
                self.assertEqual(durations, [30000, 30000])
                self.assertEqual(report['cues'][0]['reason'], 'speech_readback_unavailable')
                self.assertEqual(report['cues'][1]['status'], 'passed_readback')
                provider.release.assert_called_once()
            finally:
                job.cleanup()
