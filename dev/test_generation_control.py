import copy
from pathlib import Path
import tempfile
import unittest
from core.generation_control import generation_kwargs
from core.render_context import RenderContext, RenderCancelled, bind_job


class GenerationControlTests(unittest.TestCase):
    def test_standalone_generation_remains_unchanged(self):
        self.assertEqual(generation_kwargs(), {})

    def test_criteria_copy_retains_job_and_interrupts_next_token(self):
        with tempfile.TemporaryDirectory() as folder:
            job = RenderContext(Path(folder))
            try:
                with bind_job(job):
                    criteria = copy.deepcopy(generation_kwargs()['stopping_criteria'])[0]
                    self.assertFalse(criteria(None, None))
                    job.request_stop()
                    with self.assertRaises(RenderCancelled):
                        criteria(None, None)
            finally:
                job.cleanup()

    def test_already_cancelled_job_does_not_start_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            job = RenderContext(Path(folder))
            try:
                job.request_stop()
                with bind_job(job), self.assertRaises(RenderCancelled):
                    generation_kwargs()
            finally:
                job.cleanup()
