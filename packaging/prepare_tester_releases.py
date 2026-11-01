"""Validate downloaded CI artifacts and prepare labelled RC2 tester assets.

No native code is run, no runtime is installed, and Mac/Linux native archives
are copied byte-for-byte to preserve signatures, links and executable modes.
"""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import posixpath
import shutil
import struct
import tarfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'release-assets/Releases'
OUTPUT=INPUT/'RC2'
TARGETS=('windows-x64','linux-x64','macos-arm64','macos-x64')
LABELS={'windows-x64':'Windows-x64','linux-x64':'Linux-x64',
        'macos-arm64':'macOS-Apple-Silicon','macos-x64':'macOS-Intel'}


def sha_file(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): value.update(block)
    return value.hexdigest()


def copy_checked(source,target,expected=None):
    if not target.resolve().is_relative_to(OUTPUT):
        raise ValueError('Copy destination leaves RC2 output')
    if target.exists(): raise RuntimeError('Refusing to replace '+str(target))
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)
    digest=sha_file(target)
    if digest!=(expected or sha_file(source)):
        raise RuntimeError('Copied asset checksum differs: '+target.name)
    return digest


def unwrap(outer,destination,expected_member):
    with zipfile.ZipFile(outer) as archive:
        names=archive.namelist()
        if expected_member not in names or expected_member+'.sha256' not in names:
            raise RuntimeError('Missing native archive/checksum: '+outer.name)
        checksum=archive.read(expected_member+'.sha256').decode('utf-8-sig').split()[0].lower()
        if len(checksum)!=64 or set(checksum)-set('0123456789abcdef'):
            raise RuntimeError('Invalid download checksum')
        with archive.open(expected_member) as source,destination.open('xb') as output:
            shutil.copyfileobj(source,output,1024*1024)
    if sha_file(destination)!=checksum:
        raise RuntimeError('Downloaded inner archive checksum differs')
    return checksum


def safe_member(name):
    path=PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or not path.parts:
        raise ValueError('Unsafe archive member: '+name)
    return path.parts[0],'/'.join(path.parts[1:])


