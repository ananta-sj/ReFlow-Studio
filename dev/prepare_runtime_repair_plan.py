"""Generate a review plan from captured metadata, never an installable lock."""
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
from packaging.requirements import Requirement, InvalidRequirement
from packaging.specifiers import SpecifierSet
from packaging.tags import cpython_tags, compatible_tags
from packaging.utils import parse_wheel_filename

OUT=ROOT/'docs/validation'
PINS={
    'coqui-tts':('0.27.5','Maintained library for the existing XTTS model, in its own candidate worker'),
    'torch':('2.9.1+cpu','CPU inference proof before a separate approved GPU evaluation'),
    'torchaudio':('2.9.1+cpu','Matching Torch audio implementation'),
    'torchcodec':('0.8.1','Audio decoding paired with Torch 2.9 and existing shared FFmpeg'),
    'numpy':('2.3.5','CPython 3.13 numerical wheel; old RVC cap cannot share this environment'),
    'scipy':('1.16.3','Speech signal processing; satisfies maintained Coqui requirement'),
    'transformers':('4.57.1','Coqui minimum 4.57; preserves below-5 candidate boundary'),
    'numba':('0.63.1','Compiled numeric operations used by the audio dependency chain'),
    'llvmlite':('0.46.0','Compiler library required by this Numba version, supplied as a wheel'),
    'soundfile':('0.13.1','Audio loading and writing using the existing interface'),
    'anyascii':('0.3.3','Maintained Coqui text transliteration requirement'),
    'aiohttp':('3.14.3','HTTP helper for fsspec[http]; final dependency closure must confirm this edge'),
    'pydub':('0.25.1','Existing Reflow audio preparation and validation'),
    'audioop-lts':('0.2.2','Provides audioop removed from Python 3.13, needed by pydub'),
}
CORE={
    'pywebview':'6.2.1','pythonnet':'3.1.0','psutil':'7.2.2','pydub':'0.25.1',
    'audioop-lts':'0.2.2','pillow':'11.3.0','keyring':'25.7.0','pystray':'0.19.5',
    'requests':'2.32.5','filelock':'3.20.3','cffi':'2.0.0','soundfile':'0.13.1','packaging':'26.0',
}


