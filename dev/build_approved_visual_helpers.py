"""Build only the two approved source archives; no runtime installation."""
import argparse
import base64
import csv
from email.parser import Parser
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
from urllib.parse import urlsplit
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/validation/2026-10-16-visual-helpers'
STAGE=ROOT/'temp/visual-helpers-2026-10-16'
PINS={
 'basicsr':('1.4.2',172524,'b89b595a87ef964cda9913b4d99380ddb6554c965577c0c10cb7b78e31301e87'),
 'filterpy':('1.4.5',177985,'4f2a4d39e4ea601b9ab42b2db08b5918a9538c168cff1c6895ae26646f3d73b1')}
OWNER='reflow.approved.visual.helpers.2026-10-16'
WRAPPER=r'''
import os,sys,runpy,socket
import setuptools
import importlib.metadata as metadata
original_distributions=metadata.distributions
def named_distributions(*args,**kwargs):
    return (dist for dist in original_distributions(*args,**kwargs) if dist.metadata.get('Name'))
metadata.distributions=named_distributions
def deny(*args,**kwargs):raise RuntimeError('Helper build network/child process is disabled')
def audit(event,args):
    if event in {'socket.connect','socket.bind','socket.getaddrinfo','subprocess.Popen','os.system','os.exec','os.posix_spawn'}:deny()
sys.addaudithook(audit)
socket.create_connection=socket.getaddrinfo=deny
sys.argv=['setup.py','bdist_wheel','--dist-dir',sys.argv[1]]
runpy.run_path('setup.py',run_name='__main__')
'''


def sha(data):return hashlib.sha256(data).hexdigest()


def unpack(archive,destination):
    destination.mkdir()
    with tarfile.open(archive) as package:
        members=package.getmembers()
        assert len(members)<10000 and sum(row.size for row in members)<50_000_000
        seen=set()
        for row in members:
            path=PurePosixPath(row.name)
            assert not path.is_absolute() and '..' not in path.parts and '\\' not in row.name and ':' not in row.name
            assert not row.issym() and not row.islnk() and (row.isdir() or row.isfile())
            target=destination.joinpath(*path.parts).resolve()
            assert target.is_relative_to(destination.resolve()) and target!=destination.resolve()
            assert str(target).lower() not in seen
            seen.add(str(target).lower())
            if row.isdir():target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with package.extractfile(row) as stream:target.write_bytes(stream.read())
    roots=list(destination.iterdir());assert len(roots)==1 and roots[0].is_dir()
    return roots[0]


