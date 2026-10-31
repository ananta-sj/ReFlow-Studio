"""Full offline fixture regression and evidence/preservation audit; no model calls."""
import hashlib,json,os,sys,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'core')]
def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
    return value.hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def runtimes():
    from core import xtts_runtime,nllb_runtime,recognition_runtime,m2m100_runtime,separation_runtime,visual_runtime
    return {name:module.validate()['identity'] for name,module in [('xtts',xtts_runtime),('nllb',nllb_runtime),('recognition',recognition_runtime),('m2m100',m2m100_runtime),('separation',separation_runtime),('visual',visual_runtime)]}
def main():
    temp=ROOT/'temp/tests-dialogue-evidence';temp.mkdir(exist_ok=True)
    os.environ.update(TEMP=str(temp),TMP=str(temp),PYTHONDONTWRITEBYTECODE='1',PATH=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH',''))
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')
    paths=sorted({*ROOT.glob('core/**/*.py'),*ROOT.glob('bridge/**/*.py'),*ROOT.glob('dev/test_*.py'),Path(__file__).resolve(),
        ROOT/'frontend/src/components/shared/CueReviewPanel.tsx',ROOT/'frontend/src/lib/api.ts',*ROOT.glob('frontend/dist/**/*')})
    paths=[path for path in paths if path.is_file()]
    sources={str(path.relative_to(ROOT)):sha(path) for path in paths}
    state={name:sha(ROOT/name) for name in ('settings.json','models.json','graph.json','ui_preferences.json','hardware_profile.json')}
    identities=runtimes()
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName('dev.'+path.stem) for path in sorted((ROOT/'dev').glob('test_*.py')))
    started=time.monotonic();result=unittest.TextTestRunner(verbosity=2).run(suite)
    previous=read(ROOT/'docs/validation/2026-10-16-temporary-dialogue-evaluation.json')
    checks=dict(backend_passed=result.wasSuccessful(),saved_state_preserved=state=={name:sha(ROOT/name) for name in state},
        captured_sources_and_built_frontend_preserved=all(sha(ROOT/name)==value for name,value in sources.items()),
        six_runtime_identities_preserved=identities==runtimes()==previous['before_runtime_ids'],
        temporary_ollama_model_still_absent=not Path(previous['temporary_root']).exists())
    assets=read(ROOT/'docs/validation/2026-10-13-xtts-candidate-preservation-before.json')['assets']
    checks['eight_original_xtts_assets_preserved']=all(sha(ROOT/name)==value for name,value in assets.items())
    from core.dialogue_evidence import validate_evidence
    rejected=0
    for case in previous['cases']:
        for candidate in case.get('result',{}).get('candidates',[]):
            if candidate['meaning_status']=='not_reviewed':continue
            try:validate_evidence(candidate['meaning_status'],candidate.get('meaning_evidence'),case['case']['source'],candidate['text'])
            except ValueError:rejected+=1
            else:raise AssertionError('An unquoted historical opinion unexpectedly satisfied the new protocol')
    checks['historical_unquoted_opinions_rejected_by_new_contract']=rejected>0
    frontend=(ROOT/'docs/validation/2026-10-16-dialogue-evidence-frontend.log').read_text(encoding='utf-8-sig')
    checks['frontend_build_passed']='built in' in frontend and 'error TS' not in frontend
    report=dict(passed=all(checks.values()),checks=checks,tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        seconds=round(time.monotonic()-started,3),historical_unquoted_opinions_rejected=rejected,
        historical_replay_is_contract_test_not_new_model_quality_test=True,live_model_calls=0,models_downloaded=False,
        packages_installed=False,defaults_changed=False,dense_six_second_cue_resolved=False,release_ready=False,
        runtime_identities=identities,state_sha256=state,source_sha256=sources,
        previous_evaluation_sha256=sha(ROOT/'docs/validation/2026-10-16-temporary-dialogue-evaluation.json'))
    out=ROOT/'docs/validation/2026-10-16-dialogue-evidence-acceptance.json'
    out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('RECEIPT',out,'passed=',report['passed'],'tests=',result.testsRun,'historical_rejections=',rejected,flush=True)
    return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
