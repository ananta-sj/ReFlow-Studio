"""Existing F5 speech with an explicit transcript; no reference ASR or downloads."""
import json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'core')]
LABEL='2026-10-16-f5-lazy-speech-final'
os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='2',
    PATH=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH',''))
def main():
    from core.optional_runtime import run_feature
    from core.model_contract import local_contract
    from core.render_context import RenderContext,bind_job
    from core.audio_utils import load_speech_audio
    from core.runtime_integrity import sha
    weights=ROOT/'models/f5/acceptance_v1/F5TTS_v1_Base/model_1250000.safetensors'
    reference=ROOT/'runtime_profiles/f5/Lib/site-packages/f5_tts/infer/examples/basic/basic_ref_en.wav'
    assert weights.is_file() and reference.is_file(),'Use installed assets only'
    source_paths=[weights,ROOT/'runtime_profiles/f5/Lib/site-packages/f5_tts/infer/utils_infer.py',ROOT/'runtime_profiles/f5/Lib/site-packages/f5_tts/model/__init__.py']
    before={str(path.relative_to(ROOT)):sha(path) for path in source_paths}
    report=dict(passed=False,model_downloaded=False,packages_installed=False,automatic_reference_asr_tested=False,quality_accepted=False)
    job=RenderContext(ROOT/'temp');started=time.monotonic()
    try:
        contract=local_contract('voice',str(weights.parent.parent),'f5tts')
        with bind_job(job):
            output=job.workspace/'speech.wav'
            run_feature('f5','f5_speech',{**contract,'device':'cpu','reference_audio':str(reference),
                'reference_text':'Some call me nature, others call me mother nature.','text':'Good morning.','output_path':str(output)},timeout=300)
            clip=load_speech_audio(str(output));assert 200<=len(clip)<=15000
            destination=ROOT/'docs/validation'/f'{LABEL}.wav';job.publish(output,destination)
            report.update(passed=True,duration_ms=len(clip),sample_rate=clip.frame_rate,peak=clip.max,output=str(destination),output_sha256=sha(destination))
    except Exception as error:
        import traceback
        report.update(error=repr(error),traceback=traceback.format_exc())
    finally:
        report['owned_processes_exited']=not job.processes;job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(),seconds=round(time.monotonic()-started,3),source_and_model_hashes_preserved=before=={str(path.relative_to(ROOT)):sha(path) for path in source_paths},asset_sha256=before)
        (ROOT/'docs/validation'/f'{LABEL}.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2),flush=True)
    return not report['passed']
if __name__=='__main__':raise SystemExit(main())
