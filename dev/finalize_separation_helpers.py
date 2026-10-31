"""Verify the approved preparation, preserve lock/evidence and clean owned staging."""
import json
import os
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'dev')]
from core.runtime_integrity import sha


def main():
    from core.xtts_runtime import validate as xtts
    from core.nllb_runtime import validate as nllb
    from core.m2m100_runtime import validate as translation
    from core.recognition_runtime import validate as recognition
    folder=ROOT/'docs/validation';prefix='2026-10-16-separation-runtime'
    plan_path=folder/(prefix+'-proposal.json');plan=json.loads(plan_path.read_text())
    review=json.loads((folder/(prefix+'-independent-review.json')).read_text())
    resolver=json.loads((folder/(prefix+'-resolution-receipt.json')).read_text())
    resolution=json.loads((folder/(prefix+'-resolution-report.json')).read_text(encoding='utf-8'))
    builds=json.loads((folder/'2026-10-16-separation-helpers/build-receipt.json').read_text())
    smoke=json.loads((folder/'2026-10-16-separation-helpers-smoke.json').read_text())
    assert review['passed'] and review['proposal_sha256']==sha(plan_path) and resolver['proposal_sha256']==sha(plan_path)
    assert resolver['resolution_verified'] and builds['passed'] and smoke['passed']
    assert review['advisory_complete'] and review['advisory_matches']==0
    baseline=json.loads((folder/'2026-10-10-control-paths-state-integrity.json').read_text())['state']
    assert all(sha(ROOT/name)==row['current'].lower() for name,row in baseline.items())
    previous=json.loads((folder/'2026-10-16-separation-iteration-acceptance.json').read_text())
    assert all(sha(ROOT/name)==digest for name,digest in previous['source_sha256'].items() if name.startswith('core/'))
    identities=dict(xtts=xtts()['identity'],nllb=nllb()['identity'],translation=translation()['identity'],recognition=recognition()['identity'])
    assert identities==previous['identities']
    from core.audio_separator import DEMUCS_SHA256
    assert sha(ROOT/'models/uvr/955717e8-8726e21a.th')==DEMUCS_SHA256
    assert not (ROOT/plan['proposed_profile']).exists()
    for row in builds['packages']:
        assert sha(ROOT/row['wheel'])==row['wheel_sha256']
    for row in plan['packages']:
        if row['source']=='copy-existing':
            metadata=ROOT/row['source_metadata'];assert sha(metadata)==row['metadata_sha256']
            assert sha(metadata.parent/'RECORD')==row['record_sha256']
    supplement=review['antlr_notice_supplement'];assert sha(ROOT/supplement['file'])==supplement['sha256']
    stage=ROOT/'temp/separation-helpers-2026-10-16'
    assert stage.resolve()==Path('C:/Projects/Reflow Studio/temp/separation-helpers-2026-10-16').resolve()
    assert stage.parent.resolve()==(ROOT/'temp').resolve() and (stage/'.owner').read_text()=='reflow.approved.separation.helpers.2026-10-16'
    total=0
    for directory,dirs,files in os.walk(stage,followlinks=False):
        for entry in [Path(directory),*(Path(directory)/name for name in dirs+files)]:
            assert entry.resolve().is_relative_to(stage.resolve()) and not entry.is_symlink() and not getattr(entry.lstat(),'st_file_attributes',0)&0x400
            if entry.is_file():total+=entry.stat().st_size
    shutil.rmtree(stage)
    assert not stage.exists()
    # Preserve the proposal as history; the accepted planning lock is separate.
    from packaging.utils import canonicalize_name
    resolved={canonicalize_name(row['metadata']['name']):row for row in resolution['install']}
    lock=dict(plan)
    lock.update(schema='reflow.separation.prepared-lock.v1',pip_resolver_verified=True,independent_review_passed=True,
        ready_for_installation_proposal=True,install_authorized=False,ready_to_install=False,
        helper_smoke_checks=len(smoke['checks']),full_demucs_inference_verified=False,
        antlr_notice_supplement=supplement,distribution_rights_cleared=False,
        advisory_receipt=prefix+'-advisories.json',proposal_sha256=sha(plan_path))
    for row in lock['packages']:
        row['resolved_artifact']=resolved[row['name']]['download_info']
    lock_path=folder/(prefix+'-lock-review.json');assert not lock_path.exists();lock_path.write_text(json.dumps(lock,indent=2),encoding='utf-8')
    sources=['dev/build_approved_separation_helpers.py','dev/evaluate_separation_helpers.py',
        'dev/prepare_separation_runtime_lock.py','dev/resolve_separation_lock_metadata.py',
        'dev/audit_separation_prepared_lock.py','dev/finalize_separation_helpers.py']
    result=dict(passed=True,approved_source_archives=4,approved_source_archive_bytes=sum(row['source']['bytes'] for row in builds['packages']),
        built_wheels=4,built_wheel_bytes=sum(row['wheel_bytes'] for row in builds['packages']),
        verified_python_sources=sum(row['python_sources_verified'] for row in builds['packages']),
        helper_smoke_checks=len(smoke['checks']),package_count=plan['package_count'],active_dependency_edges=review['active_dependency_edges'],
        resolver_verified=True,advisory_complete=True,advisory_matches=0,owned_staging_removed=True,staging_bytes_removed=total,
        protected_state_and_production_sources_preserved=True,runtime_identities_preserved=identities,
        runtime_installed=False,defaults_changed=False,models_downloaded=False,release_ready=False,
        distribution_rights_cleared=False,full_demucs_inference_verified=False,
        lock_sha256=sha(lock_path),source_sha256={name:sha(ROOT/name) for name in sources})
    (folder/'2026-10-16-separation-helpers-acceptance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
