"""Extend a verified base ZIP with the tested native launcher, without duplicates."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]
NAME='ReflowStudio-Windows-RC1-2026-10-31'


def sha(stream):
    value=hashlib.sha256()
    for block in iter(lambda:stream.read(1024*1024),b''):
        value.update(block)
    return value.hexdigest()


def main():
    folder=ROOT/'dist'/NAME
    base=json.loads((ROOT/'docs/validation/2026-10-31-portable-archive.json').read_text())
    core=json.loads((ROOT/'docs/validation/2026-10-31-executable-core.json').read_text())
    desktop=json.loads((ROOT/'docs/validation/2026-10-31-executable-desktop.json').read_text())
    if not base['passed'] or not core['passed'] or not desktop['acceptance']:
        raise RuntimeError('Base archive and executable startup checks must pass')
    if Path(core['root']).resolve()!=folder or Path(desktop['application']).resolve()!=folder:
        raise RuntimeError('Executable startup receipts refer to another candidate')
    original=folder.with_suffix('.zip')
    archive=ROOT/'dist/ReflowStudio-Windows-Executable-RC1-2026-10-31.zip'
    if archive.exists():
        raise RuntimeError('Executable ZIP already exists')
    notes=('REFLOW STUDIO - WINDOWS EXECUTABLE TEST CANDIDATE\n\n'
        'Extract the entire ZIP, then double-click ReflowStudio.exe.\n'
        'Keep _internal, build, core, frontend and runtime_profiles beside the EXE.\n'
        'No system Python is required. The EXE starts the included tested Python.\n'
        'Launch_Reflow.bat remains an alternative launcher.\n'
        'Models, personal references, credentials and settings are not included.\n'
        'See START_HERE.txt for included engines, prerequisites and first-use limits.\n'
        'The experimental Hindi evaluation environments are not included.\n'
        'This candidate passed offline startup and hidden native-interface checks\n'
        'on the development PC. Clean-PC and full-workflow release checks remain.\n'
        'The base portable-manifest.json covers the original app/runtime files.\n'
        'executable-manifest.json covers the added launcher and verifies its base.\n'
        'PyInstaller was installed only in an owner-approved build-only folder.\n'
        'No model was downloaded. No GitHub upload or release was performed.\n'
        'Application licensing/distribution review is still pending.\n')
    (folder/'START_EXECUTABLE.txt').write_text(notes,encoding='utf-8')
    paths=[folder/'ReflowStudio.exe',folder/'START_EXECUTABLE.txt',
           folder/'packaging/verify_payload.py',folder/'packaging/desktop_smoke.py']
    paths+=sorted(path for path in (folder/'_internal').rglob('*') if path.is_file())
    records=[]
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(folder):
            raise RuntimeError('Executable addition leaves candidate')
        with path.open('rb') as stream:
            records.append(dict(path=path.relative_to(folder).as_posix(),bytes=path.stat().st_size,sha256=sha(stream)))
    base_manifest=(folder/'portable-manifest.json').read_bytes()
    extension=dict(base_manifest_sha256=hashlib.sha256(base_manifest).hexdigest(),files=records,
                   launcher='ReflowStudio.exe',build_tool='PyInstaller 6.22.3',
                   owner_approved_build_tool_installed=True,working_audio_runtimes_changed=False,
                   model_downloads=False,release_ready=False)
    extension_bytes=json.dumps(extension,indent=2).encode('utf-8')
    (folder/'executable-manifest.json').write_bytes(extension_bytes)
    print('Copying verified base archive...',flush=True)
    shutil.copy2(original,archive)
    with archive.open('rb') as stream:
        if sha(stream)!=base['archive_sha256']:
            raise RuntimeError('Base ZIP copy differs from verified archive')
    with zipfile.ZipFile(archive,'a',compression=zipfile.ZIP_DEFLATED,strict_timestamps=False) as bundle:
        existing=set(bundle.namelist())
        for path,row in zip(paths,records):
            name=NAME+'/'+row['path']
            if name in existing: raise RuntimeError('Duplicate executable member')
            bundle.write(path,name)
        bundle.writestr(NAME+'/executable-manifest.json',extension_bytes)
    expected={NAME+'/'+row['path']:row['sha256'] for row in json.loads(base_manifest)['files']+records}
    expected[NAME+'/portable-manifest.json']=hashlib.sha256(base_manifest).hexdigest()
    expected[NAME+'/executable-manifest.json']=hashlib.sha256(extension_bytes).hexdigest()
    print('Verifying every executable ZIP member...',flush=True)
    with zipfile.ZipFile(archive) as bundle:
        if len(bundle.namelist())!=len(expected) or set(bundle.namelist())!=set(expected):
            raise RuntimeError('Executable ZIP inventory differs')
        for index,(name,digest) in enumerate(expected.items()):
            with bundle.open(name) as stream:
                if sha(stream)!=digest: raise RuntimeError('Executable ZIP content differs: '+name)
            if index%32768==0: print('Verified %d/%d files' % (index+1,len(expected)),flush=True)
    with archive.open('rb') as stream: digest=sha(stream)
    sums=archive.with_suffix('.SHA256SUMS.txt')
    sums.write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    report=dict(passed=True,archive=str(archive),bytes=archive.stat().st_size,sha256=digest,
                every_file_sha256_verified=True,executable_startup_passed=True,native_desktop_passed=True,
                files=len(expected),release_ready=False,clean_machine_test=False,
                github_single_asset_under_2_GiB=archive.stat().st_size<2*1024**3)
    (ROOT/'docs/validation/2026-10-31-executable-archive.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    main()
