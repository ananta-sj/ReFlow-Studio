"""Real app resolver/provider session test against accepted review PCM."""
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


class Registry:
    def get_active(self, stage):
        if stage == 'tts':
            return dict(stage_type='tts', kind='local_file',
                local_path=str(ROOT / 'models/indicf5/evaluation/assets'), request_preset='indicf5',
                meta={'reference_profile':str(ROOT / 'models/indicf5/references/abhishek/profile.json')})
        return None

    def list(self, stage=None):
        return []


def main():
    import numpy as np
    import soundfile as sf
    from core.providers.resolve import resolve_tts
    from core.providers.tts.indicf5_local import digest
    from core.render_context import RenderContext, bind_job
    from core.speech_language import preflight_speech
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-06-indicf5-app-provider-'+uuid.uuid4().hex[:8])
    prior_path = ROOT / 'docs/validation/2026-10-06-indicf5-gpu-user-voices-2eb79a50.json'
    prior = json.loads(prior_path.read_text(encoding='utf-8'))
    report = dict(completed=False, human_quality_accepted=False, production_provider_tested=True,
                  registry_settings_changed=False, prior_receipt=str(prior_path), cases=[], directory=str(destination))
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            registry = Registry()
            preflight_speech(registry, ['CLONED_USER'], 'hi')
            provider = resolve_tts(registry, 'cuda:0')
            reference = ROOT / 'models/indicf5/references/abhishek/reference.wav'
            for name in ('video-cue-02-sentence-01', 'video-cue-03-sentence-01'):
                expected = next(row for row in prior['cases'] if row['name'] == name)
                original = Path(prior['directory']) / name / 'listening.wav'
                if digest(original) != expected['listening_sha256']:
                    raise ValueError('Prior accepted-video sentence changed')
                output = work / (name+'.wav')
                print('Generating through actual app provider: '+name, flush=True)
                provider.synthesize(expected['text'], str(output), 'hi', str(reference))
                actual, rate = sf.read(output, dtype='int16')
                previous, previous_rate = sf.read(original, dtype='int16')
                if rate != previous_rate or not np.array_equal(actual, previous):
                    raise ValueError('App provider changed the accepted generation recipe/sample output')
                report['cases'].append(dict(case=name, pcm_exact_match=True, seconds=len(actual)/rate,
                    result=provider.last_result, output_sha256=digest(output)))
            if len({row['result']['worker_pid'] for row in report['cases']}) != 1:
                raise ValueError('App provider did not reuse its model worker')
            provider.release()
            if getattr(job, '_indicf5_sessions', {}):
                raise ValueError('Speech stage did not release its sessions')
            report.update(completed=True, one_worker_reused=True, explicit_release_pass=True)
            job.publish(work, destination)
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(), elapsed_seconds=round(time.monotonic()-started, 3))
        destination.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'completed':report['completed'], 'receipt':str(destination.with_suffix('.json')), 'error':report.get('error')}), flush=True)


if __name__ == '__main__':
    main()
