"""Actual production provider trial: publication, reuse, child crash and new-job recovery."""
import hashlib,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/validation'
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ.update(REFLOW_OFFLINE='1',PATH=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH',''))
def main():
    from core.render_context import RenderContext,bind_job,run_process
    from core.providers.tts.xtts_local import XTTSLocalProvider
    from core.xtts_runtime import readiness
    from core.run_manifest import provider_identity
    report=dict(passed=False,checks={},native_ui_test=False,default_switched=False);started=time.monotonic()
    for phase in ['crash','recover']:
        job=RenderContext(ROOT/'temp');item=dict(phase=phase);report.setdefault('phases',[]).append(item)
        try:
            with bind_job(job):
                reference=job.workspace/'reference.wav'
                run_process(['ffmpeg','-v','error','-y','-ss','2','-i',str(ROOT/'Sample/2.mp4'),'-t','6','-vn','-ar','24000','-ac','1',str(reference)],check=True,timeout=60)
                provider=XTTSLocalProvider(device='cpu',model_path=str(ROOT/'models/xtts/default'),runtime='isolated')
                output=job.workspace/'speech.wav'
                provider.synthesize('Good morning.',str(output),'en',str(reference))
                item['pid']=provider.last_result['worker_pid'];item['identity']=provider_identity(provider)
                report['checks']['readiness_verified']=readiness()['status']=='ready-for-explicit-trial'
                if phase=='crash':
                    first=item['pid'];provider.synthesize('This is the second speech request.',str(output),'en',str(reference))
                    report['checks']['model_reused']=provider.last_result['worker_pid']==first and provider.last_result['model_loads']==1
                    before=hashlib.sha256(output.read_bytes()).hexdigest()
                    owned=list(job.processes)
                    if len(owned)!=1:raise RuntimeError('Expected exactly one owned XTTS child')
                    child=owned[0]
                    child.kill();child.wait(timeout=10)
                    try:provider.synthesize('This cannot finish after a crash.',str(output),'en',str(reference))
                    except RuntimeError:item['crash_reported']=True
                    else:raise RuntimeError('Provider hid the worker crash')
                    report['checks']['crashed_output_preserved']=hashlib.sha256(output.read_bytes()).hexdigest()==before
                else:
                    report['checks']['new_job_recovered']=output.stat().st_size>1000 and item['pid']!=report['phases'][0]['pid']
                    retained=OUT/'2026-10-13-xtts-production-provider-success.wav'
                    retained.write_bytes(output.read_bytes());item['output']=str(retained)
                provider.release()
        except Exception as error:
            import traceback
            report.update(error=str(error),traceback=traceback.format_exc());break
        finally:
            job.cleanup();item['workspace_removed']=not job.workspace.exists()
    report['checks']['all_workspaces_removed']=all(i.get('workspace_removed') for i in report['phases'])
    report['passed']='error' not in report and len(report['phases'])==2 and all(report['checks'].values())
    report['elapsed_seconds']=round(time.monotonic()-started,3)
    (OUT/'2026-10-13-xtts-production-provider.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2));return not report['passed']
if __name__=='__main__':raise SystemExit(main())
