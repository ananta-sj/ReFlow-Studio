"""Current original-runtime short visual check; no installs or downloads."""
import argparse,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='2',
    PATH=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH',''))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('engine',choices=['gfpgan','wav2lip']);args=parser.parse_args()
    from core.render_context import RenderContext,bind_job,run_process
    from core.runtime_integrity import sha
    def offline(event,values):
        if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:raise RuntimeError('This installed-engine audit forbids network access')
    sys.addaudithook(offline)
    import torch
    torch.set_num_threads(2)
    files=[ROOT/'gfpgan/weights'/name for name in ['GFPGANv1.4.pth','parsing_parsenet.pth','detection_Resnet50_Final.pth']] if args.engine=='gfpgan' else [ROOT/'core/Wav2Lip/checkpoints/Wav2Lip_GAN.pth']
    before={str(path.relative_to(ROOT)):sha(path) for path in files}
    report=dict(passed=False,engine=args.engine,device='cpu',original_runtime=True,quality_approved=False,model_downloaded=False,face_model_forward_calls=0)
    job=RenderContext(ROOT/'temp');started=time.monotonic()
    try:
        with bind_job(job):
            video=job.workspace/'source.mp4';audio=job.workspace/'source.wav';output=job.workspace/'result.mp4'
            run_process(['ffmpeg','-v','error','-nostdin','-y','-ss','2','-i',str(ROOT/'Sample/2.mp4'),'-t','1','-vf','fps=3,scale=640:-2','-an','-c:v','libx264',str(video)],check=True,timeout=60)
            if args.engine=='gfpgan':
                from core.enhancer import FaceEnhancer
                enhancer=FaceEnhancer(device='cpu')
                def observed(*values):report['face_model_forward_calls']+=1
                handle=enhancer.restorer.gfpgan.register_forward_hook(observed)
                try:enhancer.enhance(str(video),str(output))
                finally:handle.remove()
            else:
                from core.lipsync_handler import LipSyncHandler
                run_process(['ffmpeg','-v','error','-nostdin','-y','-ss','2','-i',str(ROOT/'Sample/2.mp4'),'-t','1','-vn','-ac','1','-ar','16000',str(audio)],check=True,timeout=60)
                LipSyncHandler(device='cpu').execute(str(video),str(audio),str(output))
            info=json.loads(run_process(['ffprobe','-v','error','-show_streams','-of','json',str(output)],check=True,capture_output=True,text=True,timeout=60).stdout)
            stream=next(row for row in info['streams'] if row['codec_type']=='video')
            assert int(stream['nb_frames'])==3 and abs(float(stream['duration'])-1)<.1
            run_process(['ffmpeg','-v','error','-nostdin','-i',str(output),'-f','null','-'],check=True,capture_output=True,timeout=60)
            report.update(passed=True,frames=3,duration_seconds=float(stream['duration']),output_bytes=output.stat().st_size)
    except Exception as error:
        import traceback
        report.update(error=repr(error),traceback=traceback.format_exc())
    finally:
        report['owned_processes_exited']=not job.processes;job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(),seconds=round(time.monotonic()-started,3),model_hashes_preserved=before=={str(path.relative_to(ROOT)):sha(path) for path in files},model_sha256=before)
        (ROOT/f'docs/validation/2026-10-16-installed-{args.engine}-real.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2),flush=True)
    return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
