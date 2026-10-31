"""Current-source acceptance, package notices and bounded installer cleanup."""
import csv,json,os,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'core')]
from core.runtime_integrity import sha,safe_path

def main():
    from core.separation_runtime import validate,model_contract,LOCK
    from core.xtts_runtime import validate as xtts
    from core.nllb_runtime import validate as nllb
    from core.recognition_runtime import validate as recognition
    from core.m2m100_runtime import validate as translation
    folder=ROOT/'docs/validation';route=validate();model_contract(verify_weights=True)
    lock=json.loads((ROOT/LOCK).read_text());build=json.loads((folder/'2026-10-16-separation-candidate-build.json').read_text());assert build['completed']
    receipts={name:json.loads((folder/file).read_text(encoding='utf-8')) for name,file in {
        'real':'2026-10-16-separation-candidate-real.json','native':'2026-10-16-separation-candidate-native.json',
        'interface':'2026-10-16-separation-routing-native.json','video':'2026-10-16-separation-video.json'}.items()}
    assert all(row['passed'] for row in receipts.values())
    assert receipts['real']['runtime']['identity']==route['identity']==receipts['native']['runtime_identity']
    tests={}
    for name,file in [('backend','2026-10-16-separation-routing-full-backend.log'),('focused','2026-10-16-separation-routing-focused-complete.log')]:
        match=re.search(r'Ran (\d+) tests in ([\d.]+)s\s+OK',(folder/file).read_text(encoding='utf-8'));assert match,file
        tests[name]=dict(count=int(match[1]),seconds=float(match[2]),file=file)
    assert 'built in' in (folder/'2026-10-16-separation-routing-frontend-build.log').read_text(encoding='utf-8')
    baseline=json.loads((folder/'2026-10-10-control-paths-state-integrity.json').read_text())['state']
    assert all(sha(ROOT/name)==row['current'].lower() for name,row in baseline.items())
    old=json.loads((folder/'2026-10-16-separation-helpers-acceptance.json').read_text())['runtime_identities_preserved']
    assert dict(xtts=xtts()['identity'],nllb=nllb()['identity'],recognition=recognition()['identity'],translation=translation()['identity'])==old
    profile=Path(route['profile']);site=profile/'Lib/site-packages';notice_root=folder/'2026-10-16-separation-candidate-notices';notice_root.mkdir(exist_ok=True)
    notices={};no_notice=[]
    from email.parser import Parser
    for path in sorted(site.glob('*.dist-info/METADATA')):
        name=Parser().parsestr(path.read_text(encoding='utf-8'))['Name'];matches=[]
        for filename,digest,size in csv.reader((path.parent/'RECORD').read_text(encoding='utf-8').splitlines()):
            rel=Path(filename)
            if '..' in rel.parts or rel.is_absolute():continue
            source=site/rel
            if source.is_file() and any(term in rel.name.lower() for term in ('license','licence','copying','notice')):
                target=notice_root/name/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
                matches.append(dict(file=str(target.relative_to(ROOT)),sha256=sha(target)))
        notices[name]=matches
        if not matches:no_notice.append(name)
    supplement=json.loads((folder/'2026-10-16-separation-antlr-notice.json').read_text());assert sha(ROOT/supplement['file'])==supplement['sha256']
    stage=safe_path(ROOT/'temp/separation-candidate-2026-10-16-staging')
    assert stage.parent==(ROOT/'temp').resolve() and stage.name=='separation-candidate-2026-10-16-staging'
    assert (stage/'.owner').read_text()=='reflow.separation.candidate.2026-10-16'
    expected={'.owner'}|{row['filename'] for row in lock['packages'] if row['source']=='published-wheel-pending-approval'}
    assert {path.name for path in stage.iterdir()}==expected
    removed=0
    for path in stage.iterdir():
        safe_path(path);assert path.is_file();removed+=path.stat().st_size;path.unlink()
    stage.rmdir()
    info_path=profile/'profile.json';info=json.loads(info_path.read_text());info.update(status='candidate-offline-validated',runtime_verified=True,
        real_model_inference_verified=True,per_feature_routing_integrated=True,runtime_identity=route['identity'],semantic_quality_accepted=False,
        acceptance='../../docs/validation/2026-10-16-separation-candidate-acceptance.json');assert not info['production_default'] and not info['release_eligible']
    info_path.write_text(json.dumps(info,indent=2),encoding='utf-8')
    total=0;count=0;caches=[]
    for directory,dirs,files in os.walk(profile):
        caches.extend(str(Path(directory)/name) for name in dirs if name=='__pycache__')
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_file(follow_symlinks=False):total+=entry.stat(follow_symlinks=False).st_size;count+=1
    sources=['core/separation_runtime.py','core/audio_separator.py','core/run_demucs.py','core/settings.py','core/pipeline.py','core/cue_review.py',
        'core/runtime_checks.py','core/engine_readiness.py','bridge/api.py','frontend/src/lib/api.ts','frontend/src/pages/Settings.tsx','packaging/build_portable.py',
        'dev/build_separation_candidate.py','dev/prepare_separation_routing_recipe.py','dev/evaluate_separation_candidate.py','dev/evaluate_separation_native.py',
        'dev/evaluate_separation_video.py','dev/evaluate_separation_settings_native.py','dev/test_separation_runtime.py','dev/finalize_separation_candidate.py']
    result=dict(passed=True,release_ready=False,defaults_changed=False,models_downloaded=False,existing_state_and_runtime_identities_preserved=True,
        package_count=32,copied_payload_files=build['copied_payload_files'],wheel_payload_files=build['wheel_payload_files'],downloaded_bytes=build['downloaded_bytes'],
        runtime_identity=route['identity'],candidate_bytes=total,candidate_files=count,cache_directories=caches,
        tests=tests,test_counts_overlap=True,real_checks=len(receipts['real']['checks']),native_checks=len(receipts['native']['checks']),interface_checks=len(receipts['interface']['checks']),
        video_checks=len(receipts['video']['checks']),short_english_video_passed=True,translation_tested_in_video=False,full_hindi_workflow_validated=False,
        quality_accepted=False,clean_machine_validated=False,physical_portable_copy_created=False,owned_staging_removed=True,staging_bytes_removed=removed,
        package_notices=notices,packages_without_installed_notice=no_notice,notice_supplement=supplement,distribution_rights_cleared=False,
        source_sha256={name:sha(ROOT/name) for name in sources},profile_sha256=sha(info_path),
        frontend_dist_sha256={str(path.relative_to(ROOT)):sha(path) for path in sorted((ROOT/'frontend/dist').rglob('*')) if path.is_file()})
    (folder/'2026-10-16-separation-candidate-acceptance.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
