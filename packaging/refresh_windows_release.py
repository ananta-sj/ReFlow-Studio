"""Rebuild a verified ZIP, preserving compressed bytes of unchanged runtimes.

The writer updates central-directory offsets after copying local ZIP records.
Every output member is then decoded and checked against the updated manifests.
"""
import copy
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
NAME='ReflowStudio-Windows-RC1-2026-10-31'


def sha(stream):
    value=hashlib.sha256()
    for block in iter(lambda:stream.read(1024*1024),b''): value.update(block)
    return value.hexdigest()


def rewrite_zip(source,target,replacements):
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as output:
        records=sorted(original.infolist(),key=lambda item:item.header_offset)
        if len({info.filename for info in records})!=len(records):
            raise ValueError('Input ZIP has duplicate names')
        if set(replacements)-{info.filename for info in records}:
            raise ValueError('Replacement names are missing from input ZIP')
        for index,info in enumerate(records):
            if info.filename in replacements:
                output.writestr(copy.copy(info),replacements[info.filename])
            else:
                finish=records[index+1].header_offset if index+1<len(records) else original.start_dir
                remaining=finish-info.header_offset
                if remaining<=0: raise ValueError('Invalid local ZIP record bounds')
                updated=copy.copy(info)
                updated.header_offset=output.fp.tell()
                output._writecheck(updated)
                original.fp.seek(info.header_offset)
                while remaining:
                    block=original.fp.read(min(1024*1024,remaining))
                    if not block: raise ValueError('Truncated local ZIP record')
                    output.fp.write(block);remaining-=len(block)
                output.filelist.append(updated)
                output.NameToInfo[updated.filename]=updated
                output.start_dir=output.fp.tell()
                output._didModify=True
            if index%32768==0: print('Rebuilt %d/%d members' % (index+1,len(records)),flush=True)


def main():
    folder=ROOT/'dist'/NAME
    source=ROOT/'dist/ReflowStudio-Windows-Executable-RC1-2026-10-31.zip'
    target=ROOT/'dist/ReflowStudio-Windows-Executable-RC2-2026-10-31.zip'
    branding=json.loads((ROOT/'docs/validation/2026-10-31-taskbar-branding.json').read_text())
    core=json.loads((ROOT/'docs/validation/2026-10-31-iconfix-executable-core.json').read_text())
    if not branding['passed'] or not core['passed']:
        raise RuntimeError('Icon and executable startup checks must pass first')
    prior=json.loads((ROOT/'docs/validation/2026-10-31-executable-archive.json').read_text())
    with source.open('rb') as stream:
        if sha(stream)!=prior['sha256']: raise RuntimeError('Previous verified ZIP changed')
    with zipfile.ZipFile(source) as original:
        base=json.loads(original.read(NAME+'/portable-manifest.json'))
        extension=json.loads(original.read(NAME+'/executable-manifest.json'))
    replacements={}
    changed={'main.py','core/tray.py'}
    for row in base['files']:
        if row['path'] in changed:
            payload=(folder/row['path']).read_bytes()
            base['bytes_by_component'][row['component']]+=len(payload)-row['bytes']
            row.update(bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest())
            replacements[NAME+'/'+row['path']]=payload
    for row in extension['files']:
        payload=(folder/row['path']).read_bytes()
        digest=hashlib.sha256(payload).hexdigest()
        if digest!=row['sha256']:
            row.update(bytes=len(payload),sha256=digest)
            replacements[NAME+'/'+row['path']]=payload
    base['window_branding']='ReflowStudio.Desktop'
    base_bytes=json.dumps(base,indent=2).encode('utf-8')
    extension.update(base_manifest_sha256=hashlib.sha256(base_bytes).hexdigest(),
                     window_branding_verified=True,revision='RC2')
    extra_bytes=json.dumps(extension,indent=2).encode('utf-8')
    replacements[NAME+'/portable-manifest.json']=base_bytes
    replacements[NAME+'/executable-manifest.json']=extra_bytes
    rewrite_zip(source,target,replacements)
    expected={NAME+'/'+row['path']:row['sha256'] for row in base['files']+extension['files']}
    expected[NAME+'/portable-manifest.json']=hashlib.sha256(base_bytes).hexdigest()
    expected[NAME+'/executable-manifest.json']=hashlib.sha256(extra_bytes).hexdigest()
    print('Decoding and verifying every refreshed ZIP member...',flush=True)
    with zipfile.ZipFile(target) as result:
        if len(result.namelist())!=len(expected) or set(result.namelist())!=set(expected):
            raise RuntimeError('Refreshed ZIP inventory differs')
        for index,(name,digest) in enumerate(expected.items()):
            with result.open(name) as stream:
                if sha(stream)!=digest: raise RuntimeError('Refreshed ZIP content differs: '+name)
            if index%32768==0: print('Verified %d/%d members' % (index+1,len(expected)),flush=True)
    with target.open('rb') as stream: digest=sha(stream)
    target.with_suffix('.SHA256SUMS.txt').write_text(digest+'  '+target.name+'\n',encoding='ascii')
    (folder/'portable-manifest.json').write_bytes(base_bytes)
    (folder/'executable-manifest.json').write_bytes(extra_bytes)
    report=dict(passed=True,archive=str(target),bytes=target.stat().st_size,sha256=digest,
                files=len(expected),every_member_sha256_verified=True,branding=branding,
                executable_startup_passed=True,release_ready=False,models_downloaded=False)
    (ROOT/'docs/validation/2026-10-31-iconfix-archive.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='branding'},indent=2),flush=True)


if __name__=='__main__': main()
