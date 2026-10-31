"""No-model checks of explicit selection, version drift and recipe tampering."""
import hashlib,json,os
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from core.xtts_runtime import validate,readiness
from core.providers.tts.xtts_local import XTTSLocalProvider

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.folder=self.root/'runtime_profiles/xtts-security-candidate'
        self.folder.mkdir(parents=True);(self.root/'core').mkdir()
        for name in ('python.exe','python313.dll','python313.zip'):(self.folder/name).write_bytes(name.encode())
        for name in ('xtts_worker.py','xtts_compat.py'):(self.root/'core'/name).write_bytes(name.encode())
        self.lock=self.root/'docs/validation/2026-10-13-xtts-security-cpu-lock-review.json'
        self.lock.parent.mkdir(parents=True);self.lock.write_text(json.dumps({'packages':[{'name':'torch','version':'2.14.1+cpu'}]}))
        meta=self.folder/'Lib/site-packages/torch-2.14.1.dist-info/METADATA';meta.parent.mkdir(parents=True)
        meta.write_text('Name: torch\nVersion: 2.14.1+cpu\n');self.meta=meta
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        self.profile=dict(status='candidate-offline-validated-with-adapter',python='3.13.16',device='cpu',runtime_verified=True,
            real_model_inference_verified=True,persistent_session_verified=True,
            production_adapter_sha256=sha(self.root/'core/xtts_compat.py'),production_worker_sha256=sha(self.root/'core/xtts_worker.py'),
            dependency_lock_sha256=sha(self.lock),production_bootstrap_sha256={n:sha(self.folder/n) for n in ('python.exe','python313.dll','python313.zip')})
        self.save()
    def save(self):(self.folder/'profile.json').write_text(json.dumps(self.profile))
    def test_explicit_valid_trial_has_bound_identity(self):
        self.assertEqual(validate(self.root)['identity'],validate(self.root)['identity'])
        self.assertFalse(readiness(self.root)['release_ready'])
    def test_changed_worker_rejected(self):
        (self.root/'core/xtts_worker.py').write_text('changed')
        self.assertEqual(readiness(self.root)['status'],'unverified')
    def test_changed_bootstrap_rejected(self):
        (self.folder/'python.exe').write_text('changed')
        with self.assertRaisesRegex(RuntimeError,'bootstrap changed'):validate(self.root)
    def test_package_version_drift_rejected(self):
        self.meta.write_text('Name: torch\nVersion: 2.9.1\n')
        with self.assertRaisesRegex(RuntimeError,'package versions'):validate(self.root)
    def test_duplicate_metadata_rejected(self):
        extra=self.meta.parent.with_name('torch-other.dist-info')/'METADATA';extra.parent.mkdir();extra.write_text(self.meta.read_text())
        with self.assertRaisesRegex(RuntimeError,'Duplicate'):validate(self.root)
    def test_unverified_profile_rejected(self):
        self.profile['runtime_verified']=False;self.save()
        self.assertEqual(readiness(self.root)['status'],'unverified')
    def test_legacy_remains_default(self):
        with patch.dict(os.environ,{},clear=True):self.assertEqual(XTTSLocalProvider().runtime,'legacy')
    def test_gpu_not_silently_mapped_to_cpu(self):
        with self.assertRaisesRegex(ValueError,'CPU only'):XTTSLocalProvider(device='cuda',runtime='isolated')
    def test_unknown_selection_rejected(self):
        with self.assertRaises(ValueError):XTTSLocalProvider(runtime='guess')

if __name__=='__main__':unittest.main()