def architecture(header,target):
    if target=='windows-x64':
        if header[:2]!=b'MZ' or len(header)<64: return False
        offset=struct.unpack_from('<I',header,60)[0]
        return (len(header)>=offset+6 and header[offset:offset+4]==b'PE\0\0'
                and struct.unpack_from('<H',header,offset+4)[0]==0x8664)
    if target=='linux-x64':
        return header[:4]==b'\x7fELF' and header[4:6]==b'\x02\x01' and struct.unpack_from('<H',header,18)[0]==62
    expected=0x0100000c if target=='macos-arm64' else 0x01000007
    if header[:4]==b'\xcf\xfa\xed\xfe':
        return struct.unpack_from('<I',header,4)[0]==expected
    if header[:4]==b'\xfe\xed\xfa\xcf':
        return struct.unpack_from('>I',header,4)[0]==expected
    if header[:4] in (b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca'):
        endian='>' if header[:4]==b'\xca\xfe\xba\xbe' else '<'
        count=struct.unpack_from(endian+'I',header,4)[0]
        return any(struct.unpack_from(endian+'I',header,8+i*20)[0]==expected
                   for i in range(min(count,(len(header)-8)//20)))
    return False


def inspect_native(path,target):
    files={};links={};hardlinks={};captured={};manifest=None;root_name=None
    wanted=('main.py','core/tray.py','core/tts/tts_handler.py')
    native=('ReflowStudio.app/Contents/MacOS/ReflowStudio' if target.startswith('macos')
            else 'ReflowStudio.exe' if target=='windows-x64' else 'ReflowStudio')
    payload_prefix='ReflowStudio.app/Contents/Resources/ReflowStudio/' if target.startswith('macos') else ''

    def consume(name,stream,size):
        nonlocal manifest,root_name
        top,relative=safe_member(name)
        if root_name is not None and top!=root_name: raise RuntimeError('Multiple archive roots')
        root_name=top
        digest=hashlib.sha256();parts=[];capture=(relative=='candidate-manifest.json' or relative in tuple(payload_prefix+n for n in wanted))
        header=b''
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block)
            if capture: parts.append(block)
            if relative==native and len(header)<4096: header=(header+block)[:4096]
        files[relative]=dict(bytes=size,sha256=digest.hexdigest())
        if capture:
            payload=b''.join(parts)
            if relative=='candidate-manifest.json': manifest=json.loads(payload)
            else: captured[relative.removeprefix(payload_prefix)]=payload
        if relative==native: captured['native_header']=header

    if target=='windows-x64':
        with zipfile.ZipFile(path) as archive:
            if len(archive.namelist())!=len(set(archive.namelist())): raise RuntimeError('Duplicate ZIP members')
            for item in archive.infolist():
                if item.is_dir(): continue
                with archive.open(item) as stream: consume(item.filename,stream,item.file_size)
    else:
        with tarfile.open(path,'r|gz') as archive:
            for item in archive:
                top,relative=safe_member(item.name)
                if item.isdir(): continue
                if item.issym():
                    resolved=posixpath.normpath(posixpath.join(posixpath.dirname(item.name),item.linkname))
                    if item.linkname.startswith('/') or not resolved.startswith(top+'/'):
                        raise RuntimeError('Archive symlink leaves application root')
                    links[relative]=item.linkname
                elif item.islnk():
                    link_top,link_relative=safe_member(item.linkname)
                    if link_top!=top: raise RuntimeError('Hardlink leaves archive root')
                    hardlinks[relative]=link_relative
                elif item.isfile():
                    with archive.extractfile(item) as stream: consume(item.name,stream,item.size)
                else: raise RuntimeError('Unexpected native archive member type')
    if not manifest or manifest['target']!=target:
        raise RuntimeError('Wrong platform manifest')
    for name in hardlinks:
        seen=set();reference=name
        while reference in hardlinks:
            if reference in seen: raise RuntimeError('Archive hardlink cycle')
            seen.add(reference);reference=hardlinks[reference]
        files[name]=files[reference]
    expected={row['path']:row for row in manifest['files']}
    for name,row in expected.items():
        if 'symlink' in row:
            if links.get(name)!=row['symlink']: raise RuntimeError('Native symlink differs: '+name)
        elif files.get(name)!=dict(bytes=row['bytes'],sha256=row['sha256']):
            raise RuntimeError('Native file differs from manifest: '+name)
    if set(files)|set(links)!=set(expected)|{'candidate-manifest.json'}:
        raise RuntimeError('Native inventory contains unexpected or missing files')
    if not architecture(captured.get('native_header',b''),target):
        raise RuntimeError('Native executable architecture differs from label')
    code={name:hashlib.sha256(value.replace(b'\r\n',b'\n')).hexdigest()
          for name,value in captured.items() if name!='native_header'}
    return dict(target=target,manifest_files=len(expected),every_manifest_file_verified=True,
                executable_architecture_verified=True,source_sha256_normalized=code,
                native_archive_unchanged=True,model_inference_verified=False)


def platform_guide(target):
    label=LABELS[target]
    launch=('Open ReflowStudio.exe and keep all companion files.' if target=='windows-x64'
            else 'Open ReflowStudio.app. Choose the Apple Silicon or Intel download matching your Mac.' if target.startswith('macos')
            else 'Extract with tar -xzf, then run ./ReflowStudio from the extracted folder. Keep its executable permissions.')
    return ('# Reflow Studio RC2 — '+label+' desktop preview\n\n'
        'This is a testing pre-release. The native archive is unchanged from the successful GitHub build.\n\n'
        '## Start\n\nExtract the native archive to a writable local folder. '+launch+'\n\n'
        'Python and desktop libraries are included. **Local AI engine runtimes, model weights and FFmpeg/FFprobe are not included in this desktop preview.** '
        'Those need compatible platform-specific setup before local dubbing can run. Models alone do not install the missing engine packages.\n\n'
        +('Windows needs WebView2 and the Visual C++ runtime. The larger Windows engine-bundle download is the preferred Windows dubbing candidate.\n\n' if target=='windows-x64'
          else 'Linux uses Qt. Native desktop/library compatibility varies by distribution.\n\n' if target=='linux-x64'
          else 'The Mac app is not Developer ID signed or notarized. If macOS blocks it, report the exact message. Writable-data/signing behavior is still under evaluation. Preserve the tar.gz archive format and its internal links.\n\n')+
        '## What to test\n\n'
        '1. Startup, visible interface, logo, menus and normal exit.\n'
        '2. Settings, Marketplace readiness messages, queue and file selection.\n'
        '3. If the required engines/models are installed: a short dub, subtitle export and audio/video synchronization.\n'
        '4. Cancellation, restart and recovery with disposable sample media.\n\n'
        'The CI check covered imports, application paths and basic package integrity. It did not generate a dub or certify a clean computer.\n\n'
        'Report issues at https://github.com/ananta-sj/ReFlow-Studio/issues using RC2, OS version, CPU/GPU, selected engines, steps, expected result and actual error. '
        'Remove credentials and private media from shared logs.\n')


def main():
    if OUTPUT.exists(): raise RuntimeError('RC2 output already exists; refusing replacement')
    OUTPUT.mkdir()
    (OUTPUT/'PREPARATION_STATUS.txt').write_text('IN PROGRESS — do not distribute yet.\n')
    assets=OUTPUT/'Upload-to-GitHub';assets.mkdir()
    reports={}
    for target in TARGETS:
        print('Verifying '+target+'...',flush=True)
        base='ReflowStudio-'+target+'-desktop-preview'
        extension='.zip' if target=='windows-x64' else '.tar.gz'
        name='ReflowStudio-RC2-'+LABELS[target]+'-Desktop-Preview'+extension
        digest=unwrap(INPUT/(base+'.zip'),assets/name,base+extension)
        (assets/(name+'.sha256')).write_text(digest+'  '+name+'\n',encoding='ascii')
        reports[target]=inspect_native(assets/name,target)
        with zipfile.ZipFile(INPUT/('checks-'+target+'.zip')) as checks:
            report=json.loads(checks.read('ci-'+target+'-smoke.json'))
        if not report['passed']: raise RuntimeError('CI smoke check did not pass: '+target)
        reports[target]['ci_desktop_smoke_passed']=True
        reports[target]['archive_sha256']=digest
        (assets/('TESTING-'+LABELS[target]+'.md')).write_text(platform_guide(target),encoding='utf-8')
    print('Verifying matching source export...',flush=True)
    source_name='ReflowStudio-RC2-Source.zip'
    source_digest=unwrap(INPUT/'ReflowStudio-source.zip',assets/source_name,'ReflowStudio-source.zip')
    (assets/(source_name+'.sha256')).write_text(source_digest+'  '+source_name+'\n',encoding='ascii')
    with zipfile.ZipFile(assets/source_name) as source:
        manifest=json.loads(source.read('ReflowStudio-source/SOURCE_MANIFEST.json'))
        for row in manifest['files']:
            payload=source.read('ReflowStudio-source/'+row['path'])
            if hashlib.sha256(payload).hexdigest()!=row['sha256']: raise RuntimeError('Source export differs')
        for name in ('main.py','core/tray.py','core/tts/tts_handler.py'):
            fingerprint=hashlib.sha256(source.read('ReflowStudio-source/'+name).replace(b'\r\n',b'\n')).hexdigest()
            if any(item['source_sha256_normalized'].get(name)!=fingerprint for item in reports.values()):
                raise RuntimeError('Platform packages do not share the same source: '+name)
    print('Preparing the fuller Windows engine bundle...',flush=True)
    windows=json.loads((ROOT/'docs/validation/2026-10-31-iconfix-archive.json').read_text())
    full_source=Path(windows['archive'])
    if not full_source.resolve().is_relative_to(ROOT/'dist'):
        raise ValueError('Windows source archive leaves the build output folder')
    full_folder=OUTPUT/'Windows-full-local';full_folder.mkdir()
    copy_checked(full_source,full_folder/full_source.name,windows['sha256'])
    (full_folder/'SHA256SUMS.txt').write_text(windows['sha256']+'  '+full_source.name+'\n')
    windows_parts=ROOT/'dist/github-windows-download-RC2'
    parts=json.loads((windows_parts/'download-manifest.json').read_text())
    if parts['source_sha256']!=windows['sha256']: raise RuntimeError('Windows parts refer to another build')
    for row in parts['parts']:
        if Path(row['name']).name!=row['name']:
            raise ValueError('Download part must be a simple filename')
        copy_checked(windows_parts/row['name'],assets/row['name'],row['sha256'])
    copy_checked(windows_parts/'Assemble-ReflowStudio.cmd',assets/'Assemble-ReflowStudio.cmd')
    copy_checked(windows_parts/'download-manifest.json',assets/'ReflowStudio-RC2-Windows-download-manifest.json')
    copy_checked(windows_parts/'README.txt',assets/'START-HERE-Windows-Engine-Bundle.txt')
    (assets/'START-HERE-Windows-Engine-Bundle.txt').write_text(
        'WINDOWS RC2 ENGINE BUNDLE\n\nDownload both .part files and Assemble-ReflowStudio.cmd into ONE folder.\n'
        'Run the CMD script to verify the parts and create the complete ZIP, then extract that ZIP.\n'
        'Open ReflowStudio.exe and keep all companion files.\n'
        'No extra archive tool is required. Existing ZIPs are not overwritten.\n'
        'Model downloads/reference setup are required before dubbing. See TESTING-Windows-Engine-Bundle.md.\n',encoding='utf-8')
    (assets/'TESTING-Windows-Engine-Bundle.md').write_text(
        '# Reflow Studio RC2 — Windows engine bundle\n\n'
        'Recommended Windows candidate. Download both .part files and Assemble-ReflowStudio.cmd into one folder. '
        'Run the script, extract the completed ZIP, then open ReflowStudio.exe in its folder. Keep all companion files.\n\n'
        'Includes Python, FFmpeg and eight prepared engine environments. Downloaded model weights, personal voice references, credentials and settings are excluded. '
        'Complete the selected model/reference setup before dubbing. Experimental IndicF5/IndicTrans2 evaluation environments and RVC voices are not bundled. '
        'Windows requires WebView2 and the appropriate Visual C++ runtime.\n\n'
        'Startup, native branding and archive-integrity checks passed locally. Fresh-PC and full final-package workflows need volunteer testing. '
        'Try a short dub first, then timing/subtitle export, cancellation and restart/recovery. '
        'Report OS, hardware, engines, steps and the exact error at https://github.com/ananta-sj/ReFlow-Studio/issues.\n',encoding='utf-8')
    (assets/'RC2-READ-ME-FIRST.md').write_text(
        '# Reflow Studio RC2 testing pre-release\n\n'
        '**RC2 means Release Candidate 2.** It is a candidate version, not a claim that every platform has completed full testing.\n\n'
        '| Download | Intended use |\n| --- | --- |\n'
        '| Windows .part files + Assemble-ReflowStudio.cmd | Fuller Windows engine bundle; recommended for Windows dubbing tests. |\n'
        '| Windows Desktop Preview.zip | Smaller desktop-only preview; local AI engines and FFmpeg need setup. |\n'
        '| Linux x64 Desktop Preview.tar.gz | Linux desktop testing; local AI engines and FFmpeg need setup. |\n'
        '| macOS Apple Silicon Desktop Preview.tar.gz | M-series Macs; desktop preview and separate engine setup. |\n'
        '| macOS Intel Desktop Preview.tar.gz | Intel Macs; desktop preview and separate engine setup. |\n'
        '| Source.zip | Matching CI application source, not a ready-to-run app. |\n\n'
        'Keep the Linux/Mac tar.gz format; its Unix permissions and links are preserved. Read the platform-specific TESTING guide before trying it. '
        'All native CI checks passed basic desktop/package checks; these did not test neural model inference. '
        'Mac signing/data layout, native engine support and fresh-machine behavior remain experimental. '
        'The application/component licensing decision remains pending. This package preparation does not publish a release or select a license.\n\n'
        'Please report problems at https://github.com/ananta-sj/ReFlow-Studio/issues, including RC2, platform/architecture, OS version, hardware, engines, reproduction steps and the error. '
        'Do not include credentials or private media in shared reports.\n',encoding='utf-8')
    (assets/'RC2-TEST-FEEDBACK.md').write_text(
        '# RC2 test report\n\n'
        '- Download filename:\n- OS and version:\n- CPU/architecture:\n- GPU and memory:\n'
        '- Does the app open?\n- Do the interface, taskbar/tray icon and file selection work?\n'
        '- Selected transcription/translation/speech engines:\n- Models and runtimes installed:\n'
        '- Source and target language:\n- Short input duration/type:\n'
        '- Steps to reproduce:\n- Expected result:\n- Actual result/error:\n'
        '- Audio quality and synchronization, if dubbing was tested:\n'
        '- Cancellation/restart/recovery result:\n\n'
        'Submit to https://github.com/ananta-sj/ReFlow-Studio/issues. Remove credentials and private media from logs.\n',encoding='utf-8')
    sums=[]
    for path in sorted(assets.iterdir()):
        if path.stat().st_size>=2*1024**3: raise RuntimeError('Release upload asset exceeds 2 GiB: '+path.name)
        sums.append(sha_file(path)+'  '+path.name)
    (assets/'SHA256SUMS.txt').write_text('\n'.join(sums)+'\n',encoding='ascii')
    summary=dict(preparation_complete=True,release_label='RC2',release_type='pre-release',production_ready=False,
                 native_archives_preserved=True,native_rebuild_performed=False,platforms=reports,
                 source_sha256=source_digest,windows_engine_bundle_sha256=windows['sha256'],
                 every_upload_asset_under_2_GiB=True,software_installed=False,models_downloaded=False,published=False)
    (OUTPUT/'VALIDATION.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (OUTPUT/'UPLOAD-INSTRUCTIONS.txt').write_text(
        'Attach all files inside Upload-to-GitHub to a GitHub pre-release. Do not attach the folder itself.\n'
        'Windows-full-local contains the complete large Windows ZIP for local use; use its .part downloads for GitHub.\n'
        'The original downloaded artifacts/checks remain unchanged in the parent Releases folder.\n'
        'Label Linux/macOS and the small Windows package as desktop previews. They are not full AI engine bundles.\n'
        'Read RC2-READ-ME-FIRST.md and the testing guides. This preparation does not publish anything.\n',encoding='utf-8')
    (OUTPUT/'PREPARATION_STATUS.txt').write_text('COMPLETE — archive and architecture checks passed. Prepared as a testing pre-release; not production certified.\n')
    print(json.dumps(dict(prepared=str(OUTPUT),upload_folder=str(assets),platforms=list(reports)),indent=2),flush=True)


if __name__=='__main__': main()
