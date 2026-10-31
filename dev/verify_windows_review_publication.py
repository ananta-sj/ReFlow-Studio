"""Run real review preparation while a disposable review-file handle denies rename."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
TEMP = ROOT / 'temp/tests-dialogue-2026-10-09'
TEMP.mkdir(parents=True, exist_ok=True)
os.environ.update(TEMP=str(TEMP), TMP=str(TEMP), PYTHONIOENCODING='utf-8')
from core.render_context import RenderContext
from dev.test_cue_review import CueReviewTests
from dev.windows_lock_fixture import deny_delete


def main():
    if os.name != 'nt':
        raise RuntimeError('Real Windows handles required')
    original_publish, original_replace = RenderContext.publish, os.replace
    observations = []

    def publish(job, pending, destination):
        if not Path(pending).is_dir():
            return original_publish(job, pending, destination)
        observed = threading.Event()
        errors = []
        def replace(source, target):
            try:
                return original_replace(source, target)
            except PermissionError as exc:
                errors.append(exc.winerror)
                observed.set()
                raise
        with ThreadPoolExecutor(1) as pool, patch('core.render_context.os.replace', side_effect=replace):
            with deny_delete(Path(pending) / 'review.json'):
                future = pool.submit(original_publish, job, pending, destination)
                if not observed.wait(2):
                    raise AssertionError('Expected a real review-directory lock denial')
            future.result(timeout=2)
        observations.append(dict(winerrors=errors, published_review_exists=(Path(destination) / 'review.json').is_file()))

    suite = unittest.TestSuite([CueReviewTests('test_prepare_publishes_owned_audio_snapshot_and_failed_prepare_publishes_nothing')])
    with patch.object(RenderContext, 'publish', side_effect=publish, autospec=True):
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = dict(schema='reflow.review-publication-integration.v1', passed=result.wasSuccessful(),
                  tests_run=result.testsRun, observations=observations,
                  engine_calls='fixture recognition/translation; real media preparation, persistence and Windows handles')
    (ROOT / 'docs/validation/2026-10-09-windows-review-publication-integration.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['passed'] and len(observations) == 1 else 1)


if __name__ == '__main__':
    main()
