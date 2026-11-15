"""Recovery survives process restarts and rejects changed or incomplete media."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pydub.generators import Sine
from core.audio_checkpoints import AudioCheckpoints
from core.pipeline import ReflowPipeline
from core.pipeline_contracts import PipelineSpec, RegistrySnapshot, SettingsSnapshot
from core.providers.tts.xtts_local import XTTSLocalProvider
from core.run_manifest import RunManifest
from core.stage_checkpoints import StageCheckpoints


class AudioCheckpointTests(unittest.TestCase):
    def test_cuda_runtime_is_validated_once_per_job_not_per_take(self):
        self.provider.runtime = 'cuda'
        self.provider.device = 'cuda:0'
        with patch('core.cuda_runtime.validate', return_value={'identity':'verified-gpu'}) as validate:
            first = self.cache.key('speech', {'text':'First'}, self.provider, 'CLONED_USER')
            second = self.cache.key('speech', {'text':'Second'}, self.provider, 'CLONED_USER')
            self.assertNotEqual(first, second)
            self.assertEqual(validate.call_count, 1)
            self.new_cache().key('speech', {'text':'First'}, self.provider, 'CLONED_USER')
            self.assertEqual(validate.call_count, 2)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root/'project'
        source_project = Path(__file__).resolve().parents[1]
        names = ['core/audio_checkpoints.py', 'core/pipeline.py', 'core/audio_utils.py',
                 'core/loudness.py', 'core/speech_timing.py', 'core/speech_language.py', 'core/dialogue_integrity.py',
                 'core/xtts_text.py', 'core/tts/tts_handler.py', 'core/xtts_compat.py',
                 'core/xtts_worker.py', 'core/providers/tts/xtts_local.py', 'core/media_io.py']
        names += ['core/voice_conditioning.py','core/speech_generation_budget.py']
        for name in names:
            path = self.project/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((source_project/name).read_bytes())
        self.runtime = self.root/'runtime'
        self.runtime.mkdir()
        self.executable = self.runtime/'python.exe'
        self.executable.write_bytes(b'python')
        self.model = self.root/'model'
        self.model.mkdir()
        (self.model/'weights.bin').write_bytes(b'weights')
        self.source = self.root/'source.wav'
        self.clip = Sine(220).to_audio_segment(duration=500).apply_gain(-12)
        self.clip.export(self.source, format='wav').close()
        self.registry = RegistrySnapshot(dict(entries=[], active={}))
        self.settings = SettingsSnapshot({})
        self.provider = XTTSLocalProvider(device='cpu', model_path=str(self.model))
        self.patch = patch('core.python_runtime.worker_python', return_value=str(self.executable))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.cache = self.new_cache()

    def new_cache(self):
        manifest = RunManifest(self.root/'records', PipelineSpec('video_dub'), self.source,
                               self.registry, self.settings)
        manifest.capture_source(self.source)
        stages = StageCheckpoints(self.root/'cache', manifest, self.registry, self.project)
        return AudioCheckpoints(stages, self.settings)

    def test_speech_is_reused_by_normal_segment_entry_after_restart(self):
        subject = ReflowPipeline.__new__(ReflowPipeline)
        subject.temp_dir = str(self.root)
        subject._audio_checkpoints = self.cache
        cue = dict(start=0, end=1, text='नमस्ते')
        args = (0, cue, ['CLONED_USER'], 'hi', self.provider, {}, None, str(self.source), 'cpu', None)
        with patch.object(ReflowPipeline, '_dub_segment_bound', autospec=True, return_value=self.clip) as generate:
            first = subject._dub_segment(*args)
            subject._audio_checkpoints = self.new_cache()
            second = subject._dub_segment(*args)
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(first.raw_data, second.raw_data)

    def test_model_reference_or_text_changes_invalidate_speech(self):
        key = self.cache.key('speech', dict(text='One', reference='original'), self.provider, 'CLONED_USER')
        self.assertNotEqual(key, self.cache.key('speech', dict(text='Two', reference='original'), self.provider, 'CLONED_USER'))
        self.assertNotEqual(key, self.cache.key('speech', dict(text='One', reference='new'), self.provider, 'CLONED_USER'))
        (self.model/'weights.bin').write_bytes(b'changed model')
        self.assertNotEqual(key, self.new_cache().key('speech', dict(text='One', reference='original'), self.provider, 'CLONED_USER'))

    def test_corruption_and_partial_publication_cannot_be_reused(self):
        key = 'a'*64
        self.cache.store('speech', key, {'take': self.source})
        restored = self.new_cache().load('speech', key)
        self.assertIsNotNone(restored)
        Path(restored['take']).write_bytes(b'corrupt')
        self.assertIsNone(self.new_cache().load('speech', key))
        folder = self.cache.folder('speech', 'b'*64)
        folder.mkdir(parents=True)
        (folder/'interrupted.pending').write_bytes(self.source.read_bytes())
        self.assertIsNone(self.new_cache().load('speech', 'b'*64))

    def test_separation_is_published_only_as_a_complete_pair(self):
        key = 'c'*64
        self.cache.store('separate', key, {'vocals': self.source, 'background': self.source})
        self.assertEqual(set(self.new_cache().load('separate', key)), {'vocals', 'background'})
        descriptor = self.cache.folder('separate', key)/'index.json'
        data = json.loads(descriptor.read_text())
        del data['files']['background']
        descriptor.write_text(json.dumps(data))
        self.assertIsNone(self.new_cache().load('separate', key))

    def test_generated_separation_config_does_not_invalidate_saved_stems(self):
        from types import SimpleNamespace

        model = self.root/'separation-model'
        model.mkdir()
        (model/'955717e8-8726e21a.th').write_bytes(b'weights')
        for name in ('core/audio_separator.py', 'core/run_demucs.py', 'core/separation_runtime.py'):
            target = self.project/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('fixture')
        cache = self.new_cache()
        provider = SimpleNamespace(device='cpu', runtime='legacy', models_dir=str(model))
        inputs = dict(audio_path=str(self.source))
        first = cache.key('separate', inputs, provider)
        (model/'htdemucs.yaml').write_text("models: ['955717e8']")
        self.assertEqual(self.new_cache().key('separate', inputs, provider), first)
