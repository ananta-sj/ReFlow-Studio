import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('release_refresh',ROOT/'packaging/refresh_windows_release.py')
refresh=importlib.util.module_from_spec(spec);spec.loader.exec_module(refresh)


class RefreshTests(unittest.TestCase):
    def test_changed_and_unchanged_members_decode_without_duplicates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'old.zip';target=root/'new.zip'
            with zipfile.ZipFile(source,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('first.txt',b'first'*300)
                archive.writestr('changed.txt',b'old')
                archive.writestr('last.bin',bytes(range(256))*100)
            refresh.rewrite_zip(source,target,{'changed.txt':b'new content'*1000})
            with zipfile.ZipFile(source) as old,zipfile.ZipFile(target) as new:
                self.assertEqual(len(new.namelist()),3)
                self.assertIsNone(new.testzip())
                self.assertEqual(new.read('first.txt'),old.read('first.txt'))
                self.assertEqual(new.read('last.bin'),old.read('last.bin'))
                self.assertEqual(new.read('changed.txt'),b'new content'*1000)
                a=old.getinfo('last.bin');b=new.getinfo('last.bin')
                with source.open('rb') as left,target.open('rb') as right:
                    left.seek(a.header_offset);right.seek(b.header_offset)
                    self.assertEqual(left.read(old.start_dir-a.header_offset),right.read(new.start_dir-b.header_offset))

    def test_existing_archive_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'old.zip';target=root/'new.zip'
            with zipfile.ZipFile(source,'w') as archive: archive.writestr('a','a')
            target.write_bytes(b'keep')
            with self.assertRaises(FileExistsError): refresh.rewrite_zip(source,target,{})
            self.assertEqual(target.read_bytes(),b'keep')


if __name__=='__main__': unittest.main()
