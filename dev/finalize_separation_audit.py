"""Bind this no-install separation iteration to tests and preserved user state."""
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]


def main():
    from core.runtime_integrity import sha
    from core.m2m100_runtime import validate as translation
    from core.nllb_runtime import validate as nllb
    from core.xtts_runtime import validate as xtts
    from core.recognition_runtime import validate as recognition
    folder=ROOT/'docs/validation'
    boundary=json.loads((folder/'2026-10-16-separation-boundary.json').read_text())
    cancellation=json.loads((folder/'2026-10-16-separation-cancellation.json').read_text())
    baseline=json.loads((folder/'2026-10-10-control-paths-state-integrity.json').read_text())['state']
    checks=dict(boundary_audit_completed=boundary['audit_completed'],actual_cancellation_passed=cancellation['passed'],
        state_preserved=all(sha(ROOT/name)==row['current'].lower() for name,row in baseline.items()),
        tested_production_sources_preserved=all(sha(ROOT/name)==value for name,value in boundary['source_sha256'].items() if name.startswith('core/')))
    tests={}
    for label,filename in [('backend','2026-10-16-separation-full-backend.log'),('focused','2026-10-16-separation-focused-complete.log')]:
        log=(folder/filename).read_text(encoding='utf-8')
        match=re.search(r'Ran (\d+) tests in ([\d.]+)s\s+OK',log)
        checks[label+'_passed']=bool(match)
        tests[label]=dict(count=int(match[1]) if match else None,seconds=float(match[2]) if match else None,log=filename)
    identities=dict(translation=translation()['identity'],nllb=nllb()['identity'],xtts=xtts()['identity'],recognition=recognition()['identity'])
    checks['runtime_identities_preserved']=identities==dict(
        translation='9d498b5b21a8e7b2acadb8a9fcc5d37833758d14e9775e6c330f4d13970f69f9',
        nllb='1df86b1800ee5f17229b3be3972f2bfb83e28a2303d9b48d7caf2e2f947870bd',
        xtts='85a69c83e2310e8e53303987947f2313cb4c6aa70627eeccae3b85b564fd8163',
        recognition='f065c87ef27f370e060a5bdc4e2ba0e9f5056d8d7e8e8abe16ba1715dc696162')
    helpers=['dev/test_audio_separator.py','dev/test_runtime_probe.py','dev/audit_separation_boundary.py',
        'dev/evaluate_separation_cancellation.py','dev/inspect_separation_dependencies.py',
        'dev/prepare_separation_artifact_review.py','dev/finalize_separation_audit.py']
    result=dict(passed=all(checks.values()),release_ready=False,checks=checks,tests=tests,test_counts_overlap=True,
        identities=identities,packages_installed=False,package_archives_downloaded=False,models_downloaded=False,
        defaults_changed=False,modern_separation_runtime_validated=False,full_video_workflow_validated=False,
        source_sha256={name:sha(ROOT/name) for name in [*helpers,*[name for name in boundary['source_sha256'] if name.startswith('core/')]]})
    (folder/'2026-10-16-separation-iteration-acceptance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    return not result['passed']


if __name__=='__main__':raise SystemExit(main())
