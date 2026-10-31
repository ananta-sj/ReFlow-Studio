"""Exercise overlapping segment workers with simulated mutable speech engines."""
from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import Mock, patch
import unittest

from dev.test_speech_integrity import SpeechFixture, pipeline, xtts_local, rvc_local
from core.render_context import RenderContext, bind_job
from pydub.generators import Sine


class ParallelSpeechTests(SpeechFixture):
    def setUp(self):
        super().setUp()
        self.subject = pipeline.ReflowPipeline.__new__(pipeline.ReflowPipeline)
        self.subject.temp_dir = str(self.directory)
        self.subject.registry = Mock()
        self.subject.registry.get_active.return_value = None
        self.subject.registry.list.return_value = []
        self.subject.speed_change = lambda clip, speed: clip
        self.transcript = [dict(start=0, end=1, text='first'),
                           dict(start=2, end=3, text='second')]
        self.master = Mock()
        self.attempted = threading.Event()
        self.active = 0
        self.peak = 0
        self.calls = []
        self.mutex = threading.Lock()
        original = pipeline.ReflowPipeline._maybe_locked
        self.attempts = 0
        self.operation = 'synthesize'

        def observed(lock, fn):
            # Observed calls name their operation as a literal rather than a
            # direct provider attribute. Keep the two-worker gate in both paths.
            if self.operation in (*fn.__code__.co_names, *fn.__code__.co_consts):
                with self.mutex:
                    self.attempts += 1
                    if self.attempts >= 2:
                        self.attempted.set()
            return original(lock, fn)
        self.stack.enter_context(patch.object(pipeline.ReflowPipeline, '_maybe_locked', staticmethod(observed)))

    def engine(self, label, path):
        with self.mutex:
            self.active += 1
            self.peak = max(self.peak, self.active)
            self.calls.append(label)
            first = len(self.calls) == 1
        try:
            if first and not self.attempted.wait(5):
                raise RuntimeError('second worker never attempted speech inference')
            self.write_audio(path)
        finally:
            with self.mutex:
                self.active -= 1

    def batch(self, tts, voices=None, cast=None, device='cpu'):
        gen = self.subject._dub_all_segments(
            self.transcript, cast or ['CLONED_USER'], 'en', tts, voices or {},
            None, str(self.reference), device, self.master, max(cue['end'] for cue in self.transcript), 45, 30, max_workers=2)
        while True:
            try:
                next(gen)
            except StopIteration as done:
                return done.value

    def lazy_xtts(self, device):
        handler = Mock()
        handler.generate_audio.side_effect = lambda text, path, **kw: self.engine(text, path)
        def construct(**kwargs):
            if not self.attempted.wait(5):
                raise RuntimeError('second worker never attempted lazy initialization')
            return handler
        with patch.object(xtts_local, 'TTSHandler', side_effect=construct) as constructor:
            track = self.batch(xtts_local.XTTSLocalProvider(device=device), device=device)
        self.assertEqual(constructor.call_count, 1)
        self.assertEqual(handler.generate_audio.call_count, 2)
        self.assertEqual(self.peak, 1)
        self.assertGreater(track[:900].rms, 0)
        self.assertGreater(track[2100:2900].rms, 0)

    def test_cpu_xtts_initializes_once_and_serializes_calls(self):
        self.lazy_xtts('cpu')

    def test_gpu_xtts_retains_serialization(self):
        self.lazy_xtts('cuda')

    def test_cpu_rvc_serializes_different_actors_and_model_state(self):
        self.operation = 'convert'
        self.subject.registry.list.return_value = []
        shared = {'model': None}
        handlers = []
        def constructor(**kwargs):
            handler = Mock()
            def infer(source, dest, model_name, **options):
                shared['model'] = model_name
                self.engine(model_name, dest)
                self.assertEqual(shared['model'], model_name)
                return dest
            handler.infer.side_effect = infer
            handlers.append(handler)
            return handler
        tts = Mock()
        tts.synthesize.side_effect = lambda text, path, **kw: self.write_audio(path)
        with patch.object(rvc_local, 'RVCHandler', side_effect=constructor):
            self.batch(tts, {'Alice': rvc_local.RVCLocalProvider('cpu'),
                             'Bob': rvc_local.RVCLocalProvider('cpu')}, ['Alice', 'Bob'])
        self.assertEqual(len(handlers), 2)
        self.assertCountEqual(self.calls, ['Alice', 'Bob'])
        self.assertEqual(self.peak, 1)

    def test_cpu_f5_generation_serialized_without_base_tts(self):
        self.operation = 'convert'
        self.subject.registry.list.return_value = [dict(display_name='F5', request_preset='f5tts')]
        voice = Mock()
        voice.convert.side_effect = lambda source, dest, **kw: self.engine(kw['text'], dest)
        tts = Mock()
        self.batch(tts, {'F5': voice}, ['F5'])
        self.assertEqual(self.peak, 1)
        self.assertCountEqual(self.calls, ['first', 'second'])
        tts.synthesize.assert_not_called()

    def test_mastering_remains_parallel_and_mix_keeps_source_order(self):
        second_finished = threading.Event()
        finishes = []
        def synthesize(text, path, **kwargs):
            frequency = 220 if text == 'first' else 880
            Sine(frequency).to_audio_segment(duration=1000).export(path, format='wav').close()
        def master(path):
            first = 'reflow-segment-1-' in str(path)
            if first:
                if not second_finished.wait(5):
                    raise RuntimeError('mastering did not overlap')
                finishes.append('first')
            else:
                finishes.append('second')
                second_finished.set()
        tts = Mock()
        tts.synthesize.side_effect = synthesize
        with patch('core.loudness.normalize_voice_loudness', side_effect=master):
            track = self.batch(tts)
        expected = Sine(220).to_audio_segment(duration=1000)
        self.assertEqual(finishes, ['second', 'first'])
        self.assertEqual(track[:1000].raw_data, expected.raw_data)
        self.assertEqual(track[1000:2000].rms, 0)
        self.assertEqual(track[2000:3000].raw_data, Sine(880).to_audio_segment(duration=1000).raw_data)

    def test_slow_first_segment_bounds_out_of_order_work(self):
        self.transcript = [dict(start=i, end=i + 1, text=str(i)) for i in range(20)]
        release, window_ready, escaped = threading.Event(), threading.Event(), threading.Event()
        visited = []
        lock = threading.Lock()
        def segment(index, *args, **kwargs):
            with lock:
                visited.append(index)
                if index >= 4 and not release.is_set():
                    escaped.set()
                if len(visited) == 4:
                    window_ready.set()
            if index == 0 and not release.wait(5):
                raise RuntimeError('test release timeout')
            return Sine(220).to_audio_segment(duration=100)
        with patch.object(self.subject, '_dub_segment', side_effect=segment), ThreadPoolExecutor(1) as pool:
            future = pool.submit(self.batch, Mock())
            try:
                self.assertTrue(window_ready.wait(5))
                self.assertFalse(escaped.wait(.4))
                self.assertEqual(sorted(visited), [0, 1, 2, 3])
            finally:
                release.set()
            future.result(timeout=10)
        self.assertEqual(sorted(visited), list(range(20)))

    def test_cancel_waiting_cpu_worker_skips_second_engine_and_joins_first(self):
        job = RenderContext(self.directory)
        self.subject.temp_dir = str(job.workspace)
        entered, release = threading.Event(), threading.Event()
        tts = Mock()
        def synthesize(text, path, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test release timeout')
            self.write_audio(path)
        tts.synthesize.side_effect = synthesize
        def work():
            with bind_job(job):
                return self.batch(tts)
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(work)
            try:
                self.assertTrue(entered.wait(5))
                self.assertTrue(self.attempted.wait(5))
                job.request_stop()
                self.assertFalse(future.done())
                self.assertTrue(job.workspace.exists())
            finally:
                release.set()
            with self.assertRaisesRegex(RuntimeError, 'cancellation'):
                future.result(timeout=10)
        self.assertEqual(tts.synthesize.call_count, 1)
        self.assertFalse(list(job.workspace.glob('reflow-segment-*')))
        job.cleanup()
        self.assertFalse(job.workspace.exists())


if __name__ == '__main__':
    unittest.main()
