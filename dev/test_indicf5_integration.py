"""IndicF5 routing/reference/timing guards without loading model weights."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from dev.test_speech_integrity import SpeechFixture, pipeline
from core.model_contract import local_contract
from core.providers.resolve import resolve_tts, uses_exact_reference, confirmed_reference
from core.providers.tts.indicf5_local import load_reference_profile, IndicF5TTSProvider, require_supported_text
from core.speech_language import preflight_speech


class IndicF5IntegrationTests(SpeechFixture):
    def setUp(self):
        super().setUp()
        self.model = self.directory / 'model'
        (self.model / 'checkpoints').mkdir(parents=True)
        (self.model / 'config.json').write_text(json.dumps({'model_type':'inf5','architectures':['INF5Model']}))
        (self.model / 'model.safetensors').write_bytes(b'fixture weights, never loaded')
        (self.model / 'checkpoints/vocab.txt').write_text('\n'.join(sorted(set('reference text calibration text hello')))+'\n')
        self.profile = self.directory / 'profile.json'
        self.value = dict(schema='reflow.indicf5.reference.v1', language='hi', human_reference_confirmed=True,
            reference_audio='reference.wav', reference_sha256=hashlib.sha256(self.reference.read_bytes()).hexdigest(),
            reference_text='reference text', calibration_text='calibration text', calibration_seconds=7.744,
            seed=1234, guidance=2.0, steps=32, sentence_gap_seconds=.2)
        self.save()
        self.entry = dict(kind='local_file', stage_type='tts', local_path=str(self.model),
                          meta={'reference_profile':str(self.profile)})
        self.registry = Mock(get_active=Mock(return_value=self.entry), list=Mock(return_value=[]))

    def save(self):
        self.profile.write_text(json.dumps(self.value), encoding='utf-8')

    def test_distinct_contract_and_provider_resolution(self):
        self.assertEqual(local_contract('tts', self.model)['adapter'], 'indicf5')
        self.assertIsInstance(resolve_tts(self.registry, 'cpu'), IndicF5TTSProvider)
        self.assertTrue(uses_exact_reference(self.registry))

    def test_selected_reference_without_upload_and_matching_upload(self):
        self.assertEqual(confirmed_reference(self.registry), str(self.reference))
        self.assertEqual(confirmed_reference(self.registry, str(self.reference)), str(self.reference))

    def test_explicit_wrong_or_missing_reference_is_rejected(self):
        wrong = self.directory / 'wrong.wav'
        wrong.write_bytes(b'other voice')
        with self.assertRaisesRegex(ValueError, 'confirmed Hindi voice'):
            confirmed_reference(self.registry, wrong)
        with self.assertRaisesRegex(ValueError, 'does not exist'):
            confirmed_reference(self.registry, self.directory / 'missing.wav')

    def test_default_reference_still_rejects_modified_profile_audio(self):
        self.reference.write_bytes(b'changed audio')
        with self.assertRaisesRegex(ValueError, 'changed'):
            confirmed_reference(self.registry)

    def test_missing_vocabulary_and_wrong_architecture_fail(self):
        vocab = self.model / 'checkpoints/vocab.txt'
        vocab.unlink()
        with self.assertRaises(ValueError):
            local_contract('tts', self.model)
        vocab.write_text('fixture')
        (self.model / 'config.json').write_text('{"model_type":"inf5","architectures":["Other"]}')
        with self.assertRaises(ValueError):
            local_contract('tts', self.model)

    def test_changed_reference_and_unconfirmed_pair_fail(self):
        self.value['human_reference_confirmed'] = False
        self.save()
        with self.assertRaises(ValueError):
            load_reference_profile(self.profile)
        self.value['human_reference_confirmed'] = True
        self.save()
        self.reference.write_bytes(b'changed audio')
        with self.assertRaisesRegex(ValueError, 'changed'):
            load_reference_profile(self.profile)

    def test_invalid_generation_fields_fail(self):
        original = dict(self.value)
        for field, value in [('seed', True), ('steps', 3), ('guidance', float('nan')),
                             ('sentence_gap_seconds', -1), ('calibration_seconds', 0),
                             ('reference_sha256', 'invalid'), ('original_source_sha256', [])]:
            with self.subTest(field=field):
                self.value = {**original, field:value}
                self.save()
                with self.assertRaises(ValueError):
                    load_reference_profile(self.profile)

    def test_hindi_only_and_no_rvc_reference_substitution(self):
        preflight_speech(self.registry, ['CLONED_USER'], 'hi')
        with self.assertRaisesRegex(ValueError, 'Hindi only'):
            preflight_speech(self.registry, ['CLONED_USER'], 'en')
        with self.assertRaisesRegex(ValueError, 'without RVC'):
            preflight_speech(self.registry, ['actor'], 'hi')

    def test_foreign_reference_fails_before_starting_worker(self):
        provider = resolve_tts(self.registry, 'cpu')
        unrelated = self.directory / 'other.wav'
        unrelated.write_bytes(b'unrelated')
        with patch('core.providers.tts.indicf5_local.isolated_interpreter') as runtime:
            with self.assertRaisesRegex(ValueError, 'does not match'):
                provider.synthesize('hello', self.output, 'hi', unrelated)
            runtime.assert_not_called()

    def test_invalid_floor_never_starts_runtime_or_overwrites_output(self):
        provider=IndicF5TTSProvider(str(self.model),str(self.profile))
        self.output.write_bytes(b'prior output')
        with patch('core.providers.tts.indicf5_local.isolated_interpreter') as runtime:
            with self.assertRaises(ValueError):
                provider.synthesize('hello',self.output,'hi',str(self.reference),minimum_sentence_seconds=float('nan'))
            runtime.assert_not_called()
        self.assertEqual(self.output.read_bytes(),b'prior output')

    def subject(self):
        subject = pipeline.ReflowPipeline.__new__(pipeline.ReflowPipeline)
        subject.temp_dir = str(self.directory)
        subject.registry = self.registry
        subject.speed_change = Mock(side_effect=lambda clip, speed: clip)
        return subject

    def test_unsupported_punctuation_fails_before_worker_and_preserves_output(self):
        provider = resolve_tts(self.registry, 'cpu')
        self.output.write_bytes(b'previous good output')
        with patch('core.providers.tts.indicf5_local.isolated_interpreter') as runtime:
            with self.assertRaisesRegex(ValueError, 'U\\+2014'):
                provider.synthesize('hello—hello', self.output, 'hi', self.reference)
            runtime.assert_not_called()
        self.assertEqual(self.output.read_bytes(), b'previous good output')

    def test_supported_text_and_reference_do_not_require_model_imports(self):
        require_supported_text('hello', self.model / 'checkpoints/vocab.txt', 'reference text')
        with self.assertRaisesRegex(ValueError, 'reference text contains unsupported'):
            require_supported_text('hello', self.model / 'checkpoints/vocab.txt', 'reference—text')

    def test_native_delivery_skips_old_hindi_tempo_and_mastering(self):
        subject = self.subject()
        tts = SimpleNamespace(preserves_native_delivery=True,
            synthesize=lambda text, path, **kw:self.write_audio(path, duration=900))
        mastering = Mock()
        with patch('core.loudness.normalize_voice_loudness') as normalization:
            clip = subject._dub_segment(0, {'start':0,'end':1,'text':'speech'}, ['CLONED_USER'], 'hi',
                tts, {}, str(self.reference), None, 'cpu', mastering)
            self.assertEqual(len(clip), 900)
            normalization.assert_not_called()
        mastering.master_voice_segment.assert_not_called()
        self.assertEqual(subject.speed_change.call_args.args[1], 1.0)

    def test_later_native_overflow_fails_before_any_speech(self):
        tts = SimpleNamespace(preserves_native_delivery=True,
                              estimate_duration_seconds=Mock(side_effect=[.9, 1.4]), synthesize=Mock())
        transcript = [dict(start=0, end=1, text='first'), dict(start=1, end=2, text='last')]
        with self.assertRaisesRegex(RuntimeError, 'Segment 2.*1.400s.*1.000s'):
            pipeline._preflight_native_cue_durations(tts, transcript, ['CLONED_USER'])
            tts.synthesize('first', self.output)
        tts.synthesize.assert_not_called()

    def test_native_preflight_uses_gap_and_final_cue_end(self):
        tts = SimpleNamespace(preserves_native_delivery=True,
                              estimate_duration_seconds=Mock(side_effect=[1.8, .9]))
        transcript = [dict(start=0, end=1, text='first'), dict(start=2, end=3, text='last')]
        pipeline._preflight_native_cue_durations(tts, transcript, ['CLONED_USER'])
        self.assertEqual(tts.estimate_duration_seconds.call_count, 2)
        tts.estimate_duration_seconds.reset_mock()
        pipeline._preflight_native_cue_durations(tts, transcript, ['actor'])
        tts.estimate_duration_seconds.assert_not_called()

    def test_duration_preflight_rejects_unprepared_reference_without_worker(self):
        # Fixture reference is 44.1 kHz, unlike the required prepared 24 kHz file.
        provider = resolve_tts(self.registry, 'cpu')
        with patch('core.providers.tts.indicf5_local.isolated_interpreter') as runtime:
            with self.assertRaisesRegex(ValueError, 'mono 24 kHz'):
                provider.estimate_duration_seconds('hello')
            runtime.assert_not_called()

    def test_native_overflow_is_rejected_instead_of_cutting_words(self):
        subject = self.subject()
        tts = SimpleNamespace(preserves_native_delivery=True,
            synthesize=lambda text, path, **kw:self.write_audio(path, duration=1400))
        with self.assertRaisesRegex(RuntimeError, 'cannot fit without cutting words'):
            subject._dub_segment(0, {'start':0,'end':1,'text':'speech'}, ['CLONED_USER'], 'hi',
                tts, {}, str(self.reference), None, 'cpu', Mock())
        self.assertFalse(list(self.directory.glob('reflow-segment-*')))


if __name__ == '__main__':
    unittest.main()
