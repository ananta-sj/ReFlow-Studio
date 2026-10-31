"""Consolidate actual visual acceptance and clean only approved installer staging."""
import json,os,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'core')]
from core.runtime_integrity import sha,safe_path

def main():
    from core.visual_runtime import validate,model_contract,LOCK
    route=validate();model_contract(verify_weights=True)
    out=ROOT/'docs/validation';read=lambda name:json.loads((out/name).read_text(encoding='utf-8'))
    build=read('2026-10-16-visual-candidate-build.json');assert build['completed'] and build['downloaded_bytes']==64466647
    receipts={name:read(filename) for name,filename in {'real':'2026-10-16-visual-candidate-real.json','native':'2026-10-16-visual-candidate-native.json',
        'interface':'2026-10-16-visual-routing-native.json','video':'2026-10-16-visual-stage-pipeline-final.json','payload':'2026-10-16-visual-candidate-payload.json'}.items()}
    assert all(row['passed'] for row in receipts.values())
    assert receipts['real']['runtime']['identity']==route['identity']==receipts['native']['runtime_identity']
    assert receipts['real']['model_hashes_preserved'] and receipts['real']['workspace_removed'] and receipts['video']['workspace_removed']
    assert receipts['real']['probe']['training_launchers_disabled'] and receipts['payload']['package_count']==55
    full_attempt=read('2026-10-16-visual-video.json')
    assert not full_attempt['passed'] and 'Generated speech cannot fit without cutting words' in full_attempt['error']
    assert receipts['video']['speech_generation_tested'] is False
    inventory=read('2026-10-16-visual-portable-inventory.json')
    paths={row['path'] for row in inventory['files']}
    assert LOCK in paths and 'runtime_profiles/visual-candidate/routing-recipe.json' in paths
    tests={}
    for label,filename in [('backend','2026-10-16-visual-candidate-final-backend.log'),('focused','2026-10-16-visual-candidate-final-focused.log')]:
        match=re.search(r'Ran (\d+) tests in ([\d.]+)s\s+OK',(out/filename).read_text(encoding='utf-8'));assert match,filename
        tests[label]=dict(count=int(match[1]),seconds=float(match[2]),file=filename)
    assert 'built in' in (out/'2026-10-16-visual-frontend-build.log').read_text(encoding='utf-8')
    baseline=read('2026-10-10-control-paths-state-integrity.json')['state']
    assert all(sha(ROOT/name)==row['current'].lower() for name,row in baseline.items())
    from core.separation_runtime import validate as separation
    from core.xtts_runtime import validate as xtts
    from core.nllb_runtime import validate as nllb
    from core.recognition_runtime import validate as recognition
    from core.m2m100_runtime import validate as translation
    identities={name:call()['identity'] for name,call in [('separation',separation),('xtts',xtts),('nllb',nllb),('recognition',recognition),('translation',translation)]}
    assert identities==read('2026-10-16-visual-helpers-acceptance.json')['runtime_identities']
    f5=read('2026-10-16-f5-lazy-speech-final.json')
    assert all(sha(ROOT/name)==digest for name,digest in f5['asset_sha256'].items())
    lock=json.loads((ROOT/LOCK).read_text());stage=safe_path(ROOT/'temp/visual-candidate-2026-10-16-staging')
    assert stage.resolve()==Path('C:/Projects/Reflow Studio/temp/visual-candidate-2026-10-16-staging').resolve() and stage.parent==(ROOT/'temp').resolve()
    assert (stage/'.owner').read_text()=='reflow.visual.candidate.2026-10-16'
    expected={'.owner'}|{row['filename'] for row in lock['packages'] if row['source']=='published-wheel-pending-approval'}
    assert {path.name for path in stage.iterdir()}==expected
    removed=0
    for path in stage.iterdir():safe_path(path);assert path.is_file();removed+=path.stat().st_size;path.unlink()
    stage.rmdir()
    profile=Path(route['profile']);info_path=profile/'profile.json';info=json.loads(info_path.read_text())
    info.update(status='candidate-offline-validated-with-guards',runtime_verified=True,real_model_inference_verified=True,per_feature_routing_integrated=True,
        runtime_identity=route['identity'],upstream_advisory_present=True,distributed_training_disabled=True,quality_accepted=False,
        acceptance='../../docs/validation/2026-10-16-visual-candidate-acceptance.json')
    assert not info['production_default'] and not info['release_eligible'];info_path.write_text(json.dumps(info,indent=2),encoding='utf-8')
    total=0;count=0;caches=[]
    for folder,dirs,names in os.walk(profile,followlinks=False):
        caches.extend(str(Path(folder)/name) for name in dirs if name=='__pycache__')
        for name in names:
            path=safe_path(Path(folder)/name);total+=path.stat().st_size;count+=1
    sources=['core/visual_imports.py','core/visual_runtime.py','core/run_visual.py','core/media_io.py','core/video_frames.py','core/providers/enhancer/gfpgan_local.py',
        'core/providers/resolve.py','core/settings.py','core/pipeline.py','core/cue_review.py','core/runtime_checks.py','core/engine_readiness.py','core/runtime_probe_worker.py',
        'bridge/api.py','frontend/src/lib/api.ts','frontend/src/pages/Settings.tsx','packaging/build_portable.py',
        'dev/build_visual_candidate.py','dev/prepare_visual_routing_recipe.py','dev/evaluate_visual_candidate.py','dev/evaluate_visual_native.py','dev/evaluate_visual_video.py',
        'dev/evaluate_visual_settings_native.py','dev/evaluate_visual_stage_pipeline.py','dev/audit_visual_payload.py','dev/test_visual_imports.py','dev/test_visual_runtime.py','dev/test_visual_process_guard.py','dev/finalize_visual_candidate.py']
    report=dict(passed=True,release_ready=False,defaults_changed=False,new_models_downloaded=False,existing_runtime_identities_preserved=identities,
        protected_state_preserved=True,tested_gfpgan_f5_assets_preserved=True,package_count=55,downloaded_wheel_bytes=build['downloaded_bytes'],
        candidate_bytes=total,candidate_files=count,verified_payload_files=receipts['payload']['verified_payload_files'],cache_directories=caches,
        runtime_identity=route['identity'],tests=tests,test_counts_overlap=True,
        real_checks=len(receipts['real']['checks']),native_checks=len(receipts['native']['checks']),interface_checks=len(receipts['interface']['checks']),video_checks=len(receipts['video']['checks']),
        real_face_model_forward_calls=3,cancel_return_seconds=receipts['real']['cancel_return_seconds'],
        short_english_video_passed=False,full_video_stopped_on_speech_duration=True,visual_stage_pipeline_passed_with_source_audio_fixture=True,
        speech_generation_tested_in_visual_stage_fixture=False,translation_tested_in_video=False,hindi_quality_validated=False,quality_accepted=False,
        physical_portable_copy_created=False,clean_machine_validated=False,new_gpu_acceptance=False,
        upstream_advisory_still_present=True,distinct_cves=['CVE-2024-27763'],application_training_guard_validated=True,distribution_rights_cleared=False,
        package_notices=receipts['payload']['package_notices'],packages_without_installed_notice=receipts['payload']['packages_without_installed_notice'],
        owned_staging_removed=not stage.exists(),staging_bytes_removed=removed,
        payload_audit_identity_before_media_source_split=receipts['payload']['runtime_identity'],
        source_sha256={name:sha(ROOT/name) for name in sources},profile_sha256=sha(info_path),
        frontend_dist_sha256={str(path.relative_to(ROOT)):sha(path) for path in sorted((ROOT/'frontend/dist').rglob('*')) if path.is_file()})
    (out/'2026-10-16-visual-candidate-acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in report.items() if key not in {'package_notices','source_sha256','frontend_dist_sha256'}},indent=2))
if __name__=='__main__':main()