def main():
    metadata=json.loads((OUT/'2026-10-13-runtime-repair-metadata.json').read_text(encoding='utf-8'))
    indexed={(item['name'].lower(),item['version']):item for item in metadata['packages'] if 'version' in item}
    target=set(cpython_tags(python_version=(3,13),abis=['cp313'],platforms=['win_amd64']))
    target.update(compatible_tags(python_version=(3,13),interpreter='cp313',platforms=['win_amd64']))

    def candidates(name,version):
        base=version.split('+')[0]
        row=indexed[(name,base)]
        wheels=[]
        for artifact in row['artifacts']:
            if artifact['yanked'] or not artifact['filename'].endswith('.whl'):continue
            _,_,_,tags=parse_wheel_filename(artifact['filename'])
            if target & tags: wheels.append(artifact)
        return row,wheels

    selected=[]
    for name,(version,reason) in PINS.items():
        row,wheels=candidates(name,version)
        entry=dict(name=name,version=version,why=reason,metadata_source=row['source'],
            python_requirement=row.get('requires_python'),
            python_compatible=not row.get('requires_python') or '3.13.16' in SpecifierSet(row['requires_python']),
            compatible_wheels=wheels,requires_dist=row['requires_dist'])
        if name in ('torch','torchaudio','torchcodec'):
            index=next(item for item in metadata['pytorch_cpu_index_candidates'] if item['name']==name)
            if len(index['artifact_links'])!=1: raise ValueError('Expected one official CPU artifact')
            link=urljoin(index['source'],index['artifact_links'][0])
            digest=urlsplit(link).fragment.removeprefix('sha256=')
            if len(digest)!=64:raise ValueError('CPU artifact lacks a published hash')
            entry['official_cpu_artifact']=dict(url=link.split('#')[0],sha256=digest,
                filename=unquote(urlsplit(link).path.rsplit('/',1)[1]))
        selected.append(entry)

    core=[]
    for name,version in CORE.items():
        row,wheels=candidates(name,version)
        core.append(dict(name=name,version=version,source=row['source'],
            python_compatible=not row.get('requires_python') or '3.13.16' in SpecifierSet(row['requires_python']),
            compatible_wheels=wheels))
    omega=indexed[('omegaconf','2.0.6')]
    malformed=[]
    for value in omega['requires_dist']:
        try:Requirement(value)
        except InvalidRequirement:malformed.append(value)
    fairseq=indexed[('fairseq','0.12.2')]
    fairseq_windows=[item['filename'] for item in fairseq['artifacts'] if 'win' in item['filename'] and item['filename'].endswith('.whl')]
    coqui=indexed[('coqui-tts','0.27.5')]
    _,legacy_numpy=candidates('numpy','1.26.4')
    checks=dict(all_candidate_roots_have_python313_wheels=all(item['compatible_wheels'] for item in selected),
        all_candidate_roots_allow_python313=all(item['python_compatible'] for item in selected),
        all_gui_candidate_roots_have_python313_wheels=all(item['compatible_wheels'] for item in core),
        all_gui_candidate_roots_allow_python313=all(item['python_compatible'] for item in core),
        modern_coqui_numpy_constraint_accepts_candidate='2.3.5' in Requirement(next(value for value in coqui['requires_dist'] if value.startswith('numpy'))).specifier,
        modern_coqui_scipy_constraint_accepts_candidate='1.16.3' in Requirement(next(value for value in coqui['requires_dist'] if value.startswith('scipy'))).specifier,
        numba_numpy_constraint_accepts_candidate='2.3.5' in Requirement(next(value for value in indexed[('numba','0.63.1')]['requires_dist'] if value.startswith('numpy'))).specifier,
        numba_llvmlite_constraint_accepts_candidate='0.46.0' in Requirement(next(value for value in indexed[('numba','0.63.1')]['requires_dist'] if value.startswith('llvmlite'))).specifier,
        scipy_numpy_constraint_accepts_candidate='2.3.5' in Requirement(next(value for value in indexed[('scipy','1.16.3')]['requires_dist'] if value.startswith('numpy'))).specifier,
        rvc_numpy_constraint_rejects_shared_candidate='2.3.5' not in Requirement(next(value for value in indexed[('rvc-python','0.1.5')]['requires_dist'] if value.startswith('numpy'))).specifier,
        malformed_legacy_requirement_detected=bool(malformed),fairseq_has_no_windows_wheel=not fairseq_windows,
        legacy_numpy_has_no_python313_wheel=not legacy_numpy,
        python_archive_has_published_sha256=len(metadata['python_candidate'].get('sha256') or '')==64)
    baseline=json.loads((OUT/'2026-10-10-control-paths-state-integrity.json').read_text(encoding='utf-8'))
    state={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==item['current'].lower() for name,item in baseline['state'].items()}
    checks['protected_app_state_unchanged']=all(state.values())
    resolution_path=OUT/'2026-10-13-metadata-only-scoped-mirror-receipt.json'
    if not resolution_path.exists(): resolution_path=OUT/'2026-10-13-metadata-only-resolution-receipt.json'
    resolution=json.loads(resolution_path.read_text(encoding='utf-8'))
    closure_path=OUT/'2026-10-13-xtts-candidate-lock-review.json'
    closure=json.loads(closure_path.read_text(encoding='utf-8')) if closure_path.exists() else {}
    helper_path=OUT/'2026-10-13-docopt-helper/receipt.json'
    helper=json.loads(helper_path.read_text(encoding='utf-8')) if helper_path.exists() else {}
    docopt=indexed[('docopt','0.6.2')]
    report=dict(schema='reflow.runtime-repair.plan.v1',planning_checks_passed=all(checks.values()),
        install_authorized=False,installable_lock=False,full_transitive_resolution_completed=closure.get('metadata_closure_valid',False),
        runtime_installed=False,model_downloaded=False,release_ready=False,python=metadata['python_candidate'],
        xtts_candidate_roots=selected,gui_candidate_roots=core,checks=checks,state=state,
        rvc_blockers=dict(version='0.1.5',numpy_cap='<=1.23.5',omegaconf_pin='2.0.6',
            malformed_requirements=malformed,fairseq_pin='0.12.2',windows_wheels=fairseq_windows),
        xtts_resolution=dict(exit_code=resolution['exit_code'],complete=resolution['resolution_complete'],
            metadata_requests=len(resolution['requests']),source_only_helper=dict(name='docopt',version='0.6.2',
                required_by='num2words, required by coqui-tts',artifacts=docopt['artifacts'],
                source_build_authorized=bool(helper.get('build_passed')),python313_execution_verified=False,
                build_receipt=str(helper_path.relative_to(ROOT)) if helper else None)),
        candidate_lock_review=dict(packages=len(closure.get('packages',[])),
            metadata_closure_valid=closure.get('metadata_closure_valid',False),
            excluded_host_marker_packages=closure.get('excluded_host_marker_packages',[]),
            artifact_download_bytes=closure.get('artifact_download_bytes'),
            download_size_verified=closure.get('download_size_verified',False),
            actual_runtime_acceptance=False),
        required_before_install=['Freeze and review complete transitive dependencies and hashes',
            'Check sources/wheel availability and exact total storage/download budget',
            'Obtain user approval for candidate creation, package downloads and support dependencies'],
        required_after_install=['No duplicate metadata, dependency checks pass','Actual decoding and XTTS model execution',
            'Cancellation, publication and persistent-session lifetime','Package vulnerability/notice inventory',
            'Native app bridge, relocation and clean Windows acceptance'])
    path=OUT/'2026-10-13-runtime-repair-plan.json';path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(planning_checks_passed=report['planning_checks_passed'],checks=checks,
        installable_lock=False,runtime_installed=False),indent=2))
    return 0 if report['planning_checks_passed'] else 1


if __name__=='__main__':raise SystemExit(main())
