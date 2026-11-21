"""Pinned inference subset validation with synthetic files; no transfers."""
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest


class MarketplaceRecipeTests(unittest.TestCase):
    def test_supported_recipe_excludes_duplicate_weights_and_optimizer(self):
        from core.download_recipes import repository_download_recipe
        recipe=repository_download_recipe('filter','https://huggingface.co/Falconsai/nsfw_image_detection','image_classifier')
        self.assertEqual(len(recipe['revision']),40)
        self.assertEqual(set(recipe['files']),{'config.json','preprocessor_config.json','model.safetensors','README.md'})
        self.assertEqual(recipe['files']['model.safetensors']['bytes'],343223968)
        self.assertIsNone(repository_download_recipe('stt','https://huggingface.co/another/repo','custom'))

    def test_runtime_inventory_contains_recipe(self):
        import runpy
        inventory=runpy.run_path('packaging/build_portable.py')
        self.assertIn('packaging/downloads/falconsai-image-classifier.json',inventory['ROOT_FILES'])

    def test_equivalent_repo_url_retains_reviewed_subset(self):
        from core.download_recipes import repository_download_recipe
        self.assertIsNotNone(repository_download_recipe('filter','https://huggingface.co/Falconsai/nsfw_image_detection/?download=true','image_classifier'))

    def test_child_transfer_error_codes_are_bounded(self):
        from core.download_failures import DownloadTransferFailure, describe_download_failure
        for code in ('access_denied','network_error','storage_error'):
            self.assertEqual(describe_download_failure(DownloadTransferFailure(code))['code'],code)
        self.assertEqual(describe_download_failure(DownloadTransferFailure('SENTINEL'))['code'],'transfer_failed')

    def test_worker_serializes_and_parent_recovers_transport_failures(self):
        import errno, json, runpy, subprocess, sys
        from unittest.mock import patch
        import requests
        from core import downloader
        from core.download_failures import describe_download_failure
        denied=requests.HTTPError('SENTINEL');denied.response=SimpleNamespace(status_code=403)
        for error,code in [(denied,'access_denied'),(requests.Timeout('SENTINEL'),'network_error'),(OSError(errno.ENOSPC,'SENTINEL'),'storage_error')]:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as folder:
                def child(args, **kwargs):
                    def transfer(**kwargs):raise error
                    with patch.dict(sys.modules, {'huggingface_hub':SimpleNamespace(snapshot_download=transfer)}), patch.object(sys,'argv',['worker',args[-1]]):
                        try:runpy.run_path('core/run_hf_download.py',run_name='__main__')
                        except Exception:raise subprocess.CalledProcessError(1,args)
                metadata=SimpleNamespace(model_info=lambda *a,**kw:SimpleNamespace(siblings=[]))
                with patch.dict(sys.modules, {'huggingface_hub':SimpleNamespace(HfApi=lambda:metadata)}), patch.object(downloader,'require_hub_transport'), patch.object(downloader,'run_process',side_effect=child):
                    with self.assertRaises(Exception) as caught:list(downloader._snapshot_progress('fixture/repo',folder))
                self.assertEqual(describe_download_failure(caught.exception)['code'],code)
                self.assertNotIn('SENTINEL',str(caught.exception))

    def test_missing_required_metadata_aborts(self):
        from core.download_recipes import validate_snapshot_metadata
        with self.assertRaisesRegex(RuntimeError,'metadata'):
            validate_snapshot_metadata(SimpleNamespace(sha='a'*40,siblings=[]),'a'*40,{'model.safetensors':{'bytes':4,'sha256':'b'*64}})

    def test_hash_mismatch_does_not_accept_file(self):
        from core.download_recipes import validate_snapshot_files
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'model.safetensors';path.write_bytes(b'wrong')
            with self.assertRaisesRegex(RuntimeError,'identity'):
                validate_snapshot_files(folder,{'model.safetensors':{'bytes':5,'sha256':hashlib.sha256(b'right').hexdigest()}})
            self.assertEqual(path.read_bytes(),b'wrong')

    def test_valid_snapshot_and_metadata_are_accepted(self):
        from core.download_recipes import validate_snapshot_metadata,validate_snapshot_files
        expected={'config.json':{'bytes':2,'sha256':hashlib.sha256(b'{}').hexdigest(),'blob_id':'blob'}}
        validate_snapshot_metadata(SimpleNamespace(sha='a'*40,siblings=[SimpleNamespace(rfilename='config.json',size=2,blob_id='blob')]),'a'*40,expected)
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'config.json').write_bytes(b'{}');validate_snapshot_files(folder,expected)


if __name__=='__main__':unittest.main()
