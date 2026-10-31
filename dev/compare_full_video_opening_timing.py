"""Compare raw translation and previously accepted concise opening; no tempo changes."""
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'REFLOW_OFFLINE'):
    os.environ[key] = '1'


class Registry:
    def get_active(self, stage):
        if stage == 'tts':
            return dict(stage_type='tts', kind='local_file', request_preset='indicf5',
                        local_path=str(ROOT / 'models/indicf5/evaluation/assets'),
                        meta={'reference_profile':str(ROOT / 'models/indicf5/references/abhishek/profile.json'),
                              'speech_device':'cuda:0'})
        return None

    def list(self, stage=None):
        return []


def main():
    import soundfile as sf
    from core.providers.resolve import resolve_tts
    from core.providers.tts.indicf5_local import digest
    from core.render_context import RenderContext, bind_job
    raw = json.loads((ROOT / 'docs/validation/2026-10-08-indictrans2-full-video-translation.json').read_text(encoding='utf-8'))
    editorial_path = ROOT / 'docs/validation/2026-10-06-video-hindi-editorial-draft.json'
    accepted = json.loads((ROOT / 'docs/validation/2026-10-06-video-hindi-editorial-acceptance.json').read_text(encoding='utf-8'))
    assert accepted['human_translation_accepted'] and digest(editorial_path) == accepted['draft_sha256']
    editorial = json.loads(editorial_path.read_text(encoding='utf-8'))
    destination = ROOT / 'docs/validation' / ('2026-10-08-opening-timing-'+uuid.uuid4().hex[:8])
    report = dict(completed=False, human_quality_accepted=False, production_changed=False,
                  voice='Abhishek', tempo_changed=False, available_seconds=6.4, cases=[], directory=str(destination))
    job = RenderContext(ROOT / 'temp')
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            provider = resolve_tts(Registry(), 'cpu')
            reference = ROOT / 'models/indicf5/references/abhishek/reference.wav'
            try:
                for name, text, origin in (
                    ('raw-opening', raw['cases'][0]['translation'], 'raw IndicTrans2'),
                    ('concise-opening', editorial['cues'][0]['text'], 'previously accepted editorial wording')):
                    output = work / (name+'.wav')
                    provider.synthesize(text, str(output), 'hi', str(reference))
                    info = sf.info(str(output))
                    seconds = info.frames/info.samplerate
                    report['cases'].append(dict(name=name, text=text, origin=origin, seconds=seconds,
                        fits_window=seconds <= 6.4, file=output.name, sha256=digest(output), result=provider.last_result))
                    print(json.dumps(dict(name=name, seconds=seconds, fits_window=seconds <= 6.4)), flush=True)
            finally:
                provider.release()
            report['completed'] = True
            (work / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            job.publish(work, destination)
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        job.cleanup()
        report.update(elapsed_seconds=round(time.monotonic()-started,3), workspace_removed=not job.workspace.exists())
        destination.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(dict(completed=report['completed'], receipt=str(destination.with_suffix('.json')))), flush=True)


if __name__ == '__main__':
    main()
