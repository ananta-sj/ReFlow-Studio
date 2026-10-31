"""Build only the four approved source archives; no runtime installation."""
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
OUT=ROOT/'docs/validation/2026-10-16-separation-helpers'
STAGE=ROOT/'temp/separation-helpers-2026-10-16'
PINS={
 'antlr4-python3-runtime':('4.9.3',117034,'f224469b4168294902bb1efa80a8bf7855f24c99aef99cbefc1bcd3cce77881b'),
 'demucs':('4.0.1',1212924,'e45a5a788bae79767c37bbf6e69aae03862ddcca05550fb79b926346a177d713'),
 'dora-search':('0.1.12',87111,'2956fd2c4c7e4b9a4830e83f0d4cf961be45cfba1a2f0570281e91d15ac516fb'),
 'julius':('0.2.7',59640,'3c0f5f5306d7d6016fcc95196b274cae6f07e2c9596eed314e4e7641554fbb08')}
OWNER='reflow.approved.separation.helpers.2026-10-16'
WRAPPER=r'''
import os,sys,runpy,socket
import setuptools
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


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fetch-only',action='store_true');args=parser.parse_args()
    review=json.loads((ROOT/'docs/validation/2026-10-16-separation-artifact-review.json').read_text())
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
            source=next(extraction.iterdir()) if extraction.exists() else unpack(archive,extraction)
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
            assert 'ext_modules' not in setup and 'setup_requires' not in setup,'Unreviewed build mechanism'
            env={**os.environ,'TEMP':str(STAGE),'TMP':str(STAGE),'PIP_NO_INDEX':'1','PIP_DISABLE_PIP_VERSION_CHECK':'1',
                'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8','SOURCE_DATE_EPOCH':'1792108800'}
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
                        assert original.is_file() and package.read(filename)==original.read_bytes(),filename
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
