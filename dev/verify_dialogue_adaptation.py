"""Actual native timing and fresh alternatives from preserved real ASR/MT evidence."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ.update(REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')


def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def main():
    from core.pipeline import _preflight_native_cue_durations
    from core.dialogue_adaptation import DialogueReviewRequired, propose
    from core.providers import resolve
    from core.model_registry import ModelRegistry
    from core.settings import Settings
    from core.pipeline_contracts import PipelineSpec,SettingsSnapshot
    from core.run_manifest import RunManifest,bind_manifest
    from core.transcription import normalize_transcription
    from core.source_language import resolve_source_language
    from core.render_context import RenderContext,bind_job
    origin=ROOT/'docs/validation/2026-10-09-stage-checkpoints-500390d0/run_records/5aa34b74e5e54cb8b6d40f9a0b970ff5/manifest.json'
    old=json.loads(origin.read_text(encoding='utf-8'))
    artifact=next(a for a in old['cue_artifacts'] if a['phase']=='speech-input')
    if sha(artifact['path'])!=artifact['sha256']:raise RuntimeError('Preserved cue evidence changed.')
    transcript=normalize_transcription(json.loads(Path(artifact['path']).read_text(encoding='utf-8')))
    before=deepcopy(transcript.to_payload())
    registry=ModelRegistry().snapshot();settings=SettingsSnapshot(Settings().all())
    if registry.get_active('translation')['request_preset']!='indictrans2':raise RuntimeError('Selected translator changed.')
    folder=ROOT/'docs/validation'/('2026-10-09-dialogue-adaptation-'+uuid.uuid4().hex[:8]);folder.mkdir()
    report=dict(origin_manifest=str(origin),origin_manifest_sha256=sha(origin),cue_artifact=artifact,
        reused_real_asr_and_raw_translation=True,fresh_recognition=False,fresh_full_translation=False,
        speech_generated=False,full_video_rendered=False,meaning_or_naturalness_accepted=False,proposals=[])
    state={name:sha(ROOT/name) for name in ('models.json','settings.json')}
    manifest=RunManifest(folder/'run_records',PipelineSpec('video_dub',dict(target_lang='hi',keep_background=False)),
        old['source']['path'],registry,settings);manifest.capture_source(old['source']['path'])
    job=RenderContext(ROOT/'temp');translator=None;started=time.monotonic()
    try:
        with bind_job(job),bind_manifest(manifest):
            tts=resolve.resolve_tts(registry,'cpu')
            try:_preflight_native_cue_durations(tts,transcript,['CLONED_USER'])
            except DialogueReviewRequired as error:report['assessment']=error.report
            else:raise RuntimeError('Expected documented raw-translation overflow.')
            translator=resolve.resolve_translation(registry,settings.get('ollama_host'))
            source=resolve_source_language('auto',transcript.language,transcript.language_probability)
            for assessment in [c for c in report['assessment']['cues'] if c['status']=='needs_review'][:3]:
                cue=transcript[assessment['index']]
                with manifest.operation('dialogue-options',translator,evidence=dict(cue_id=cue['cue_id'],candidate_limit=3)):
                    options=propose(tts,translator,cue['source_text'],cue['text'],'Hindi',source,assessment['available_seconds'])
                report['proposals'].append(dict(cue_id=cue['cue_id'],index=assessment['index'],options=options,
                    worker_result=deepcopy(translator.last_result)))
                print('CUE',assessment['index']+1,'alternatives',len(options['candidates']),
                    'fitting',sum(c['fits'] for c in options['candidates']),flush=True)
            manifest.cues('unchanged-speech-input',transcript)
            manifest.finish('needs_review')
    finally:
        if translator is not None:
            if translator.session is not None and translator.session.log.exists():
                (folder/'translation-worker.log').write_bytes(translator.session.log.read_bytes())
            translator.release()
        job.cleanup()
    report.update(elapsed_seconds=time.monotonic()-started,manifest_path=str(manifest.path),
        source_text_and_translation_unchanged=before==transcript.to_payload(),workspace_removed=not job.workspace.exists(),
        saved_state_unchanged=state=={name:sha(ROOT/name) for name in state},
        all_conflicts_assessed=len(report['assessment']['cues'])==14)
    report['passed']=all(report[k] for k in ('source_text_and_translation_unchanged','workspace_removed','saved_state_unchanged','all_conflicts_assessed'))
    report['passed'] &= all(len(p['options']['candidates'])<=3 and p['options']['human_review_required'] for p in report['proposals'])
    files=['core/dialogue_adaptation.py','core/pipeline.py','core/run_manifest.py','core/indictrans2_worker.py','core/providers/translation/indictrans2_local.py','core/cue_review.py']
    report['implementation_sha256']={name:sha(ROOT/name) for name in files}
    path=folder.with_suffix('.json');path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('REPORT',path,'passed=',report['passed'],flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
