"""Meaning-review boundaries, budgets and fail-closed orchestration."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from core.dialogue_supervision import supervise
from core.render_context import RenderContext, RenderCancelled, bind_job
import tempfile
from contextlib import nullcontext


class SupervisionTests(unittest.TestCase):
    def setUp(self):
        self.provider = SimpleNamespace(preserves_native_delivery=True,
            estimate_duration_seconds=lambda text: len(text)/10)
        self.writer = SimpleNamespace(rewrite_dialogue=Mock(return_value=['यह ठीक है।']))
        self.reviewer = SimpleNamespace(review_dialogue=Mock(return_value=[
            dict(id='candidate-1', status='preserved', reasons=['Original assertion retained.'])]))

    def run_review(self, **kwargs):
        return supervise(self.provider, self.writer, self.reviewer,
            'A long original source.', 'यह बहुत लंबा मूल अनुवाद है और इसे पूरा रखा गया है।', 2, **kwargs)

    def test_preserved_opinion_never_accepts_or_changes_original(self):
        result = self.run_review()
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(result['outcome'], 'proposals_need_human_review')
        self.assertFalse(result['auto_rewrite'])
        self.assertTrue(result['human_review_required'])
        self.assertFalse(result['candidates'][0]['approved'])
        self.assertEqual(result['writer_requests']+result['reviewer_requests'], 2)
        self.writer.rewrite_dialogue.assert_called_once()
        self.reviewer.review_dialogue.assert_called_once()
        self.assertEqual(self.reviewer.review_dialogue.call_args.kwargs['source_text'], 'A long original source.')

    def test_fitting_original_spends_no_model_queries(self):
        result = supervise(self.provider,self.writer,self.reviewer,'Source','ठीक है।',2)
        self.assertEqual(result['status'],'fits_prediction')
        self.writer.rewrite_dialogue.assert_not_called()
        self.reviewer.review_dialogue.assert_not_called()

    def test_saved_input_whitespace_is_preserved_exactly(self):
        source='  Original source.  '
        text='  यह मूल अनुवाद बहुत लंबा है और इसे रखना चाहिए।  '
        result=supervise(self.provider,self.writer,self.reviewer,source,text,2)
        self.assertEqual(result['source_text'],source)
        self.assertEqual(result['input_text'],text)

    def test_duplicates_and_original_do_not_create_extra_candidates(self):
        self.writer.rewrite_dialogue.return_value=['यह ठीक है।','यह ठीक है।']
        self.assertEqual(len(self.run_review()['candidates']),1)

    def test_overflow_and_wrong_script_skip_critic(self):
        self.writer.rewrite_dialogue.return_value=['A short line','यह बहुत लंबा वाक्य है '*10]
        result=self.run_review()
        self.assertEqual(result['outcome'],'no_reviewed_fitting_alternative')
        self.reviewer.review_dialogue.assert_not_called()

    def test_number_loss_blocks_critic_even_when_fitting(self):
        result=supervise(self.provider,self.writer,self.reviewer,'There are 42 items.',
            'यहाँ कुल 42 सामान रखे हुए हैं और सबकी गिनती की गई है।',2)
        self.assertTrue(result['candidates'][0]['warnings'])
        self.reviewer.review_dialogue.assert_not_called()

    def test_changed_or_uncertain_meaning_is_not_promoted(self):
        for status in ('changed','uncertain'):
            self.reviewer.review_dialogue.return_value=[dict(id='candidate-1',status=status,reasons=['Uncertain detail.'])]
            self.assertEqual(self.run_review()['outcome'],'no_reviewed_fitting_alternative')

    def test_malformed_critic_outputs_fail_closed(self):
        for value in ([],[{}],[dict(id='other',status='preserved',reasons=['x'])],
                      [dict(id='candidate-1',status='approved',reasons=['x'])],
                      [dict(id='candidate-1',status='preserved',reasons=[])],
                      [dict(id='candidate-1',status='preserved',reasons=['x'*1001])]):
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.reviewer.review_dialogue.return_value=value
                self.run_review()

    def test_duplicate_critic_ids_fail_closed(self):
        self.writer.rewrite_dialogue.return_value=['यह ठीक है।','यह अच्छा है।']
        opinion=dict(id='candidate-1',status='preserved',reasons=['x'])
        self.reviewer.review_dialogue.return_value=[opinion,deepcopy(opinion)]
        with self.assertRaises(ValueError):self.run_review()

    def test_writer_budget_and_invalid_text_fail_without_review(self):
        for value in (['a']*4,[None],[' '],['x'*4001],{}):
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.writer.rewrite_dialogue.return_value=value
                self.run_review()
        self.reviewer.review_dialogue.assert_not_called()

    def test_missing_services_and_language_rejected_before_requests(self):
        with self.assertRaises(ValueError):self.run_review(target_language='ta')
        with self.assertRaises(ValueError):supervise(self.provider,None,self.reviewer,'Source','Target',1)
        self.writer.rewrite_dialogue.assert_not_called()

    def test_service_error_is_not_retried_or_substituted(self):
        self.writer.rewrite_dialogue.side_effect=RuntimeError('endpoint unavailable')
        with self.assertRaisesRegex(RuntimeError,'endpoint unavailable'):self.run_review()
        self.assertEqual(self.writer.rewrite_dialogue.call_count,1)
        self.reviewer.review_dialogue.assert_not_called()

    def test_cancelled_job_does_not_query(self):
        with tempfile.TemporaryDirectory() as folder:
            job=RenderContext(folder)
            try:
                job.request_stop()
                with bind_job(job),self.assertRaises(RenderCancelled):self.run_review()
            finally:job.cleanup()
        self.writer.rewrite_dialogue.assert_not_called()

    def test_durable_report_retains_review_requirement_and_query_operations(self):
        manifest=SimpleNamespace(report=Mock(),operation=Mock(side_effect=lambda *a,**k:nullcontext()))
        result=self.run_review(manifest=manifest)
        manifest.report.assert_called_once_with('dialogue-supervision',result)
        self.assertEqual(result['status'],'needs_review')
        self.assertEqual([call.args[0] for call in manifest.operation.call_args_list],
            ['dialogue-rewrite','dialogue-meaning-review'])

    def test_actual_manifest_saves_report_and_requires_review(self):
        import json
        from pathlib import Path
        from core.run_manifest import RunManifest
        from core.pipeline_contracts import PipelineSpec, RegistrySnapshot, SettingsSnapshot
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.txt'
            source.write_text('Source evidence',encoding='utf-8')
            manifest=RunManifest(Path(folder)/'records',PipelineSpec('video_dub'),source,
                RegistrySnapshot({'entries':[],'active':{}}),SettingsSnapshot({}))
            result=self.run_review(manifest=manifest)
            saved=json.loads(manifest.path.read_text(encoding='utf-8'))
            self.assertTrue(saved['review_required'])
            artifact=saved['quality_reports'][0]
            self.assertEqual(json.loads(Path(artifact['path']).read_text(encoding='utf-8')),result)
            self.assertEqual([o['status'] for o in saved['operations']],['completed','completed'])


if __name__=='__main__':unittest.main()
