"""Recheck an exported draft without rerunning translation or speech."""
import json
import os
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]
os.environ['PATH'] = str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH', '')


def main():
    from pydub import AudioSegment
    from core.render_context import RenderContext, bind_job
    from core.run_manifest import RunManifest
    from core.cuda_providers import CudaWhisperProvider
    from core.batch_intelligibility import verify
    from core.batch_review import publish
    manifest = RunManifest.__new__(RunManifest)
    manifest.path = Path(sys.argv[1]).resolve()
    if not manifest.path.is_relative_to(ROOT/'outputs/run_records'):
        raise ValueError('Only owned render records can be rechecked')
    manifest.folder = manifest.path.parent
    manifest.lock = threading.RLock()
    manifest.data = json.loads(manifest.path.read_text(encoding='utf-8'))
    data = manifest.data
    artifact = next(item for item in reversed(data['cue_artifacts']) if item['phase']=='speech-input')
    transcript = json.loads(Path(artifact['path']).read_text(encoding='utf-8'))['segments']
    retained = next((item for item in reversed(data['quality_reports']) if item['kind']=='original-audio-kept'), None)
    preserved = {row['index']:row['reason'] for row in json.loads(Path(retained['path']).read_text(encoding='utf-8'))['cues']} if retained else {}
    output = Path(data['output']['path'])
    stem = output.with_name(output.stem+'_stem_dubbed.wav')
    job = RenderContext(ROOT/'temp')
    try:
        with bind_job(job):
            provider = CudaWhisperProvider(str(ROOT/'models/whisper/ct2-turbo-candidate-compat/model'))
            result = verify(AudioSegment.from_wav(stem), transcript, provider, 'hi', preserved, manifest)
            publish(manifest.path, output)
            print('Readback:', result['status'], 'checked:',len(result['cues']),
                  'passed:',sum(row['status']=='passed_readback' for row in result['cues']), flush=True)
    finally:
        job.cleanup()


if __name__ == '__main__':
    main()