def unpack_zip(archive,destination):
    destination.mkdir()
    with zipfile.ZipFile(archive) as package:
        rows=package.infolist();assert len(rows)<10000 and sum(row.file_size for row in rows)<50_000_000
        seen=set()
        for row in rows:
            path=PurePosixPath(row.filename)
            assert not path.is_absolute() and '..' not in path.parts and '\\' not in row.filename and ':' not in row.filename
            assert (row.external_attr>>16)&0o170000!=0o120000
            target=destination.joinpath(*path.parts).resolve()
            assert target.is_relative_to(destination.resolve()) and target!=destination.resolve()
            assert str(target).lower() not in seen;seen.add(str(target).lower())
            if row.is_dir():target.mkdir(parents=True,exist_ok=True)
            else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(package.read(row))
    roots=list(destination.iterdir());assert len(roots)==1 and roots[0].is_dir()
    return roots[0]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fetch-only',action='store_true');args=parser.parse_args()
    review=json.loads((ROOT/'docs/validation/2026-10-16-visual-runtime-feasibility.json').read_text())
    if STAGE.exists():assert (STAGE/'.owner').read_text()==OWNER
    else:STAGE.mkdir();(STAGE/'.owner').write_text(OWNER)
    assert STAGE.resolve().parent==(ROOT/'temp').resolve() and not STAGE.is_symlink()
    OUT.mkdir(exist_ok=True)
    report=dict(passed=False,runtime_installed=False,models_downloaded=False,defaults_changed=False,packages=[])
    try:
        for name,(version,size,digest) in PINS.items():
            row=next(row for row in review['packages'] if row['name']==name)
            artifact=row['source_archives'][0]
            assert (row['version'],artifact['bytes'],artifact['sha256'])==(version,size,digest)
            parsed=urlsplit(artifact['url']);assert parsed.scheme=='https' and parsed.hostname=='files.pythonhosted.org'
            archive=STAGE/artifact['filename']
            if not archive.exists():
                with urllib.request.urlopen(artifact['url'],timeout=30) as response:
                    assert urlsplit(response.url).hostname==parsed.hostname
                    payload=response.read(size+1)
                assert len(payload)==size and sha(payload)==digest
                archive.write_bytes(payload)
            assert archive.stat().st_size==size and sha(archive.read_bytes())==digest
            extraction=STAGE/(name+'-source')
            source=next(extraction.iterdir()) if extraction.exists() else (unpack_zip(archive,extraction) if archive.suffix=='.zip' else unpack(archive,extraction))
            package_out=OUT/name;package_out.mkdir(exist_ok=True)
            inspected={}
            for path in sorted(source.rglob('*')):
                if not path.is_file():continue
                rel=path.relative_to(source)
                if path.name in {'setup.py','setup.cfg','pyproject.toml','MANIFEST.in'} or any(term in path.name.lower() for term in ('license','licence','copying','notice')):
                    copy=package_out/'source-review'/rel;copy.parent.mkdir(parents=True,exist_ok=True);copy.write_bytes(path.read_bytes())
                    inspected[str(rel)]=sha(path.read_bytes())
            item=dict(name=name,version=version,source=artifact,source_review=inspected,build_passed=False)
            report['packages'].append(item)
            if args.fetch_only:continue
            assert not list(package_out.glob('*.whl')),'Preserve previous wheels'
            setup=(source/'setup.py').read_text(encoding='utf-8')
            approved=json.loads((package_out/'build-review-approved.json').read_text())
            assert approved['reviewed'] and sha((source/'setup.py').read_bytes())==approved['setup_sha256'],'Build source differs from review'
            env={**os.environ,'TEMP':str(STAGE),'TMP':str(STAGE),'PIP_NO_INDEX':'1','PIP_DISABLE_PIP_VERSION_CHECK':'1',
                'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8','SOURCE_DATE_EPOCH':'1792108800','BASICSR_EXT':'False','MAX_JOBS':'1'}
            result=subprocess.run([str(ROOT/'build/windows-portable/python.exe'),'-B','-X','utf8','-c',WRAPPER,str(package_out)],
                cwd=source,env=env,capture_output=True,text=True,encoding='utf-8',timeout=120,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            (package_out/'build.log').write_text(result.stdout+result.stderr,encoding='utf-8')
            assert result.returncode==0,result.stdout[-1500:]+result.stderr[-3000:]
            wheels=list(package_out.glob('*.whl'));assert len(wheels)==1
            wheel=wheels[0]
            with zipfile.ZipFile(wheel) as package:
                names=package.namelist();assert len(names)==len(set(names))
                for filename in names:
                    path=PurePosixPath(filename);assert not path.is_absolute() and '..' not in path.parts and ':' not in filename and '\\' not in filename
                headers=Parser().parsestr(package.read(next(n for n in names if n.endswith('/METADATA'))).decode())
                assert headers['Name'].lower().replace('_','-')==name and headers['Version']==version
                for filename,hash_value,length in csv.reader(io.StringIO(package.read(next(n for n in names if n.endswith('/RECORD'))).decode())):
                    if hash_value:
                        payload=package.read(filename)
                        assert hash_value=='sha256='+base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).decode().rstrip('=') and int(length)==len(payload)
                matches=[]
                for filename in names:
                    if filename.endswith('.py'):
                        original=source/filename
                        if not original.exists():original=source/'src'/filename
                        assert original.is_file(),filename
                        if original.name=='version.py' and name=='basicsr':
                            compile(package.read(filename),filename,'exec')
                        else:assert package.read(filename)==original.read_bytes(),filename
                        matches.append(filename)
                item.update(build_passed=True,wheel=str(wheel.relative_to(ROOT)),wheel_bytes=wheel.stat().st_size,wheel_sha256=sha(wheel.read_bytes()),
                    requires_dist=headers.get_all('Requires-Dist') or [],record_verified=True,python_sources_verified=len(matches),
                    notice_files=[n for n in names if any(term in n.lower() for term in ('license','licence','copying','notice'))])
            print(name,'wheel verified',flush=True)
        report['passed']=not args.fetch_only and all(row['build_passed'] for row in report['packages'])
    except Exception as error:
        report.update(error_type=type(error).__name__,error=str(error));raise
    finally:
        report['fetch_only']=args.fetch_only
        (OUT/('fetch-receipt.json' if args.fetch_only else 'build-receipt.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
