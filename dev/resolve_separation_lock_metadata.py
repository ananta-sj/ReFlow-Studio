"""Genuine pip dry-run; only index/metadata network transfers are allowed."""
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/validation';PREFIX='2026-10-16-separation-runtime'
sys.path.insert(0,str(ROOT))


def main():
    from pip._internal.network.session import PipSession
    from pip._internal.cli.main import main as pip_main
    from core.runtime_integrity import sha
    plan_path=OUT/(PREFIX+'-proposal.json');plan=json.loads(plan_path.read_text())
    expected={row['name']:row['version'] for row in plan['packages']}
    original=PipSession.send;seen=[]
    def guarded(session,request,**kwargs):
        parsed=urlsplit(request.url);path=parsed.path.lower()
        allowed=request.method=='GET' and parsed.scheme=='https' and not parsed.username and (
            parsed.hostname=='pypi.org' and path.startswith('/simple/') or
            parsed.hostname in {'files.pythonhosted.org','download.pytorch.org','download-r2.pytorch.org'} and path.endswith('.whl.metadata') or
            parsed.hostname in {'download.pytorch.org','download-r2.pytorch.org'} and path.startswith('/whl/cpu/') and path.endswith('/'))
        if parsed.hostname in {'download.pytorch.org','download-r2.pytorch.org'} and path.endswith('/') and path.rsplit('/',2)[-2] not in {'torch','torchaudio','torchcodec'}:
            from pip._vendor.requests import Response
            response=Response();response.status_code=200;response.url=request.url;response.headers['Content-Type']='text/html';response._content=b'<html></html>'
            seen.append(dict(url=request.url,allowed=True,network_sent=False));return response
        seen.append(dict(url=request.url,allowed=allowed))
        if not allowed:raise RuntimeError('Planning blocked non-metadata transfer: '+request.url)
        return original(session,request,**kwargs)
    report_path=OUT/(PREFIX+'-resolution-report.json');assert not report_path.exists()
    arguments=['--isolated','install','--dry-run','--ignore-installed','--no-cache-dir','--only-binary=:all:',
        '--python-version','3.13','--platform','win_amd64','--implementation','cp','--abi','cp313',
        '--disable-pip-version-check','--index-url','https://pypi.org/simple','--extra-index-url','https://download.pytorch.org/whl/cpu',
        '--timeout','20','--retries','0','--report',str(report_path)]
    for row in plan['packages']:
        if row['source']=='approved-built-wheel':
            wheel=ROOT/row['local_wheel'];assert sha(wheel)==row['sha256'];arguments.append(str(wheel))
        else:arguments.append(row['name']+'=='+row['version'])
    os.environ['PIP_DISABLE_PIP_VERSION_CHECK']='1';PipSession.send=guarded
    receipt=dict(runtime_installed=False,models_downloaded=False,new_archives_allowed=False,source_builds_allowed=False,
        proposal_sha256=sha(plan_path),requests=seen)
    try:
        code=pip_main(arguments)
        if code==0:
            from packaging.utils import canonicalize_name
            result=json.loads(report_path.read_text())
            actual={canonicalize_name(row['metadata']['name']):row['metadata']['version'] for row in result['install']}
            assert actual==expected,(actual,expected)
        receipt.update(exit_code=code,resolution_verified=code==0)
    except Exception as error:
        receipt.update(exit_code=1,resolution_verified=False,error=repr(error));raise
    finally:
        PipSession.send=original
        (OUT/(PREFIX+'-resolution-receipt.json')).write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    return receipt['exit_code']


if __name__=='__main__':raise SystemExit(main())
