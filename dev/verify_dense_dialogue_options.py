"""Evaluate installed MT alternatives on retained overflowing real cue evidence."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ.update(REFLOW_OFFLINE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONIOENCODING='utf-8')
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='replace')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    from core.model_registry import ModelRegistry
    from core.settings import Settings
    from core.providers import resolve
    from core.dialogue_adaptation import propose
    from core.render_context import RenderContext, bind_job
    origin = next((ROOT / 'docs/validation/2026-10-12-live-workflow-7e72844c/run_records').glob('*/manifest.json'))
    manifest = json.loads(origin.read_text(encoding='utf-8'))
    artifact = next(item for item in manifest['cue_artifacts'] if item['phase'] == 'speech-input')
    if sha(artifact['path']) != artifact['sha256']:
        raise RuntimeError('Original cue artifact changed')
    cue = json.loads(Path(artifact['path']).read_text(encoding='utf-8'))['segments'][0]
    registry = ModelRegistry().snapshot()
    if registry.get_active('translation')['request_preset'] != 'indictrans2':
        raise RuntimeError('Installed translator selection changed')
    state = {name:sha(ROOT / name) for name in ('models.json','settings.json','graph.json','ui_preferences.json','hardware_profile.json')}
    folder = ROOT / 'docs/validation' / ('2026-10-12-dense-options-' + uuid.uuid4().hex[:8])
    folder.mkdir()
    report = dict(completed=False, origin_manifest=str(origin), cue_artifact_sha256=artifact['sha256'],
        source_text=cue['source_text'], translated_text=cue['text'], available_seconds=8,
        incomplete_source_sentence=cue.get('incomplete_sentence_tail',False),
        real_asr_and_translation_evidence_reused=True, fresh_alternative_request=True,
        speech_generated=False, wording_applied=False, human_meaning_accepted=False)
    job = RenderContext(ROOT / 'temp')
    translator = None
    started = time.monotonic()
    try:
        with bind_job(job):
            speech = resolve.resolve_tts(registry,'cpu')
            translator = resolve.resolve_translation(registry,Settings().get('ollama_host'))
            report['original_predicted_seconds'] = speech.estimate_duration_seconds(cue['text'])
            report['options'] = propose(speech, translator, cue['source_text'], cue['text'], 'Hindi','en',8)
            report['worker_result'] = translator.last_result
            report['completed'] = True
    except Exception as error:
        report.update(error_type=type(error).__name__,error=str(error))
    finally:
        if translator is not None:
            if translator.session and translator.session.log.exists():
                (folder/'translation-worker.log').write_bytes(translator.session.log.read_bytes())
            translator.release()
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(), elapsed_seconds=round(time.monotonic()-started,3),
            original_artifact_unchanged=sha(artifact['path'])==artifact['sha256'],
            saved_state_unchanged=state=={name:sha(ROOT/name) for name in state})
        receipt = folder.with_suffix('.json')
        receipt.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('REPORT',receipt,flush=True)
        print(json.dumps(report,ensure_ascii=True,indent=2),flush=True)
    return 0 if report['completed'] and report['saved_state_unchanged'] and report['original_artifact_unchanged'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
