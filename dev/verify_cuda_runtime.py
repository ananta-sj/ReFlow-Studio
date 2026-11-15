"""Prove each GPU stage on local media before enabling its application route."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--select', action='store_true')
    parser.add_argument('--source-episode',type=Path)
    args = parser.parse_args()
    from core.cuda_runtime import validate, STAGES
    from core.render_context import RenderContext, bind_job, run_process
    from core.feature_session import FeatureSession
    from core.audio_utils import load_playable_audio, load_speech_audio
    from core.model_registry import ModelRegistry
    from core.transcription import normalize_transcription, require_media_bounds, require_spoken_transcription
    route = validate(candidate=True)
    query = subprocess.run(['nvidia-smi', '--query-gpu=memory.free', '--format=csv,noheader,nounits'],
                           capture_output=True, text=True, check=True)
    if int(query.stdout.splitlines()[0]) < 4096:
        raise RuntimeError('Free at least 4 GB of NVIDIA memory before running model tests.')
    registry = ModelRegistry()
    source = ROOT/'temp/perrine-ep1-check-9299cc6e/baron-41.wav'
    job = RenderContext(ROOT/'temp')
    report = dict(identity=route['identity'], stages={})
    started = time.monotonic()
    try:
        with bind_job(job):
            if not source.is_file():
                queue = json.loads((ROOT/'queue_state.json').read_text(encoding='utf-8'))
                video = args.source_episode or next(Path(item['input_path']) for item in reversed(queue['items'])
                             if Path(item['input_path']).is_file())
                source = job.workspace/'japanese-reference.wav'
                run_process([str(ROOT/'ffmpeg/bin/ffmpeg.exe'), '-v', 'error', '-nostdin', '-y',
                    '-ss', '274', '-i', str(video), '-t', '5', '-vn', '-ac', '1', '-ar', '24000',
                    str(source)], check=True, timeout=60)
            models = dict(speech=registry.get_active('tts')['local_path'],
                          translation=registry.get_active('translation')['local_path'],
                          recognition=str(ROOT/'models/whisper/ct2-turbo-candidate-compat/model'),
                          separate=str(ROOT/'models/uvr'))
            for stage in STAGES:
                print('Testing GPU stage', stage, flush=True)
                worker = FeatureSession(job, route['executable'], dict(stage=stage,
                    model_path=models[stage], session_label='GPU validation '+stage, candidate=True),
                    worker=ROOT/'core/cuda_worker.py', operation='cuda_session')
                try:
                    if stage == 'speech':
                        output = job.workspace/'hindi-number.wav'
                        result = worker.call(dict(text='यह लगभग 100 साल पहले था। मैं 13 साल का हूँ।',
                            language='hi', reference_audio=str(source), output_path=str(output)))
                        duration = len(load_speech_audio(output))/1000
                        if not 0 < duration < 30:
                            raise RuntimeError('GPU speech produced an invalid duration')
                        result['audio_seconds'] = duration
                    elif stage == 'translation':
                        result = worker.call(dict(text='え?', target='Hindi', source='ja'))
                        if result.get('translation') != 'क्या?':
                            raise RuntimeError('GPU translation did not recover the failed Japanese reaction')
                        second = worker.call(dict(text='私は13歳です。', target='Hindi', source='ja'))
                        if '13' not in second['translation'] and 'तेरह' not in second['translation']:
                            raise RuntimeError('GPU translation lost the test number')
                        result['second_translation'] = second['translation']
                    elif stage == 'recognition':
                        result = worker.call(dict(audio_paths=[str(source)], source_language='ja', takes=False))
                        transcript = require_spoken_transcription(normalize_transcription(result['transcriptions'][0]))
                        require_media_bounds(transcript, len(load_playable_audio(source))/1000)
                    else:
                        result = worker.call(dict(audio_path=str(source), output_path=str(job.workspace/'stems')))
                        for role in ('vocals', 'background'):
                            if abs(len(load_playable_audio(result[role]))-len(load_playable_audio(source))) > 50:
                                raise RuntimeError('GPU separation changed the source timeline')
                    if result.get('device') != 'cuda:0':
                        raise RuntimeError('Stage did not confirm CUDA execution')
                    report['stages'][stage] = result
                    print(stage, 'passed on', result['device'], result['gpu_name'], flush=True)
                finally:
                    worker.close()
    finally:
        job.cleanup()
    if validate(candidate=True)['identity'] != report['identity']:
        raise RuntimeError('GPU code or packages changed during testing; the route remains unverified')
    report['elapsed_seconds'] = round(time.monotonic()-started, 2)
    path = ROOT/'runtime_profiles/cuda/profile.json'
    profile = json.loads(path.read_text(encoding='utf-8'))
    profile.update(status='gpu-models-verified', gpu_validation=report)
    pending = path.with_suffix('.pending')
    pending.write_text(json.dumps(profile, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    pending.replace(path)
    for stage in STAGES:
        validate(stage)
    if args.select:
        from core.ui_preferences import UIPreferences
        UIPreferences().update({'reflow.device': 'cuda:0'})
    print('All GPU stages verified.', flush=True)


if __name__ == '__main__':
    main()
