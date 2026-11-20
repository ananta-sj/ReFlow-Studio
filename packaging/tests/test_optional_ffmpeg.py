import hashlib
import json
from pathlib import Path
import tempfile
import unittest


class SharedFFmpegTests(unittest.TestCase):
    def fixture(self, root):
        source=root/'source';(source/'bin').mkdir(parents=True)
        (source/'bin/avcodec.dll').write_bytes(b'reviewed-library')
        (source/'LICENSE').write_bytes(b'reviewed-license')
        recipe=root/'packaging/optional/ffmpeg-shared.json';recipe.parent.mkdir(parents=True)
        recipe.write_text(json.dumps({'files':{str(p.relative_to(source)).replace(chr(92),'/'): {'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in source.rglob('*') if p.is_file()}}))
        profile=root/'runtime_profiles/f5';profile.mkdir(parents=True)
        return source,profile

    def test_verified_libraries_and_license_are_copied(self):
        from dev.optional_ffmpeg import prepare_shared
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source,profile=self.fixture(root)
            result=prepare_shared(root, profile, source)
            self.assertEqual((result/'bin/avcodec.dll').read_bytes(),b'reviewed-library')
            self.assertEqual((result/'LICENSE').read_bytes(),b'reviewed-license')
            self.assertEqual(prepare_shared(root,profile,source),result)

    def test_modified_source_never_creates_ready_directory(self):
        from dev.optional_ffmpeg import prepare_shared
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source,profile=self.fixture(root)
            (source/'bin/avcodec.dll').write_bytes(b'unreviewed')
            with self.assertRaisesRegex(RuntimeError,'identity'):
                prepare_shared(root,profile,source)
            self.assertFalse((profile/'ffmpeg').exists())

    def test_modified_existing_destination_is_not_overwritten(self):
        from dev.optional_ffmpeg import prepare_shared
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source,profile=self.fixture(root)
            result=prepare_shared(root,profile,source)
            (result/'bin/avcodec.dll').write_bytes(b'preserve-mismatch')
            with self.assertRaisesRegex(RuntimeError,'identity'):
                prepare_shared(root,profile,source)
            self.assertEqual((result/'bin/avcodec.dll').read_bytes(),b'preserve-mismatch')
