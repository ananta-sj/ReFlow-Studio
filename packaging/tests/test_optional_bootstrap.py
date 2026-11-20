import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from dev.optional_bootstrap import prepare_modern


class OptionalBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.platform = patch("dev.optional_bootstrap.sys.platform", "win32")
        self.machine = patch("dev.optional_bootstrap.platform.machine", return_value="AMD64")
        self.platform.start()
        self.machine.start()
        self.addCleanup(self.platform.stop)
        self.addCleanup(self.machine.stop)

    def test_foreign_host_fails_before_creating_profile(self):
        with tempfile.TemporaryDirectory() as temporary, patch("dev.optional_bootstrap.sys.platform", "linux"):
            root = Path(temporary)
            with self.assertRaisesRegex(RuntimeError, "Windows x64"):
                prepare_modern(root, "musetalk")
            self.assertFalse((root/"runtime_profiles").exists())

    def fixture(self, root, member='python/python.exe'):
        archive = root / 'runtime.tar.gz'
        with tarfile.open(archive, 'w:gz') as bundle:
            payload = b'fixture interpreter'
            info = tarfile.TarInfo(member)
            info.size = len(payload)
            bundle.addfile(info, io.BytesIO(payload))
        recipe = root / 'packaging/optional/python-runtime.json'
        recipe.parent.mkdir(parents=True)
        recipe.write_text(json.dumps(dict(python='3.11.18', bytes=archive.stat().st_size,
            sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), filename=archive.name)), encoding='utf-8')
        return archive

    def test_verified_bundle_has_expected_profile_layout(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self.fixture(root)
            destination = prepare_modern(root, 'musetalk', archive)
            self.assertEqual((destination/'python.exe').read_bytes(), b'fixture interpreter')
            profile = json.loads((destination/'profile.json').read_text())
            self.assertEqual(profile['python'], '3.11.18')
            self.assertEqual(profile['status'], 'prepared')
            paths = (destination/'python311._pth').read_text()
            self.assertIn('Lib/site-packages', paths)
            self.assertNotIn('import site', paths)

    def test_tampering_fails_before_destination_created(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self.fixture(root)
            archive.write_bytes(archive.read_bytes()+b'tampered')
            with self.assertRaisesRegex(RuntimeError, 'identity'):
                prepare_modern(root, 'musetalk', archive)
            self.assertFalse((root/'runtime_profiles/musetalk').exists())

    def test_traversal_cannot_escape_staging(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self.fixture(root, 'python/../../escaped')
            with self.assertRaises((ValueError, RuntimeError)):
                prepare_modern(root, 'musetalk', archive)
            self.assertFalse((root/'escaped').exists())
            self.assertFalse((root/'runtime_profiles/musetalk').exists())

    def test_existing_profile_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self.fixture(root)
            destination = root/'runtime_profiles/musetalk'
            destination.mkdir(parents=True)
            (destination/'keep').write_text('existing')
            with self.assertRaises(FileExistsError):
                prepare_modern(root, 'musetalk', archive)
            self.assertEqual((destination/'keep').read_text(), 'existing')


class OptionalInstallCommandTests(unittest.TestCase):
    def invoke(self, root, with_lock=True, reviewed=True, profile="musetalk"):
        from unittest.mock import patch
        from dev import prepare_optional_runtime as module
        destination = root/'runtime_profiles'/profile
        destination.mkdir(parents=True)
        recipe = root/'packaging/optional/python-runtime.json'
        recipe.parent.mkdir(parents=True)
        recipe.write_text(json.dumps(dict(python='3.11.18', sha256='reviewed-bootstrap')))
        (destination/'profile.json').write_text(json.dumps(dict(profile=profile, status='prepared', python='3.11.18', bootstrap_sha256='reviewed-bootstrap' if reviewed else 'old-bootstrap')))
        lock = root/'packaging/optional'/(profile+'.lock.txt')
        lock.parent.mkdir(parents=True, exist_ok=True)
        if with_lock:
            lock.write_text('# fixture lock')
        if profile == 'f5':
            wheelhouse=root/'build/optional-wheels';wheelhouse.mkdir(parents=True)
            wheel=wheelhouse/'fixture.whl';wheel.write_bytes(b'reviewed-wheel')
            (recipe.parent/'cached-path-compat.json').write_text(json.dumps(dict(filename=wheel.name,sha256=hashlib.sha256(wheel.read_bytes()).hexdigest())))
            (destination/'ffmpeg').mkdir()
            (recipe.parent/'ffmpeg-shared.json').write_text('{"files":{}}')
        def run(command, **kwargs):
            if 'install' in command:
                (destination/'package-install-report.json').write_text('{"install": []}')
        with patch.object(module, 'ROOT', root), patch.object(module.sys, 'argv', ['prepare', profile, '--resume', '--install']), patch.object(module.subprocess, 'run', side_effect=run) as process:
            module.main()
            return process.call_args_list, destination

    def test_package_resolution_uses_profile_interpreter_and_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            calls, destination = self.invoke(Path(temporary))
            command = calls[0].args[0]
            self.assertIn('--python', command)
            self.assertEqual(command[command.index('--python')+1], str(destination/'python.exe'))
            self.assertIn('--require-hashes', command)
            self.assertNotIn('--target', command)
            self.assertNotIn('--ignore-installed', command)

    def test_f5_install_uses_reviewed_wheelhouse_and_profile_interpreter(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            calls,destination=self.invoke(root,profile='f5')
            command=calls[0].args[0]
            self.assertEqual(command[command.index('--python')+1],str(destination/'python.exe'))
            self.assertIn('--require-hashes',command)
            self.assertEqual(command[command.index('--find-links')+1],str(root/'build/optional-wheels'))
            self.assertNotIn('--target',command)

    def test_f5_rejects_legacy_bootstrap_before_package_install(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, 'bootstrap'):
                self.invoke(Path(temporary), reviewed=False, profile='f5')

    def test_resume_rejects_unreviewed_interpreter_before_install(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, 'bootstrap'):
                self.invoke(Path(temporary), reviewed=False)

    def test_missing_reviewed_lock_never_runs_unpinned_install(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, 'lock is missing'):
                self.invoke(Path(temporary), with_lock=False)


class OptionalInventoryTests(unittest.TestCase):
    def test_readiness_rejects_old_or_unreviewed_packages(self):
        from dev.verify_optional_runtime import locked_package_problems
        with tempfile.TemporaryDirectory() as temporary:
            lock = Path(temporary)/'engine.lock'
            lock.write_text('torch==2.15.0+cpu --hash=sha256:fixture\nnumpy==1.26.4 --hash=sha256:fixture\n')
            self.assertEqual(locked_package_problems(lock, {'torch':'2.15.0+cpu','numpy':'1.26.4','pip':'26.2'}), [])
            errors = locked_package_problems(lock, {'torch':'2.7.1','numpy':'1.26.4','unreviewed':'1.0'})
            self.assertTrue(any('torch' in item for item in errors))
            self.assertTrue(any('unreviewed' in item for item in errors))
