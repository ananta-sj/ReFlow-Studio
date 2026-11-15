import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from core import failed_review_state as subject


class FailedReviewStateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.patcher=patch('config.OUTPUT_PATH',str(self.root));self.patcher.start();self.addCleanup(self.patcher.stop)
        self.identifier='a'*32;self.folder=self.root/'run_records'/self.identifier;self.folder.mkdir(parents=True)
        self.path=self.folder/'manifest.json'
        self.path.write_text(json.dumps(dict(run_id=self.identifier,cue_artifacts=[],quality_reports=[])),encoding='utf-8')

    def test_report_is_recovered_by_a_new_bridge_after_restart(self):
        from bridge.api import PythonBridge
        subject.remember(self.path)
        bridge=PythonBridge.__new__(PythonBridge)
        result=bridge.get_failed_render_review()
        self.assertTrue(result['ok'])
        self.assertEqual(Path(result['review']['manifest']),self.path)

    def test_clear_and_deleted_outputs_do_not_recover_a_stale_report(self):
        subject.remember(self.path);self.path.unlink()
        self.assertIsNone(subject.recall())
        subject.clear();self.assertIsNone(subject.recall())

    def test_marker_never_accepts_an_external_path(self):
        external=self.root/'outside'/'manifest.json';external.parent.mkdir()
        external.write_text(json.dumps({'run_id':self.identifier}))
        with self.assertRaises(ValueError):subject.remember(external)

    def test_replaced_manifest_identity_is_rejected(self):
        subject.remember(self.path)
        self.path.write_text(json.dumps({'run_id':'b'*32}))
        with self.assertRaises(ValueError):subject.recall()


if __name__=='__main__':unittest.main()
