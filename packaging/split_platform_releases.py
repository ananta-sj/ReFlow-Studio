"""Prepare four independent GitHub pre-release upload sets from verified RC2."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'release-assets/Releases/RC2'
VERSION='v0.7.0-rc.2'
SPECS=(
    ('Windows-x64','windows-x64','Windows x64',None,'TESTING-Windows-Engine-Bundle.md'),
    ('Linux-x64','linux-x64','Linux x64 Desktop Preview','ReflowStudio-RC2-Linux-x64-Desktop-Preview.tar.gz','TESTING-Linux-x64.md'),
    ('macOS-Apple-Silicon','macos-arm64','macOS Apple Silicon Desktop Preview','ReflowStudio-RC2-macOS-Apple-Silicon-Desktop-Preview.tar.gz','TESTING-macOS-Apple-Silicon.md'),
    ('macOS-Intel','macos-x64','macOS Intel Desktop Preview','ReflowStudio-RC2-macOS-Intel-Desktop-Preview.tar.gz','TESTING-macOS-Intel.md'),
)


def sha(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): value.update(block)
    return value.hexdigest()


def release_body(label,target,windows):
    beginning=('# ReFlow Studio '+VERSION+' — '+label+'\n\n'
        'This is a **volunteer-testing pre-release**. RC2 means Release Candidate 2; '
        'the shared release version is **'+VERSION+'**. Please test on real hardware and report issues.\n\n')
    if windows:
        setup=('## Windows download\n\n'
            'Download both `.part` files and `Assemble-ReflowStudio.cmd` into one folder. '
            'Run the script, extract the verified ZIP, then open **ReflowStudio.exe**. Keep all companion folders.\n\n'
            'Includes Python, FFmpeg and eight prepared engine environments. Downloaded model weights, '
            'personal voice references and credentials are excluded. Complete the selected engine/model/reference setup before dubbing. '
            'WebView2 and the appropriate Visual C++ runtime are required.\n\n'
            'This release uses the fuller Windows engine bundle.\n\n')
    else:
        launch=('Extract on Linux and run `./ReflowStudio`.' if target=='linux-x64'
                else 'Extract on your Mac and open `ReflowStudio.app`. This download is for '+('Apple M-series chips.' if target=='macos-arm64' else 'Intel Macs.'))
        setup=('## Platform download\n\n'+launch+' Keep all companion files and preserve executable permissions and links.\n\n'
            '**Desktop preview:** Python and desktop libraries are included. Local AI engine runtimes, '
            'model weights and FFmpeg/FFprobe require separate, compatible setup. Downloading models alone '
            'does not install the missing engine packages, so local dubbing is not ready out of the box.\n\n'
            +('Linux uses the Qt backend; distribution-specific native dependencies need testing.\n\n' if target=='linux-x64'
              else 'The app is not Developer ID signed or notarized. Mac writable-data/signing and native engine behavior remain under evaluation.\n\n'))
    return beginning+setup+(
        '## Volunteer testing\n\n'
        'Test startup, branding, menus, settings, file selection, Marketplace readiness and queues. '
        'When compatible engines/models are available, try a short dub, pronunciation/voice quality, '
        'audio/video timing, subtitle/audio export, cancellation and restart/recovery.\n\n'
        'Report issues at https://github.com/ananta-sj/ReFlow-Studio/issues using **'+VERSION+' / '+label+'**, '
        'your OS version, CPU/GPU, download filename, engines/models, reproduction steps and exact error. '
        'Use the included feedback template and remove credentials/private media from shared logs.\n\n'
        '## Validation and limits\n\n'
        +('Local Windows startup, native branding and archive-integrity checks passed.\n\n' if windows
          else 'Native CI desktop checks passed, and archive manifests/checksums and CPU architecture were verified. Native archive bytes are unchanged.\n\n')+
        'These checks do not establish complete model inference or clean-machine acceptance on every system. '
        'This is not a stable production release. Application/component licensing review remains pending.\n\n'
        'Read the included README and platform testing guide. Checksum files are supplied. '
        'GitHub’s automatic Source code archives contain source, not the ready-to-run application.\n')


def main():
    source=BASE/'Upload-to-GitHub'
    if not source.is_dir(): source=BASE/'_reference/combined-upload'
    if not source.is_dir(): raise RuntimeError('Verified combined RC2 set is missing')
    if any((BASE/spec[0]).exists() for spec in SPECS):
        raise RuntimeError('A platform release folder already exists; refusing replacement')
    expected={}
    for line in (source/'SHA256SUMS.txt').read_text().splitlines():
        digest,name=line.split('  ',1);expected[name]=digest
    parts=json.loads((source/'ReflowStudio-RC2-Windows-download-manifest.json').read_text())
    summaries=[]
    for directory,target,label,native,guide in SPECS:
        print('Preparing '+label+'...',flush=True)
        folder=BASE/directory;upload=folder/'Upload-to-GitHub'
        upload.mkdir(parents=True)
        files=[guide,'RC2-TEST-FEEDBACK.md']
        if native:
            files += [native,native+'.sha256']
        else:
            files += [row['name'] for row in parts['parts']]
            files += ['Assemble-ReflowStudio.cmd','ReflowStudio-RC2-Windows-download-manifest.json',
                      'START-HERE-Windows-Engine-Bundle.txt']
        for name in files:
            if Path(name).name!=name or name not in expected: raise ValueError('Unexpected upload filename')
            destination=upload/name
            shutil.copy2(source/name,destination)
            if sha(destination)!=expected[name]: raise RuntimeError('Platform asset copy differs: '+name)
        readme=(ROOT/'README.md').read_text(encoding='utf-8')
        if VERSION not in readme: raise RuntimeError('Project README has a different version')
        for link in ('docs/GITHUB_NATIVE_BUILDS.md','docs/GITHUB_UPLOAD_GUIDE.md',
                     'docs/RC2_PLATFORM_RELEASES.md','packaging/README.md'):
            readme=readme.replace(']('+link+')','](https://github.com/ananta-sj/ReFlow-Studio/blob/main/'+link+')')
        (upload/'README.md').write_text(readme,encoding='utf-8')
        tag=target+'-'+VERSION
        title='ReFlow Studio '+VERSION+' — '+label
        body=release_body(label,target,native is None)
        (folder/'RELEASE-NOTES.md').write_text(body,encoding='utf-8')
        details=('# GitHub release fields\n\n'
            '- **Version:** `'+VERSION+'`\n- **Tag:** `'+tag+'`\n- **Target:** the same updated source commit on `main` for all four releases\n'
            '- **Title:** '+title+'\n- **This is a pre-release:** select it\n\n'
            'Paste `RELEASE-NOTES.md` into the description and attach **only the files inside this folder’s `Upload-to-GitHub` directory**. '
            'Do not attach another platform’s downloads or the parent folder. GitHub supplies source archives from the selected tag. '
            'No release is created by this file.\n\n'
            'The platform-prefixed tag distinguishes this release while keeping the common version '+VERSION+'. '
            'It does not match the workflow’s automatic `v*` tag trigger, so publishing these existing assets does not schedule four duplicate full build matrices.\n')
        (folder/'RELEASE-DETAILS.md').write_text(details,encoding='utf-8')
        checks=[]
        for path in sorted(upload.iterdir()):
            if path.stat().st_size>=2*1024**3: raise RuntimeError('Upload file exceeds GitHub asset size')
            checks.append(sha(path)+'  '+path.name)
        (upload/'SHA256SUMS.txt').write_text('\n'.join(checks)+'\n',encoding='ascii')
        summaries.append(dict(platform=target,folder=directory,tag=tag,title=title,
                              version=VERSION,asset_count=len(checks)+1,
                              original_native_bytes_preserved=True,prerelease=True))
    (BASE/'RELEASE-SETS.json').write_text(json.dumps(dict(version=VERSION,
        separate_platform_releases=summaries,published=False,software_installed=False),indent=2),encoding='utf-8')
    (BASE/'UPLOAD-INSTRUCTIONS.txt').write_text(
        'v0.7.0-rc.2 — FOUR SEPARATE PRE-RELEASES\n\n'
        'Open Windows-x64, Linux-x64, macOS-Apple-Silicon or macOS-Intel.\n'
        'Each folder has RELEASE-DETAILS.md (tag/title), RELEASE-NOTES.md (description), and Upload-to-GitHub (attach all files inside).\n'
        'Create a separate pre-release for each platform, targeting the same updated source commit.\n'
        'Use each supplied distinct platform-prefixed tag. Mark all four as pre-releases.\n'
        'Windows uses the fuller engine bundle. Linux and Mac remain desktop previews requiring engine/model/FFmpeg setup.\n'
        'Windows-x64/Local-only holds the large full ZIP for local use, not a GitHub upload.\n'
        'Older combined downloads are retained under _reference. Nothing has been uploaded or published.\n',encoding='utf-8')
    print(json.dumps(summaries,indent=2),flush=True)


if __name__=='__main__': main()
