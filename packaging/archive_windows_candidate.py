"""Archive only verified manifest files, then read every ZIP member back."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha_stream(stream):
    value = hashlib.sha256()
    for block in iter(lambda: stream.read(1024*1024), b''):
        value.update(block)
    return value.hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('candidate',type=Path)
    parser.add_argument('--core-report',type=Path,required=True)
    parser.add_argument('--desktop-report',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    folder=args.candidate.resolve()
    if not folder.is_relative_to(ROOT/'dist') or folder==ROOT/'dist':
        raise ValueError('Expected an owned candidate inside dist')
    core=json.loads(args.core_report.read_text(encoding='utf-8'))
    desktop=json.loads(args.desktop_report.read_text(encoding='utf-8'))
    if (not core.get('passed') or not desktop.get('acceptance')
            or Path(desktop['application']).resolve()!=folder
            or Path(core['worker']['root']).resolve()!=folder):
        raise RuntimeError('Candidate startup checks must pass before archiving')
    manifest_path=folder/'portable-manifest.json'
    manifest_bytes=manifest_path.read_bytes()
    manifest=json.loads(manifest_bytes)
    files=manifest['files']
    paths=[row['path'] for row in files]
    if len(set(p.casefold() for p in paths))!=len(paths):
        raise ValueError('Duplicate manifest file paths')
    for name in paths:
        path=Path(name)
        if path.is_absolute() or '..' in path.parts or not (folder/path).resolve().is_relative_to(folder):
            raise ValueError('Unsafe manifest path')
    archive=folder.with_suffix('.zip')
    sums=folder.with_suffix('.SHA256SUMS.txt')
    if archive.exists() or sums.exists():
        raise RuntimeError('Refusing to replace an existing archive/checksum')
    started=time.monotonic()
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as output:
        for index,row in enumerate(files):
            source=folder/row['path']
            if source.stat().st_size!=row['bytes']:
                raise RuntimeError('Changed candidate file: '+row['path'])
            output.write(source,folder.name+'/'+row['path'])
            if index%8192==0:
                print('Archived %d/%d files' % (index+1,len(files)),flush=True)
        output.writestr(folder.name+'/portable-manifest.json',manifest_bytes)
    print('Reading back every ZIP file and checking its SHA-256...',flush=True)
    with zipfile.ZipFile(archive) as saved:
        expected={folder.name+'/'+row['path']:row for row in files}
        if set(saved.namelist())!=set(expected)|{folder.name+'/portable-manifest.json'}:
            raise RuntimeError('ZIP inventory mismatch')
        if saved.read(folder.name+'/portable-manifest.json')!=manifest_bytes:
            raise RuntimeError('ZIP manifest mismatch')
        for index,(name,row) in enumerate(expected.items()):
            with saved.open(name) as stream:
                if sha_stream(stream)!=row['sha256']:
                    raise RuntimeError('ZIP content differs from assembled source: '+name)
            if index%16384==0:
                print('Verified %d/%d archived files' % (index+1,len(files)),flush=True)
    with archive.open('rb') as stream:
        digest=sha_stream(stream)
    sums.write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    report=dict(passed=True,release_ready=False,archive=str(archive),archive_bytes=archive.stat().st_size,
                archive_sha256=digest,checksum_file=str(sums),file_count=len(files)+1,
                every_archived_file_sha256_verified=True,core_startup_passed=True,
                native_desktop_startup_passed=True,clean_machine_test=False,model_inference_test=False,
                elapsed_seconds=round(time.monotonic()-started,3),software_installed=False,models_downloaded=False)
    args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    main()
