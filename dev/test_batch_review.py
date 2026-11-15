import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.batch_review import publish


class BatchReviewTests(unittest.TestCase):
    def timing_fixture(self,folder,audio_bytes=b'retained take'):
        import hashlib
        audio=folder/'candidate.wav';audio.write_bytes(audio_bytes)
        evidence=folder/'timing.json'
        payload=dict(cue_id='a',index=0,start=1,end=3,measured_seconds=2.3,
            available_seconds=2.,excess_seconds=.3,
            candidate=dict(path=str(audio),bytes=audio.stat().st_size,
                           sha256=hashlib.sha256(audio.read_bytes()).hexdigest()))
        evidence.write_text(json.dumps(payload),encoding='utf-8')
        manifest=folder/'manifest.json'
        manifest.write_text(json.dumps(dict(quality_reports=[dict(kind='measured-speech-timing',
            path=str(evidence),sha256=hashlib.sha256(evidence.read_bytes()).hexdigest())])),encoding='utf-8')
        return manifest,audio,evidence

    def test_retained_timing_take_is_exposed_with_measured_gap_without_acceptance(self):
        from core.batch_review import build,timing_candidate
        with tempfile.TemporaryDirectory() as directory:
            manifest,audio,_=self.timing_fixture(Path(directory))
            report=build(manifest);row=report['cues'][0]
            self.assertTrue(row['has_saved_take']);self.assertEqual(row['timing']['excess_seconds'],.3)
            self.assertFalse(report['human_quality_accepted'])
            self.assertEqual(timing_candidate(manifest,'a'),audio.read_bytes())
            audio.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'take changed'):timing_candidate(manifest,'a')

    def test_modified_timing_evidence_and_unrelated_cue_are_rejected(self):
        from core.batch_review import timing_candidate
        with tempfile.TemporaryDirectory() as directory:
            manifest,_,evidence=self.timing_fixture(Path(directory))
            with self.assertRaisesRegex(ValueError,'No saved timing'):timing_candidate(manifest,'other')
            evidence.write_text('{}',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'evidence changed'):timing_candidate(manifest,'a')

    def test_bridge_serves_saved_wav_without_regeneration_and_rejects_external_run(self):
        import io,wave
        from bridge.api import PythonBridge
        buffer=io.BytesIO()
        with wave.open(buffer,'wb') as audio:
            audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(24000)
            audio.writeframes(b'\x01\x00'*2400)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'outputs/run_records'/('a'*32);folder.mkdir(parents=True)
            manifest,_,_=self.timing_fixture(folder,buffer.getvalue())
            bridge=PythonBridge.__new__(PythonBridge);bridge._last_run_manifest_path=str(manifest)
            with patch('bridge.api.config.OUTPUT_PATH',str(root/'outputs')):
                response=bridge.get_failed_render_take('a')
                self.assertTrue(response['ok']);self.assertTrue(response['audio'].startswith('data:audio/wav;base64,'))
                bridge._last_run_manifest_path=str(root/'private/manifest.json')
                self.assertFalse(bridge.get_failed_render_take('a')['ok'])

    def test_saved_take_path_cannot_escape_its_run_even_with_valid_checksum(self):
        import hashlib
        from core.batch_review import timing_candidate
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'run';folder.mkdir()
            manifest,audio,evidence=self.timing_fixture(folder)
            outside=root/'private.wav';outside.write_bytes(audio.read_bytes())
            payload=json.loads(evidence.read_text(encoding='utf-8'))
            payload['candidate']['path']=str(outside)
            evidence.write_text(json.dumps(payload),encoding='utf-8')
            record=json.loads(manifest.read_text(encoding='utf-8'))
            record['quality_reports'][0]['sha256']=hashlib.sha256(evidence.read_bytes()).hexdigest()
            manifest.write_text(json.dumps(record),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'take must belong'):timing_candidate(manifest,'a')

    def test_successful_recheck_supersedes_an_old_readback_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            old, new = folder/'old.json', folder/'new.json'
            old.write_text(json.dumps(dict(status='needs_review', error={'type':'RuntimeError'},
                reason='speech_readback_unavailable', cues=[dict(cue_id='a', index=0)])), encoding='utf-8')
            new.write_text(json.dumps(dict(status='passed_readback', cues=[dict(cue_id='a', index=0,
                status='passed_readback', observed='Hello')])), encoding='utf-8')
            manifest = folder/'manifest.json'
            manifest.write_text(json.dumps(dict(quality_reports=[dict(kind='batch-intelligibility', path=str(path))
                for path in (old,new)])), encoding='utf-8')
            report = publish(manifest, folder/'result.mp4')
            self.assertEqual(report['cues'], [])
            self.assertFalse(report['human_quality_accepted'])

    def test_flagged_lines_keep_their_words_times_and_readback(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            cues = folder/'cues.json'
            cues.write_text(json.dumps(dict(segments=[dict(cue_id='a', start=2, end=4, text='Hello', source_text='こんにちは')]))
                            , encoding='utf-8')
            check = folder/'check.json'
            check.write_text(json.dumps(dict(status='needs_review', cues=[dict(cue_id='a', index=0,
                status='needs_review', observed='Other words')])) , encoding='utf-8')
            manifest = folder/'manifest.json'
            manifest.write_text(json.dumps(dict(cue_artifacts=[dict(phase='speech-input', path=str(cues))],
                quality_reports=[dict(kind='batch-intelligibility', path=str(check))])), encoding='utf-8')
            report = publish(manifest, folder/'result.mp4')
            self.assertEqual(report['status'], 'needs_review')
            self.assertEqual(report['cues'][0]['start'], 2)
            self.assertEqual(report['cues'][0]['text'], 'Hello')
            self.assertEqual(report['cues'][0]['observed'], 'Other words')
            self.assertFalse(report['human_quality_accepted'])

    def test_bridge_refuses_reports_outside_outputs(self):
        from bridge.api import PythonBridge
        bridge = PythonBridge.__new__(PythonBridge)
        with tempfile.TemporaryDirectory() as folder, patch('bridge.api.config.OUTPUT_PATH', str(Path(folder)/'outputs')):
            outside = Path(folder)/'private.mp4'
            outside.write_bytes(b'file')
            response = bridge.get_render_review(str(outside))
            self.assertFalse(response['ok'])
