"""Read-back and optional recognizer diagnostic; no human-quality assertion."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', REFLOW_OFFLINE='1')
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('receipt', type=Path)
    parser.add_argument('--recognize', action='store_true')
    args = parser.parse_args()
    import numpy as np
    import soundfile as sf
    from pydub import AudioSegment
    from core.cue_review import digest
    from core.pipeline import ReflowPipeline
    from core.providers import resolve
    from core.render_context import RenderContext, bind_job, run_process
    from core import cue_review
    from core.settings import Settings
    report = json.loads(args.receipt.read_text(encoding='utf-8'))
    assert report['completed'] and report['all_14_measured_fit']
    prior = json.loads((ROOT / 'docs/validation/2026-10-08-spoken-hindi-full-video-887151ac.json').read_text(encoding='utf-8'))
    audit = dict(human_quality_accepted=False, receipt=str(args.receipt), receipt_sha256=digest(args.receipt),
                 no_tempo_change=True, baseline_comparisons=[], timing_checks=[])
    baseline = Path(prior['directory']) / prior['output']
    assert digest(baseline) == prior['output_sha256']
    audit.update(approved_baseline_video_unchanged=True, approved_baseline_sha256=prior['output_sha256'])
    for index, row in enumerate(report['cues']):
        assert digest(row['file']) == row['sha256']
        info = sf.info(row['file'])
        assert info.duration <= row['available_seconds'] + .001
        if index < 10:
            old = Path(prior['directory']) / prior['cues'][index]['file']
            assert digest(old) == prior['cues'][index]['result']['output_sha256']
            a, rate_a = sf.read(row['file'], dtype='int16')
            b, rate_b = sf.read(old, dtype='int16')
            audit['baseline_comparisons'].append(dict(cue=index+1,
                speech_pcm_identical=rate_a == rate_b and np.array_equal(a,b)))
    pipe = ReflowPipeline()
    manifest_path = Path(report['review_manifest'])
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    store = cue_review.ReviewStore(manifest_path.parents[2])
    for index in (10, 11):
        result = cue_review.estimate_timing(store,pipe,manifest['id'],manifest['revision'],index,Settings())
        assert result['fits']
        audit['timing_checks'].append(dict(cue=index+1, **result))
    media = json.loads(run_process(['ffprobe','-v','error','-show_streams','-show_format','-of','json',report['output']],capture_output=True,check=True).stdout)
    assert {'video','audio','subtitle'} <= {row['codec_type'] for row in media['streams']}
    assert next(row for row in media['streams'] if row['codec_type']=='subtitle')['tags']['language'] == 'hin'
    audit.update(subtitle_language='hin',duration_seconds=float(media['format']['duration']))
    if args.recognize:
        provider = resolve.resolve_stt(pipe.registry, 'tiny')
        job = RenderContext(ROOT / 'temp')
        try:
            with bind_job(job):
                audio = AudioSegment.from_file(report['cues'][10]['file']) + AudioSegment.silent(duration=200) + AudioSegment.from_file(report['cues'][11]['file'])
                diagnostic = job.workspace / 'rewritten-passages.wav'
                audio.export(diagnostic, format='wav').close()
                result = provider.transcribe(diagnostic)
                audit.update(recognition=result.to_payload(), recognition_raw=provider.last_result,
                    recognition_worker_released=provider.worker_released,
                    scope='Recognizer diagnostic for the two rewritten passages; not a naturalness or synchronization verdict')
        finally:
            job.cleanup()
            audit['recognition_workspace_removed'] = not job.workspace.exists()
    destination = args.receipt.with_name(args.receipt.stem + '-audit.json')
    destination.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(destination, flush=True)


if __name__ == '__main__':
    main()
