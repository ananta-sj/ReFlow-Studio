"""Consolidate bounded evaluation evidence without equating fit with quality."""
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'core')]
def read(name):return json.loads((ROOT/'docs/validation'/name).read_text(encoding='utf-8-sig'))
def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
    return value.hexdigest()
def main():
    live=read('2026-10-16-temporary-dialogue-evaluation.json')
    tests=read('2026-10-16-assisted-review-backend-complete.json')
    meta=read('2026-10-16-temporary-dialogue-model-proposal-metadata.json')
    final_build=(ROOT/'docs/validation/2026-10-16-measured-dialogue-frontend-final.log').read_text(encoding='utf-8-sig')
    focused=(ROOT/'docs/validation/2026-10-16-measured-dialogue-integrity-final.log').read_text(encoding='utf-8-sig')
    checks={key:live.get(key) is True for key in ('temporary_runtime_models_removed','owned_processes_exited','owned_endpoint_released',
        'saved_state_unchanged','external_ollama_unchanged','environment_unchanged','runtime_ids_unchanged','archive_verified','layers_verified','cloud_disabled_verified')}
    checks['temporary_directory_absent']=not Path(live['temporary_root']).exists()
    checks['backend_passed']=tests['passed'] is True and tests['tests_run']>=941
    checks['backend_sources_still_match']=all(sha(ROOT/path)==value for path,value in tests['source_sha256'].items())
    checks['final_integrity_fixtures_passed']=bool(re.search(r'Ran 8 tests in [\d.]+s\s+OK',focused))
    checks['frontend_build_passed']='built in' in final_build and 'error TS' not in final_build
    checks['pinned_model']=live.get('model_identity',{}).get('digest')==meta['model']['manifest_sha256']
    checks['bounded_cases']=len(live['cases'])==8
    checks['bounded_speech']=len(live['speech'])<=6
    checks['all_text_cases_recorded']=live['completed'] is True
    diagnosis=read('2026-10-16-speech-overflow-diagnosis.json')
    replay=read('2026-10-16-speech-timing-replay.json')
    checks['original_audio_still_matches']=sha(diagnosis['output'])==diagnosis['output_sha256']==replay['raw_source_sha256']
    assets=read('2026-10-13-xtts-candidate-preservation-before.json')['assets']
    checks['eight_original_xtts_assets_preserved']=all(sha(ROOT/path)==value for path,value in assets.items())
    checks['speech_reference_preserved']=not live['speech'] or live.get('speech_reference_sha256')==diagnosis['reference_sha256']
    checks['candidate_audio_matches']=all(sha(c['path'])==c['sha256'] and c['words_cut'] is False and 1<=c['speed']<=1.3 for c in live['speech'])
    checks['request_budget_preserved']=sum(c.get('result',{}).get('writer_requests',0)+c.get('result',{}).get('reviewer_requests',0) for c in live['cases'])<=16
    import psutil
    owned=Path(live['temporary_root'])
    survivors=[]
    for process in psutil.process_iter(['exe','cmdline']):
        try:
            command=process.info.get('cmdline') or []
            executable=process.info.get('exe') or (command[0].strip('"') if command else '')
            if executable and Path(executable).is_absolute() and Path(executable).resolve().is_relative_to(owned):survivors.append(process.pid)
        except (psutil.AccessDenied,psutil.NoSuchProcess):pass
    checks['independent_owned_process_scan_clear']=not survivors
    if live['cases']:
        checks['dense_budget_matches_measured_conflict']=live['cases'][0]['case']['measured']==replay['measured_conflict']['measured_seconds']
    context=live.get('dense_context',{})
    checks['historical_context_still_matches']=bool(context) and sha(context['path'])==context['sha256']
    sources=['core/providers/dialogue_chat.py','core/dialogue_supervision.py','core/cue_review.py',
        'frontend/src/lib/api.ts','frontend/src/components/shared/CueReviewPanel.tsx',
        'dev/test_measured_dialogue_supervision.py','dev/evaluate_temporary_dialogue_model.py',
        'dev/cleanup_temporary_ollama.py','dev/finalize_temporary_dialogue_evaluation.py']
    report=dict(technical_checks_passed=all(checks.values()),checks=checks,backend_tests=tests['tests_run'],
        backend_seconds=tests['elapsed_seconds'],additional_focused_tests=8,test_counts_overlap=True,
        live_case_outcomes=[dict(label=c['case']['label'],outcome=c.get('result',{}).get('outcome'),error=c.get('error'),seconds=c['seconds']) for c in live['cases']],
        measured_candidates=live['speech'],human_quality_accepted=False,release_ready=False,
        dense_cue_has_measured_fit=any(c['fits'] for c in live['speech']),automatic_quality_judge_approved=False,
        dialogue_requests=sum(c.get('result',{}).get('writer_requests',0)+c.get('result',{}).get('reviewer_requests',0) for c in live['cases']),
        new_python_packages=False,defaults_changed=False,temporary_tools_removed=live.get('temporary_runtime_models_removed'),
        observed_owned_bytes_before_removal=live.get('peak_owned_bytes_observed'),
        source_sha256={name:sha(ROOT/name) for name in sources},
        evidence_sha256={name:sha(ROOT/'docs/validation'/name) for name in ['2026-10-16-temporary-dialogue-evaluation.json',
            '2026-10-16-assisted-review-backend-complete.json','2026-10-16-measured-dialogue-integrity-final.log',
            '2026-10-16-measured-dialogue-frontend-final.log','2026-10-16-temporary-dialogue-model-proposal-metadata.json',
            '2026-10-16-speech-overflow-diagnosis.json','2026-10-16-speech-timing-replay.json','2026-10-16-temporary-ollama-notices.json']})
    out=ROOT/'docs/validation/2026-10-16-temporary-dialogue-acceptance.json'
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['technical_checks_passed'] else 1
if __name__=='__main__':raise SystemExit(main())
