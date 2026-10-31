"""Actual existing NudeNet worker from an AI-free desktop; preserve publication."""
import importlib.util,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ.update(PYTHONDONTWRITEBYTECODE='1',REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
    PATH=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH',''))

def main():
    from core.providers.resolve import resolve_filter,resolve_enhancer
    from core.optional_runtime import interpreter
    from core.render_context import RenderContext,bind_job,run_process
    from core.runtime_integrity import sha
    checkpoint=ROOT/'runtime_profiles/vision/Lib/site-packages/nudenet/320n.onnx'
    assert checkpoint.is_file(),'Bundled local detector required; no downloads permitted'
    before=sha(checkpoint)
    report=dict(passed=False,checks={},model_downloaded=False,detection_quality_approved=False)
    def check(name,value):
        report['checks'][name]=bool(value)
        if not value:raise AssertionError(name)
    job=RenderContext(ROOT/'temp')
    try:
        check('no_parent_torch_opencv_or_detector',all(importlib.util.find_spec(name) is None for name in ['torch','cv2','nudenet']))
        provider=resolve_filter(None);enhancer=resolve_enhancer(None,device='cpu',upscale=1)
        check('providers_resolve_without_parent_ai',provider.__class__.__name__=='NudeNetLocalProvider' and enhancer.__class__.__name__=='GFPGANLocalProvider')
        report['vision_interpreter']=interpreter('vision')
        with bind_job(job):
            source=job.workspace/'source.mp4';output=job.workspace/'filtered.mp4'
            run_process(['ffmpeg','-v','error','-nostdin','-y','-f','lavfi','-i','color=c=blue:s=64x64:r=3:d=1','-c:v','libx264',str(source)],check=True,timeout=60)
            result=provider.scan_and_blur(str(source),str(output));check('real_optional_detector_output',result==str(output) and output.is_file())
            data=json.loads(run_process(['ffprobe','-v','error','-show_streams','-of','json',str(output)],check=True,capture_output=True,text=True,timeout=30).stdout)
            video=next(row for row in data['streams'] if row['codec_type']=='video')
            check('all_frames_and_dimensions',int(video['nb_frames'])==3 and video['width']==64 and video['height']==64)
            run_process(['ffmpeg','-v','error','-nostdin','-i',str(output),'-f','null','-'],check=True,capture_output=True,timeout=60)
            check('full_decode',True)
            prior=output.read_bytes()
            try:provider.scan_and_blur(str(job.workspace/'missing.mp4'),str(output))
            except RuntimeError:check('failed_input_preserves_output',output.read_bytes()==prior)
            else:check('failed_input_preserves_output',False)
            check('stage_workers_exited',not job.processes)
        check('model_unchanged',sha(checkpoint)==before)
        report['passed']=True
    except BaseException as error:
        import traceback
        report.update(error=repr(error),traceback=traceback.format_exc());raise
    finally:
        job.cleanup();report['workspace_removed']=not job.workspace.exists()
        (ROOT/'docs/validation/2026-10-16-clean-visual-boundary.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
