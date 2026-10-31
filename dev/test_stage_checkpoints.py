"""Recovery and invalidation behavior with disposable local assets."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave

from core.pipeline_contracts import PipelineSpec, RegistrySnapshot, SettingsSnapshot, identify_cues
from core.run_manifest import RunManifest, bind_manifest
from core.stage_checkpoints import StageCheckpoints, digest, validate_payload
from core.transcription import TranscriptionResult
from core import stage_checkpoints as checkpoints
from core import review_cue_contracts as review
from core.source_language import resolve_source_language
from core.pipeline import ReflowPipeline


class Provider:
    prefers_sentence_groups = True
    def __init__(self):
        self.calls = 0
    def translate(self, text, target, **kwargs):
        self.calls += 1
        return 'Hindi: ' + text


class StageCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ('core', 'model', 'runtime'):
            (self.root / folder).mkdir()
        (self.root/'core/stage.py').write_text('code-v1', encoding='utf-8')
        (self.root/'config.py').write_text('config-v1', encoding='utf-8')
        (self.root/'model/weights.bin').write_bytes(b'weights-v1')
        (self.root/'runtime/python.exe').write_bytes(b'runtime-v1')
        self.source = self.root/'source.srt'
        self.source.write_text('source', encoding='utf-8')
        entries = [dict(id=stage, stage_type=stage, kind='local_file', local_path=str(self.root/'model'),
                        request_preset=stage) for stage in ('stt', 'translation')]
        self.registry = RegistrySnapshot(dict(entries=entries, active={stage:stage for stage in ('stt','translation')}))
        self.manifest = RunManifest(self.root/'records', PipelineSpec('subtitle_translate'),
                                    self.source, self.registry, SettingsSnapshot({}))
        self.manifest.capture_source(self.source)
        self.cache = self.new_cache()
        self.provider = Provider()
        adapter = Provider.__module__+'.'+Provider.__name__
        for patcher in (patch.dict(checkpoints.SUPPORTED, stt=adapter, translation=adapter),
                patch('core.whisper_turbo_assets.isolated_interpreter', return_value=str(self.root/'runtime/python.exe')),
                patch('core.indictrans2_assets.isolated_interpreter', return_value=str(self.root/'runtime/python.exe'))):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.transcript = TranscriptionResult(identify_cues([dict(start=0,end=1,text='Hello')]), 'en', .99)
        self.inputs = dict(audio_sha256='audio-one', duration=2, sentence_continuations=True)

    def new_cache(self):
        return StageCheckpoints(self.root/'cache', self.manifest, self.registry, self.root)

    def key(self, stage='stt', inputs=None):
        return self.new_cache().key(stage, self.provider, inputs or self.inputs)

    def test_roundtrip_records_origin_without_fake_inference(self):
        key = self.key()
        self.assertIsNone(self.cache.load('stt', key, self.inputs))
        self.cache.store('stt', key, self.inputs, self.transcript, self.provider)
        loaded = self.cache.load('stt', key, self.inputs)
        self.assertEqual(loaded.to_payload(), self.transcript.to_payload())
        loaded[0]['text'] = 'edited'
        self.assertEqual(self.cache.load('stt',key,self.inputs)[0]['text'], 'Hello')
        self.assertEqual(self.manifest.data['checkpoints'][-1]['origin_run_id'], self.manifest.data['run_id'])
        self.assertFalse(self.manifest.data['operations'])

    def test_model_runtime_code_and_source_changes_invalidate(self):
        original = self.key()
        for path in ('model/weights.bin','runtime/python.exe','core/stage.py'):
            item = self.root/path; before=item.read_bytes()
            item.write_bytes(before+b'change')
            self.assertNotEqual(self.key(), original, path)
            item.write_bytes(before)
        self.manifest.data['source']['sha256'] = 'changed-source'
        self.assertNotEqual(self.key(),original)

    def test_audio_and_grouping_changes_invalidate(self):
        key=self.key()
        for field, value in [('audio_sha256','other'),('duration',3),('sentence_continuations',False)]:
            self.assertNotEqual(self.key(inputs=dict(self.inputs, **{field:value})),key)

    def test_downstream_voice_and_target_do_not_change_recognition_key(self):
        key=self.key()
        self.manifest.data['plan']['parameters'].update(target_lang='fr',cast_list=['another'])
        self.assertEqual(self.key(),key)

    def test_corrupt_payload_and_incomplete_file_are_not_reused(self):
        key=self.key();self.cache.store('stt',key,self.inputs,self.transcript,self.provider)
        path=self.cache.path('stt',key);item=json.loads(path.read_text(encoding='utf-8'))
        item['payload']['segments'][0]['text']='tampered'
        path.write_text(json.dumps(item),encoding='utf-8')
        self.assertIsNone(self.cache.load('stt',key,self.inputs))
        path.write_text('{',encoding='utf-8')
        self.assertIsNone(self.cache.load('stt',key,self.inputs))
        self.assertEqual(self.manifest.data['checkpoints'][-1]['status'],'invalid')

    def test_semantically_invalid_payload_is_rejected_even_with_valid_digest(self):
        key=self.key();self.cache.store('stt',key,self.inputs,self.transcript,self.provider)
        path=self.cache.path('stt',key);item=json.loads(path.read_text(encoding='utf-8'))
        item['payload']['segments'][0]['end']=10
        item['payload_sha256']=digest(item['payload'])
        path.write_text(json.dumps(item),encoding='utf-8')
        self.assertIsNone(self.cache.load('stt',key,self.inputs))

    def test_disabled_provider_or_moderation_cannot_cache(self):
        self.assertIsNone(self.cache.key('stt', object(), self.inputs))
        self.assertIsNone(self.cache.key('translation', self.provider, self.inputs,disabled=True))
        self.registry._data['entries'][0]['kind']='cloud_api'
        self.assertIsNone(self.cache.key('stt',self.provider,self.inputs))

    def test_path_traversal_rejected(self):
        for stage,key in [('..','a'*64),('stt','../outside'),('speech','a'*64)]:
            with self.assertRaises(ValueError):self.cache.path(stage,key)

    def translation_inputs(self):
        return dict(transcript=self.transcript.to_payload(),target='Hindi',source={'code':'en'},instructions='')

    def test_target_source_text_and_instructions_invalidate_translation(self):
        inputs=self.translation_inputs();key=self.key('translation',inputs)
        for field,value in [('target','French'),('source',{'code':'fr'}),('instructions','changed')]:
            self.assertNotEqual(self.key('translation',dict(inputs,**{field:value})),key)
        other=deepcopy(inputs);other['transcript']['segments'][0]['text']='Changed'
        self.assertNotEqual(self.key('translation',other),key)

    def test_reuse_translation_skips_provider_and_preserves_ids(self):
        subject=ReflowPipeline.__new__(ReflowPipeline);subject._checkpoints=self.cache
        source=resolve_source_language('en')
        first=deepcopy(self.transcript)
        list(subject._translate_cues(first,'Hindi',self.provider,'',None,'',source))
        self.assertEqual(self.provider.calls,1)
        second=deepcopy(self.transcript)
        list(subject._translate_cues(second,'Hindi',self.provider,'',None,'',source))
        self.assertEqual(self.provider.calls,1)
        self.assertEqual(first.to_payload(),second.to_payload())

    def test_partial_translation_never_publishes_checkpoint(self):
        subject=ReflowPipeline.__new__(ReflowPipeline);subject._checkpoints=self.cache
        generator=subject._translate_cues(deepcopy(self.transcript),'Hindi',self.provider,'',None,'',resolve_source_language('en'))
        next(generator);generator.close()
        self.assertFalse(list((self.root/'cache').rglob('*.json')))

    def test_translation_cannot_replace_original_source(self):
        inputs=self.translation_inputs();changed=deepcopy(self.transcript.to_payload())
        changed['segments'][0].update(text='Hindi',translated_text='Hindi',source_text='Changed')
        with self.assertRaises(ValueError):validate_payload(changed,'translation',inputs)

    def test_restart_after_partial_translation_reuses_recognition_and_recomputes_translation(self):
        audio = self.root / 'source.wav'
        with wave.open(str(audio), 'wb') as stream:
            stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(8000)
            stream.writeframes(b'\x01\x00' * 16000)
        self.provider.transcribe = Mock(return_value=TranscriptionResult([
            dict(start=0, end=1, text='Hello.'), dict(start=1, end=2, text='Thanks.')], 'en', .99))
        self.provider.engine_id = 'indictrans2'
        self.provider.release = Mock()
        self.provider.translate = Mock(side_effect=['Hindi: Hello.', RuntimeError('second cue fixture failure')])
        def new_run():
            manifest = RunManifest(self.root/'records', PipelineSpec('audio_dub', {'target_lang':'hi'}),
                                   audio, self.registry, SettingsSnapshot({}))
            manifest.capture_source(audio)
            subject = ReflowPipeline.__new__(ReflowPipeline)
            subject.registry = self.registry
            subject._manifest = manifest
            subject._checkpoints = StageCheckpoints(self.root/'cache', manifest, self.registry, self.root)
            subject.clear_vram = Mock()
            subject._resolve_translation_and_filter = Mock(return_value=(self.provider, '', None, ''))
            return subject, manifest
        first, first_manifest = new_run()
        with patch('core.pipeline.providers.resolve_stt', return_value=self.provider), bind_manifest(first_manifest), self.assertRaisesRegex(RuntimeError, 'second cue fixture failure'):
            first._transcribe_and_translate(str(audio), 'hi', SettingsSnapshot({}), source_language='en')
        self.provider.release.assert_called_once()
        self.assertTrue(any(event['stage']=='stt' and event['status']=='stored' for event in first_manifest.data['checkpoints']))
        self.assertFalse(list((self.root/'cache/translation').glob('*.json')))
        self.provider.translate.side_effect = ['Hindi: Hello.', 'Hindi: Thanks.']
        second, second_manifest = new_run()
        with patch('core.pipeline.providers.resolve_stt', return_value=self.provider), bind_manifest(second_manifest):
            translated = second._transcribe_and_translate(str(audio), 'hi', SettingsSnapshot({}), source_language='en')
        self.provider.transcribe.assert_called_once()
        self.assertEqual(self.provider.translate.call_count, 4)
        self.assertEqual(self.provider.release.call_count, 2)
        self.assertEqual([cue['text'] for cue in translated], ['Hindi: Hello.', 'Hindi: Thanks.'])
        hit = next(event for event in second_manifest.data['checkpoints'] if event['stage']=='stt' and event['status']=='hit')
        self.assertEqual(hit['origin_run_id'], first_manifest.data['run_id'])
        self.assertTrue(any(event['stage']=='translation' and event['status']=='stored' for event in second_manifest.data['checkpoints']))

    def test_recognition_reuse_requires_same_source_hint_and_preserves_origin(self):
        audio = self.root/'hint.wav'
        with wave.open(str(audio), 'wb') as stream:
            stream.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
            stream.writeframes(b'\1\0'*16000)
        self.provider.transcribe = Mock(return_value=TranscriptionResult([
            dict(start=0, end=2, text='नमस्ते।')], 'hi', language_origin='hint'))
        subject = ReflowPipeline.__new__(ReflowPipeline)
        subject._checkpoints = self.cache
        subject._save_cues = Mock()
        first = subject._transcribe_source(self.provider, str(audio), source_language='hi')
        cached = subject._transcribe_source(self.provider, str(audio), source_language='Hindi')
        self.assertEqual(self.provider.transcribe.call_count, 1)
        self.assertEqual(first.to_payload(), cached.to_payload())
        self.assertEqual(cached.language_origin, 'hint')
        self.assertIsNone(cached.language_probability)
        subject._transcribe_source(self.provider, str(audio), source_language='auto')
        self.assertEqual(self.provider.transcribe.call_count, 2)

    def test_translation_checkpoint_cannot_drop_hint_origin(self):
        self.transcript = TranscriptionResult(list(self.transcript), 'hi', language_origin='hint')
        inputs = self.translation_inputs()
        payload = self.transcript.to_payload()
        payload.pop('language_origin')
        with self.assertRaisesRegex(ValueError, 'metadata'):
            validate_payload(payload, 'translation', inputs)


class ReviewIdentityTests(unittest.TestCase):
    def cue(self,start=0,text='Hello'):
        return dict(start=start,end=start+1,source_text=text,text='Translation')

    def test_legacy_upgrade_is_in_memory_and_does_not_invent_translation(self):
        old=dict(id='a'*32,cues=[self.cue()]);before=deepcopy(old)
        new=review.migrate(deepcopy(old));self.assertEqual(old,before)
        contract=new['cues'][0]['cue_contract']
        self.assertFalse(contract['original_source_known']);self.assertIsNone(contract['translated_text'])
        self.assertEqual(review.migrate(deepcopy(before))['cues'][0]['cue_id'],new['cues'][0]['cue_id'])

    def test_edit_keeps_identity_and_original_source(self):
        cue=self.cue();review.attach(cue,'review',0)
        identifier=cue['cue_id'];cue.update(source_text='Corrected',text='Edited',start=.1)
        review.sync(cue);review.validate([cue])
        self.assertEqual(cue['cue_id'],identifier)
        self.assertEqual(cue['cue_contract']['source_text'],'Hello')
        self.assertEqual(cue['cue_contract']['source_start'],0)
        self.assertEqual(cue['cue_contract']['corrected_source_text'],'Corrected')

    def test_combination_retains_parents_and_other_cue_identity(self):
        cues=[self.cue(i,str(i)) for i in range(3)]
        for i,cue in enumerate(cues):review.attach(cue,'review',i)
        parents=[cues[0]['cue_id'],cues[1]['cue_id']];third=deepcopy(cues[2])
        cues[0].update(end=cues[1]['end'],source_text='0 1',text='Combined')
        review.combine(cues[0],cues[1]);review.validate([cues[0],cues[2]])
        self.assertEqual(cues[0]['cue_contract']['parent_ids'],parents)
        self.assertEqual(len(cues[0]['cue_contract']['source_fragments']),2)
        self.assertEqual(cues[2],third)

    def test_duplicate_or_drifting_contract_is_rejected(self):
        cue=self.cue();review.attach(cue,'review',0)
        with self.assertRaises(ValueError):review.validate([cue,deepcopy(cue)])
        cue['text']='drift'
        with self.assertRaises(ValueError):review.validate([cue])


if __name__=='__main__':unittest.main()
