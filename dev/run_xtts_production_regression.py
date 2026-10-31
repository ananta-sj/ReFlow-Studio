"""Run backend modules independently with workspace-owned temporary roots."""
import hashlib,json,os,re,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/validation'
def main():
    previous=json.loads((OUT/'2026-10-12-windows-release-backend-complete.json').read_text())
    # These two legacy scripts mutate app state/download fixtures and expose no
    # unittest cases. Their import is not test acceptance.
    excluded={'dev.test_model_download','dev.test_pipeline_dryrun'}
    modules=[m for m in previous['modules'] if m not in excluded]+['dev.test_xtts_runtime_selection']
    reports=[];start=time.monotonic()
    for module in modules:
        code="import sys,tempfile;from pathlib import Path;r=Path.cwd();sys.path[:0]=[str(r),str(r/'core')];tempfile.tempdir=str(r/'temp');import unittest;unittest.main(module=None,argv=['tests',sys.argv[1]])"
        result=subprocess.run([sys.executable,'-B','-X','utf8','-c',code,module],cwd=ROOT,
            env={**{k:v for k,v in os.environ.items() if k!='REFLOW_OFFLINE'},'TEMP':str(ROOT/'temp'),'TMP':str(ROOT/'temp'),'REFLOW_XTTS_RUNTIME':'legacy'},
            capture_output=True,text=True,encoding='utf-8',timeout=180,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        log=result.stdout+result.stderr
        (OUT/f'2026-10-13-xtts-production-{module.rsplit(".",1)[-1]}.log').write_text(log,encoding='utf-8')
        count=re.search(r'Ran (\d+) tests?',log)
        reports.append(dict(module=module,exit_code=result.returncode,tests=int(count.group(1)) if count else 0))
        print(module,result.returncode,flush=True)
    report=dict(passed=all(r['exit_code']==0 and r['tests']>0 for r in reports),tests_run=sum(r['tests'] for r in reports),
        modules=reports,elapsed_seconds=round(time.monotonic()-start,3),
        source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in previous['source_sha256']})
    report['new_sources']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'core/xtts_worker.py',ROOT/'core/xtts_runtime.py',ROOT/'core/xtts_compat.py']}
    (OUT/'2026-10-13-xtts-production-backend.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=report['passed'],tests_run=report['tests_run']),indent=2));return not report['passed']
if __name__=='__main__':raise SystemExit(main())
