"""Preserve prepared visual lock, verify originals, and remove only owned staging."""
import json,os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'core')]
from core.runtime_integrity import sha,safe_path

def main():
    out=ROOT/'docs/validation';prefix='2026-10-16-visual-runtime'
    read=lambda name:json.loads((out/name).read_text(encoding='utf-8'))
    plan_path=out/(prefix+'-proposal.json');plan=read(prefix+'-proposal.json')
    audit=read(prefix+'-independent-review.json');resolver=read(prefix+'-resolution-receipt.json')
    builds=read('2026-10-16-visual-helpers/build-receipt.json');smoke=read('2026-10-16-visual-helpers-smoke.json')
    checks={}
    checks['two_approved_helpers_built']=builds['passed'] and len(builds['packages'])==2 and sum(row['source']['bytes'] for row in builds['packages'])==350509
    checks['wheels_and_records_verified']=all(row['record_verified'] and sha(ROOT/row['wheel'])==row['wheel_sha256'] for row in builds['packages'])
    checks['129_python_sources_verified']=sum(row['python_sources_verified'] for row in builds['packages'])==129
    checks['both_helper_notices_present']=all(row['notice_files'] for row in builds['packages'])
    checks['python313_smoke_passed']=smoke['passed'] and all(smoke['checks'].values())
    checks['resolver_and_independent_review_passed']=audit['passed'] and resolver['resolution_verified'] and audit['proposal_sha256']==sha(plan_path)==resolver['proposal_sha256']
    advisory=read(prefix+'-advisories.json')
    checks['point_in_time_advisories_reviewed']=audit['advisory_complete'] and audit['advisory_matches']==2 and len(advisory['matches'])==1 and advisory['matches'][0]['package']=='basicsr'
    details=[read('2026-10-16-visual-'+name+'.json') for name in ['GHSA-86w8-vhw6-q9qq','PYSEC-2026-1215']]
    checks['advisory_aliases_confirmed']=all('CVE-2024-27763' in row['aliases'] for row in details)
    guard=read('2026-10-16-visual-guard-prototype.json')
    checks['no_install_guard_prototype_passed']=guard['passed'] and guard['launchers_blocked']==3 and guard['shell_calls']==0 and guard['nondistributed_helpers_preserved']
    baseline=read('2026-10-10-control-paths-state-integrity.json')['state']
    checks['protected_state_preserved']=all(sha(ROOT/name)==row['current'].lower() for name,row in baseline.items())
    previous=read('2026-10-16-f5-startup-acceptance.json')
    checks['latest_production_sources_preserved']=all(sha(ROOT/name)==digest for name,digest in previous['source_sha256'].items() if name.startswith('core/'))
    other=read('2026-10-16-remaining-engines-acceptance.json')
    checks['preceding_engine_sources_preserved']=all(sha(ROOT/name)==digest for name,digest in other['source_sha256'].items() if name.startswith('core/'))
    from core.separation_runtime import validate as separation
    from core.xtts_runtime import validate as xtts
    from core.nllb_runtime import validate as nllb
    from core.recognition_runtime import validate as recognition
    from core.m2m100_runtime import validate as translation
    identities={name:call()['identity'] for name,call in [('separation',separation),('xtts',xtts),('nllb',nllb),('recognition',recognition),('translation',translation)]}
    checks['five_runtime_identities_preserved']=identities==previous['runtime_identities']
    checks['no_visual_runtime_created']=not (ROOT/plan['proposed_profile']).exists()
    checks['copied_package_metadata_preserved']=all(sha(ROOT/row['source_metadata'])==row['metadata_sha256'] and sha((ROOT/row['source_metadata']).parent/'RECORD')==row['record_sha256'] for row in plan['packages'] if row['source']=='copy-existing')
    # Retain references to tested existing F5 assets rather than rehash unrelated model families.
    speech=read('2026-10-16-f5-lazy-speech-final.json')
    checks['tested_f5_assets_preserved']=all(sha(ROOT/name)==digest for name,digest in speech['asset_sha256'].items())
    separation_evidence=read('2026-10-16-separation-candidate-acceptance.json')
    checks['built_frontend_preserved']=all(sha(ROOT/name)==digest for name,digest in separation_evidence['frontend_dist_sha256'].items())
    assert all(checks.values()),checks
    lock=dict(plan);lock.update(schema='reflow.visual.prepared-lock.v1',pip_resolver_verified=True,independent_review_passed=True,install_authorized=False,ready_to_install=False,
        advisory_receipt=prefix+'-advisories.json',security_clear=False,advisory_records=2,distinct_cves=['CVE-2024-27763'],
        required_mitigation='Disable reviewed BasicSR distributed training launch paths before any isolated visual inference; test exact-source guard without shell execution.',
        distribution_rights_cleared=False,full_gfpgan_inference_verified=False,proposal_sha256=sha(plan_path))
    resolution=read(prefix+'-resolution-report.json')
    from packaging.utils import canonicalize_name
    resolved={canonicalize_name(row['metadata']['name']):row for row in resolution['install']}
    lock['packages']=[{**row,'resolved_artifact':resolved[row['name']]['download_info']} for row in plan['packages']]
    lock_path=out/(prefix+'-lock-review.json');assert not lock_path.exists();lock_path.write_text(json.dumps(lock,indent=2),encoding='utf-8')
    stage=ROOT/'temp/visual-helpers-2026-10-16'
    assert safe_path(stage).resolve()==Path('C:/Projects/Reflow Studio/temp/visual-helpers-2026-10-16').resolve()
    assert stage.parent.resolve()==(ROOT/'temp').resolve() and (stage/'.owner').read_text()=='reflow.approved.visual.helpers.2026-10-16'
    total=0
    for folder,dirs,files in os.walk(stage,followlinks=False):
        for path in [Path(folder),*(Path(folder)/name for name in dirs+files)]:
            assert safe_path(path).resolve().is_relative_to(stage.resolve())
            if path.is_file():total+=path.stat().st_size
    shutil.rmtree(stage);checks['owned_staging_removed']=not stage.exists()
    sources=['dev/build_approved_visual_helpers.py','dev/evaluate_visual_helpers.py','dev/prepare_visual_runtime_lock.py','dev/resolve_visual_lock_metadata.py','dev/audit_visual_prepared_lock.py','dev/review_visual_source_guard.py','dev/finalize_visual_helpers.py']
    report=dict(passed=all(checks.values()),checks=checks,approved_archive_bytes=350509,built_wheel_bytes=sum(row['wheel_bytes'] for row in builds['packages']),verified_python_sources=129,
        helper_smoke_checks=len(smoke['checks']),packages=plan['package_count'],dependency_edges=audit['active_dependency_edges'],
        proposed_download_bytes=plan['pending_download_bytes'],staging_bytes_removed=total,runtime_identities=identities,
        runtime_installed=False,models_downloaded=False,defaults_changed=False,release_ready=False,distribution_rights_cleared=False,
        security_clear=False,advisory_records=2,distinct_cves=['CVE-2024-27763'],
        lock_sha256=sha(lock_path),source_sha256={name:sha(ROOT/name) for name in sources})
    (out/'2026-10-16-visual-helpers-acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
