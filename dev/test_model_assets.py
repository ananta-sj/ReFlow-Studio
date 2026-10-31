"""Offline regression checks for feature-scoped model recovery."""
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import tempfile
import unittest
import hashlib
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import model_assets
from core.integrity import IntegrityDoctor

class ModelAssetsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(model_assets.ASSETS, {'test': [('weights/model.bin', 'https://example.org/model', 3)]}))
        self.stack.enter_context(patch.dict(os.environ, {'REFLOW_OFFLINE': '0'}))
        self.get = self.stack.enter_context(patch('requests.get'))
        self.response = MagicMock()
        self.response.headers = {'Content-Length': '3', 'Content-Type': 'application/octet-stream'}
        self.response.iter_content.return_value = [b'abc']
        self.get.return_value.__enter__.return_value = self.response

    def test_atomic_success(self):
        target, = model_assets.ensure_assets('test', root=self.root)
        self.assertEqual(target.read_bytes(), b'abc')
        self.assertFalse(target.with_name('model.bin.download').exists())

    def test_existing_valid_model_does_not_contact_network(self):
        target = self.root / 'weights/model.bin'
        target.parent.mkdir()
        target.write_bytes(b'abc')
        model_assets.ensure_assets('test', root=self.root)
        self.get.assert_not_called()

    def test_incomplete_transfer_is_not_installed(self):
        self.response.iter_content.return_value = [b'ab']
        with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
            model_assets.ensure_assets('test', root=self.root)
        self.assertFalse((self.root / 'weights/model.bin').exists())
        self.assertFalse((self.root / 'weights/model.bin.download').exists())

    def test_wrong_asset_size_preserves_prior_file(self):
        target = self.root / 'weights/model.bin'
        target.parent.mkdir()
        target.write_bytes(b'prior incomplete asset')
        self.response.headers['Content-Length'] = '4'
        self.response.iter_content.return_value = [b'abcd']
        with self.assertRaisesRegex(RuntimeError, 'asset size'):
            model_assets.ensure_assets('test', root=self.root)
        self.assertEqual(target.read_bytes(), b'prior incomplete asset')

    def test_failed_transfer_preserves_old_file(self):
        target = self.root / 'weights/model.bin'
        target.parent.mkdir()
        target.write_bytes(b'old incomplete')
        self.response.iter_content.side_effect = OSError('transfer interrupted')
        with self.assertRaises(OSError):
            model_assets.ensure_assets('test', root=self.root)
        self.assertEqual(target.read_bytes(), b'old incomplete')
        self.assertFalse(target.with_name('model.bin.download').exists())

    def test_checksum_failure_preserves_prior_asset(self):
        from core.downloader import download_with_progress
        target = self.root / 'model.bin'
        target.write_bytes(b'prior')
        with self.assertRaisesRegex(RuntimeError, 'checksum'):
            list(download_with_progress('https://example.org/model', str(target),
                expected_sha256=hashlib.sha256(b'wrong').hexdigest()))
        self.assertEqual(target.read_bytes(), b'prior')
        self.assertEqual(list(self.root.glob('.model-download-*')), [])

    def test_checksum_checks_existing_same_size_assets(self):
        target = self.root / 'model.bin'
        target.write_bytes(b'abc')
        self.assertTrue(model_assets._valid(target, 3, hashlib.sha256(b'abc').hexdigest()))
        self.assertFalse(model_assets._valid(target, 3, hashlib.sha256(b'xyz').hexdigest()))

    def test_offline_missing_model_has_recovery_instruction(self):
        with patch.dict(os.environ, {'REFLOW_OFFLINE': '1'}):
            with self.assertRaisesRegex(RuntimeError, 'restore_models'):
                model_assets.ensure_assets('test', root=self.root)
        self.get.assert_not_called()

    def test_html_error_page_is_not_installed(self):
        self.response.headers['Content-Type'] = 'text/html'
        with self.assertRaisesRegex(RuntimeError, 'HTML'):
            model_assets.ensure_assets('test', root=self.root)
        self.assertFalse((self.root / 'weights/model.bin').exists())

    def test_http_failure_is_not_installed(self):
        self.response.raise_for_status.side_effect = RuntimeError('HTTP failure')
        with self.assertRaisesRegex(RuntimeError, 'HTTP failure'):
            model_assets.ensure_assets('test', root=self.root)
        self.assertFalse((self.root / 'weights/model.bin').exists())

    def test_startup_integrity_does_not_download_models(self):
        doctor = IntegrityDoctor()
        with patch.object(doctor, 'check_libraries'), patch.object(doctor, 'check_models') as downloads:
            doctor.run_all_checks()
            downloads.assert_not_called()
            doctor.run_all_checks(include_models=True)
            downloads.assert_called_once()

    def test_restore_registry_preserves_selections_and_unrelated_entries(self):
        from dev.restore_models import record_restored
        entry = dict(id='voice', stage_type='tts', kind='local_file', display_name='XTTS',
                     source_url='https://huggingface.co/coqui/XTTS-v2', status='missing', meta={})
        other = dict(id='other', stage_type='translation', kind='local_file', display_name='Other', meta={})
        saved = dict(entries=[entry, other], active={'tts': 'voice', 'translation': 'other'})
        path = self.root / 'models.json'
        path.write_text(json.dumps(saved), encoding='utf-8')
        record_restored('xtts', self.root)
        restored = json.loads(path.read_text())
        self.assertEqual(restored['active'], saved['active'])
        self.assertEqual(restored['entries'][1], other)
        self.assertEqual(restored['entries'][0]['status'], 'installed')

    def test_restore_registry_failed_publication_preserves_saved_bytes(self):
        from dev.restore_models import record_restored
        path = self.root / 'models.json'
        original = b'{"entries": [], "active": {}}'
        path.write_bytes(original)
        with patch('core.json_store.atomic_bytes', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                record_restored('xtts', self.root)
        self.assertEqual(path.read_bytes(), original)

if __name__ == '__main__':
    unittest.main(verbosity=2)
