"""Replay retained actual synthesis through production pacing, without new inference."""
import json
import os
from pathlib import Path
import shutil
import sys
import uuid
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


def main():
    from core.audio_utils import AudioEngineer, load_speech_audio
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, bind_job
    prior = json.loads((ROOT / 'docs/validation/2026-10-04-long-hindi-voice.json').read_text(encoding='utf-8'))
    source = Path(prior['review_directory'])
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-hindi-production-pace-' + uuid.uuid4().hex[:8])
    report = dict(synthesis_rerun=False, synthesis_source=str(source),
                  check='Retained actual XTTS audio through production segment mastering/timing',
                  acceptance=False, cases=[])
    try:
        with bind_job(job):
            folder = job.workspace / 'review'
            folder.mkdir()
            pipeline = ReflowPipeline.__new__(ReflowPipeline)
            pipeline.temp_dir = str(job.workspace)
            pipeline.registry = Mock()
            pipeline.registry.get_active.return_value = None
            pipeline.registry.list.return_value = []
            for case in prior['cases']:
                raw = source / (case['name'] + '-raw.wav')
                approved = load_speech_audio(source / (case['name'] + '-preferred-pace.wav'))
                def replay(text, path, language, reference_audio):
                    if text != case['text'] or language != 'hi':
                        raise RuntimeError('Cached synthesis request differs from the accepted case')
                    shutil.copy2(raw, path)
                    return str(path)
                tts = Mock()
                tts.synthesize.side_effect = replay
                segment = dict(start=0, end=case['raw_duration_ms'] / 1000 + 1, text=case['text'])
                clip = pipeline._dub_segment(0, segment, ['CLONED_USER'], 'hi', tts,
                    {}, None, str(source / 'reference.wav'), 'cpu', AudioEngineer())
                exact = (clip.frame_rate == approved.frame_rate and clip.channels == approved.channels
                         and clip.sample_width == approved.sample_width and clip.raw_data == approved.raw_data)
                if not exact:
                    raise RuntimeError('Production pace does not reproduce the accepted longer preview')
                clip.export(folder / (case['name'] + '.wav'), format='wav').close()
                report['cases'].append(dict(name=case['name'], duration_ms=len(clip),
                                            pcm_matches_approved_preview=True))
            job.publish(folder, destination)
            report.update(acceptance=True, output=str(destination))
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report['workspace_removed'] = not job.workspace.exists()
        (ROOT / 'docs/validation/2026-10-04-hindi-production-pacing.json').write_text(
            json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
