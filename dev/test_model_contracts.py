"""Selection, owned installation and grouped-output regression checks."""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import zipfile

import torch
import pipeline
from core import marketplace, render_state
from core.model_contract import local_contract
from core.model_registry import ModelRegistry
from core.providers import resolve
from core.providers.voice import rvc_local
from core.providers.enhancer import gfpgan_local


class ModelContracts(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))

    def checkpoint(self, name='voice.pth', version='v2'):
        path = self.root / name
        torch.save({'config': [0] * 18, 'version': version,
                    'weight': {'emb_g.weight': torch.zeros(1, 1),
                               'enc_p.emb_phone.weight': torch.zeros(1, 256 if version == 'v1' else 768)}}, path)
        return path

    def registry(self, entry):
        registry = Mock()
        registry.get_active.return_value = entry
        registry.list.return_value = [entry] if entry else []
        return registry

    def test_missing_selected_checkpoint_has_no_default_fallback(self):
        for stage, function, arguments in (
            ('stt', resolve.resolve_stt, ['tiny']), ('tts', resolve.resolve_tts, ['cpu']),
            ('translation', resolve.resolve_translation, ['http://localhost:11434']),
            ('enhancer', resolve.resolve_enhancer, ['cpu', 1]),
            ('lipsync', resolve.resolve_lipsync, ['cpu']), ('filter', resolve.resolve_filter, ['cpu'])):
            entry = dict(id='missing', stage_type=stage, kind='local_file', local_path=None)
            with self.subTest(stage=stage), self.assertRaisesRegex(ValueError, 'installed artifact'):
                function(self.registry(entry), *arguments)

    def test_rvc_versions_and_embedded_contract(self):
        for version in ('v1', 'v2'):
            path = self.checkpoint(version + '.pth', version)
            self.assertEqual(local_contract('voice', str(path))['rvc_version'], version)
        path = self.root / 'training.pth'
        torch.save({'model': {}}, path)
        with self.assertRaisesRegex(ValueError, 'inference checkpoint'):
            local_contract('voice', str(path))

    def test_selected_voice_uses_checkpoint_and_index(self):
        path = self.checkpoint()
        index = self.root / 'voice.index'
        index.write_bytes(b'retrieval index')
        entry = dict(id='unique', display_name='friendly', stage_type='voice', kind='local_file',
                     local_path=str(path), meta={'index_path': str(index)})
        provider = resolve.resolve_voice_for_actor(self.registry(entry), 'unique', 'cpu')
        self.assertIsInstance(provider, rvc_local.RVCLocalProvider)
        self.assertEqual(provider.model_path, str(path))
        self.assertEqual(provider.index_path, str(index))
        self.assertEqual(provider.version, 'v2')

    def test_duplicate_voice_alias_rejected_but_ids_remain_selectable(self):
        registry = Mock()
        registry.list.return_value = [dict(id='one', display_name='Actor'), dict(id='two', display_name='Actor')]
        self.assertEqual(resolve.voice_entry(registry, 'two')['id'], 'two')
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            resolve.voice_entry(registry, 'Actor')

    def test_selected_enhancer_binds_checkpoint(self):
        path = self.root / 'custom.pth'
        path.write_bytes(b'checkpoint')
        entry = dict(stage_type='enhancer', kind='local_file', local_path=str(path))
        provider = resolve.resolve_enhancer(self.registry(entry), 'cpu', 2)
        self.assertIsInstance(provider, gfpgan_local.GFPGANLocalProvider)
        self.assertEqual(provider.model_path, str(path))

    def test_owned_voice_install_preserves_original_and_other_models(self):
        path = self.checkpoint()
        other = self.root / 'custom' / path.name
        other.parent.mkdir()
        other.write_bytes(b'custom model must remain')
        name, installed = marketplace.install_downloaded_voice_model(str(path))
        self.assertEqual(installed, str(path))
        self.assertEqual(name, 'voice')
        self.assertEqual(other.read_bytes(), b'custom model must remain')
        self.assertTrue(path.exists())

    def test_ambiguous_voice_archive_cannot_choose_last_weight(self):
        archive = self.root / 'models.zip'
        with zipfile.ZipFile(archive, 'w') as stream:
            stream.writestr('first.pth', b'one')
            stream.writestr('second.pth', b'two')
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            marketplace.install_downloaded_voice_model(str(archive))
        self.assertTrue(archive.exists())

    def test_wrong_stage_and_uninstalled_entries_cannot_activate(self):
        self.stack.enter_context(patch('core.model_registry.REGISTRY_PATH', str(self.root / 'models.json')))
        registry = ModelRegistry()
        entry = registry.add('voice', 'local_file', 'pending')
        with self.assertRaises(ValueError):
            registry.set_active('voice', entry['id'])
        with self.assertRaises(ValueError):
            registry.set_active('tts', entry['id'])

    def test_bundle_failure_publishes_no_partial_files(self):
        output = self.root / 'render.wav'
        with self.assertRaisesRegex(RuntimeError, 'stem failed'):
            with pipeline._staged_bundle(str(output)) as pending:
                Path(pending).write_bytes(b'main render')
                Path(pending).with_name('render_stem_vocals.wav').write_bytes(b'vocals')
                raise RuntimeError('stem failed')
        self.assertEqual(list(self.root.iterdir()), [])

    def test_bundle_publication_is_complete_and_collision_safe(self):
        output = self.root / 'render.wav'
        with pipeline._staged_bundle(str(output)) as pending:
            Path(pending).write_bytes(b'main')
            Path(pending).with_name('render_stem_vocals.wav').write_bytes(b'vocals')
        published = Path(pipeline._bundle_path(str(output)))
        self.assertEqual(published.read_bytes(), b'main')
        self.assertEqual((published.parent / 'render_stem_vocals.wav').read_bytes(), b'vocals')
        with self.assertRaisesRegex(RuntimeError, 'preserved'):
            with pipeline._staged_bundle(str(output)):
                self.fail('existing bundle must be refused')
        self.assertEqual(published.read_bytes(), b'main')

    def test_bundle_publication_failure_cleans_staging(self):
        with patch.object(pipeline.os, 'replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                with pipeline._staged_bundle(str(self.root / 'render.wav')) as pending:
                    Path(pending).write_bytes(b'main')
        self.assertEqual(list(self.root.iterdir()), [])

    def test_recovery_reads_repeat_and_stale_ack_preserves_new_record(self):
        with patch.object(render_state, 'STATE_PATH', str(self.root / 'render.json')):
            render_state.mark_started('old.mp4', {}, 'video_dub')
            first = render_state.get_interrupted()
            self.assertEqual(render_state.get_interrupted(), first)
            render_state.mark_started('new.mp4', {}, 'video_dub')
            self.assertFalse(render_state.discard(first['recovery_token']))
            newest = render_state.get_interrupted()
            self.assertEqual(newest['input_path'], 'new.mp4')
            self.assertTrue(render_state.discard(newest['recovery_token']))
            self.assertIsNone(render_state.get_interrupted())


if __name__ == '__main__':
    unittest.main()
