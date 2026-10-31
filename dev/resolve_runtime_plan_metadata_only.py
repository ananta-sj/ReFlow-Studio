"""Bounded pip dry-run with archive transfers blocked; never install/build code."""
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit
import argparse

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/validation'
plan=json.loads((OUT/'2026-10-13-runtime-repair-plan.json').read_text(encoding='utf-8'))
os.environ['PIP_CACHE_DIR']=str(ROOT/'temp/runtime-repair-metadata-cache')
os.environ['PIP_DISABLE_PIP_VERSION_CHECK']='1'
from pip._internal.network.session import PipSession
from pip._internal.cli.main import main as pip_main

original_send=PipSession.send
requests_seen=[]


def metadata_send(self,request,**kwargs):
    parsed=urlsplit(request.url)
    path=parsed.path.lower()
    if parsed.hostname in {'download.pytorch.org','download-r2.pytorch.org'} and path.startswith('/whl/cpu/') and path.endswith('/') and path.rsplit('/',2)[-2] not in {'torch','torchaudio','torchcodec'}:
        from pip._vendor.requests import Response
        response=Response()
        response.status_code=200
        response.url=request.url
        response.headers['Content-Type']='text/html'
        response._content=b'<html><body></body></html>'
        requests_seen.append(dict(method=request.method,url=request.url,allowed=True,network_sent=False,reason='CPU mirror restricted to Torch family'))
        return response
    allowed=parsed.scheme=='https' and not parsed.username and parsed.hostname in {
        'pypi.org','files.pythonhosted.org','download.pytorch.org','download-r2.pytorch.org'}
    if request.method.upper()!='HEAD':
        allowed=allowed and (path.endswith('.whl.metadata') or
            parsed.hostname=='pypi.org' and path.startswith('/simple/') or
            parsed.hostname in {'download.pytorch.org','download-r2.pytorch.org'} and path.endswith('/') and path.startswith('/whl/cpu/'))
    requests_seen.append(dict(method=request.method,url=request.url.split('#')[0],allowed=allowed))
    if not allowed:raise RuntimeError('Metadata-only planning blocked an archive or non-metadata request')
    return original_send(self,request,**kwargs)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--label',default='with-docopt')
    parser.add_argument('--plan',type=Path,default=OUT/'2026-10-13-runtime-repair-plan.json')
    args=parser.parse_args()
    label=args.label
    assert args.plan.resolve().is_relative_to(OUT.resolve())
    selected_plan=json.loads(args.plan.read_text(encoding='utf-8'))
    assert label.replace('-','').isalnum()
    helper_dir=OUT/'2026-10-13-docopt-helper'
    helper=json.loads((helper_dir/'receipt.json').read_text(encoding='utf-8'))
    wheel=helper_dir/helper['wheel']
    import hashlib
    assert wheel.resolve().is_relative_to(helper_dir.resolve())
    assert hashlib.sha256(wheel.read_bytes()).hexdigest()==helper['wheel_sha256']
    report_path=OUT/f'2026-10-13-xtts-{label}-resolution-report.json'
    assert not report_path.exists(), 'Preserve existing evidence; select a new report filename'
    PipSession.send=metadata_send
    arguments=['--isolated','install','--dry-run','--ignore-installed','--no-cache-dir',
        '--only-binary=:all:','--python-version','3.13','--platform','win_amd64',
        '--implementation','cp','--abi','cp313','--disable-pip-version-check',
        '--index-url','https://pypi.org/simple','--extra-index-url','https://download.pytorch.org/whl/cpu',
        '--timeout','20','--retries','0',
        '--report',str(report_path),str(wheel)]
    for item in selected_plan['xtts_candidate_roots']:
        arguments.append(item['name']+'=='+item['version'])
    try:
        code=pip_main(arguments)
    except Exception as error:
        code=1
        print(type(error).__name__,str(error),flush=True)
    finally:
        PipSession.send=original_send
        report=dict(metadata_only=True,installation_requested=False,source_builds_allowed=False,
            archives_allowed=False,exit_code=locals().get('code',1),requests=requests_seen,
            local_helper_sha256=helper['wheel_sha256'],
            resolution_complete=report_path.is_file())
        (OUT/f'2026-10-13-metadata-only-{label}-receipt.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return code


if __name__=='__main__':raise SystemExit(main())
