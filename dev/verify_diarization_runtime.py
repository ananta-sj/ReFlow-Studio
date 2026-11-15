"""Verify real, unforced speaker detection and reference extraction before enabling it."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]


def main():
    import psutil
    from pydub import AudioSegment
    from core.diarization_runtime import validate
    from core.diarization import validate_turns, references
    from core.render_context import RenderContext, bind_job, run_process
    source = ROOT/'outputs/episode1-original-native-context-80-380.wav'
    route = validate(candidate=True)
    job = RenderContext(ROOT/'temp')
    destination = ROOT/'docs/validation/community-speaker-probe-2026-11-13'
    destination.mkdir(exist_ok=True)
    try:
        with bind_job(job), (destination/'worker.log').open('wb') as log:
            if not source.is_file():
                source=job.workspace/'source-context.wav'
                episode=next(Path(r'C:\Users\19shr\Downloads\New folder').glob('*Perrine HD 01*'))
                run_process([str(ROOT/'ffmpeg/bin/ffmpeg.exe'),'-v','error','-nostdin','-y','-ss','80',
                    '-i',str(episode),'-t','300','-vn','-ar','44100','-ac','2',str(source)],check=True,timeout=120)
            result_path = job.workspace/'speaker-result.json'
            cue_file=job.workspace/'probe-captions.json'
            cue_file.write_text(json.dumps([
                dict(cue_id='mother-long',start=140.678,end=143.264,text='母'),
                dict(cue_id='daughter-long',start=151.773,end=154.859,text='娘'),
                dict(cue_id='mother-short',start=163.117,end=164.744,text='母'),
            ]),encoding='utf-8')
            run_process([route['executable'], '-B', str(ROOT/'core/diarization_worker.py'), str(source),
                str(result_path), '--device', 'cuda:0', '--probe','--cues',str(cue_file)], stdout=log, stderr=log,
                check=True, timeout=1800, env={**os.environ, 'PYTHONIOENCODING':'utf-8',
                    'REFLOW_PARENT_PID':str(os.getpid()), 'REFLOW_PARENT_CREATED':str(psutil.Process().create_time())})
            result = json.loads(result_path.read_text(encoding='utf-8'))
            if {r['cue_id'] for r in result.get('cue_embeddings',[])} != {'mother-long','daughter-long','mother-short'}:
                raise RuntimeError('Variable-duration source voice extraction failed its actual-model check')
            turns = validate_turns(result)
            anchors = references(AudioSegment.from_wav(source), result, destination)
            scene_speakers = {row['speaker'] for row in turns if row['start'] < 180 and row['end'] > 138}
            result.update(source=str(source), reference_files=anchors,
                          human_quality_accepted=False, expected_scene_speakers=2,
                          scene_speakers=len(scene_speakers),
                          actual_speakers=len({row['speaker'] for row in turns}))
            (destination/'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            if len(scene_speakers) != 2 or not scene_speakers <= anchors.keys() or len(anchors) < 3:
                raise RuntimeError('The known two-character scene did not yield two usable voices; inspect retained evidence')
            if validate(candidate=True)['identity'] != route['identity']:
                raise RuntimeError('Speaker runtime changed during verification')
            profile_path = ROOT/'runtime_profiles/speaker-diarization/profile.json'
            profile = json.loads(profile_path.read_text(encoding='utf-8'))
            profile.update(status='speaker-model-verified', speaker_probe=dict(identity=route['identity'],
                device='cuda:0', speakers=result['actual_speakers'], scene_speakers=2,
                evidence=str(destination/'result.json')))
            from core.run_manifest import _publish_bytes
            _publish_bytes(profile_path, (json.dumps(profile, indent=2)+'\n').encode('utf-8'))
            validate()
            print('Dedicated speaker detector passed: multiple voices, distinct mother/daughter references, cuda:0.', flush=True)
    finally:
        job.cleanup()


if __name__ == '__main__':
    main()
