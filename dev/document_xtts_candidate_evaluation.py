"""Document measured candidate acceptance without claiming release readiness."""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/validation'

def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))

def main():
    install=read('2026-10-13-xtts-candidate-install.json')
    probe=read('2026-10-13-xtts-candidate-runtime-probe-audited-network.json')
    live=read('2026-10-13-xtts-candidate-live-evaluation-audited-network.json')
    speech=read('2026-10-13-xtts-candidate-speech-content.json')
    preservation=read('2026-10-13-xtts-candidate-preservation-after.json')
    cleanup=read('2026-10-13-xtts-candidate-staging-cleanup.json')
    scan=read('2026-10-13-xtts-candidate-advisories.json')
    details=read('2026-10-13-xtts-candidate-advisory-details.json')
    notices=read('2026-10-13-xtts-candidate-notices/inventory.json')
    missing=[row['package'] for row in notices if not row['notice_files']]
    checks=dict(candidate_install_completed=install['completed'],runtime_probe_passed=probe['passed'],
        actual_xtts_speech_and_cancellation_passed=live['acceptance'],speech_content_passed=speech['passed'],
        protected_state_models_sources_preserved=preservation['passed'],
        owned_staging_removed=cleanup['removed'] and not (ROOT/'temp/xtts-candidate-2026-10-13-staging').exists(),
        exact_candidate_scope=install['packages']==85,known_advisories_retained=scan['complete'] and bool(scan['matches']),
        output_hash_matches=hashlib.sha256(Path(live['output_file']).read_bytes()).hexdigest()==live['output_sha256'],
        existing_models_only=not install['model_downloaded'] and not live['model_downloaded'] and not speech['model_downloaded'],
        release_not_claimed=not install['release_eligible'] and not live['release_eligible'])
    helpers=['build_xtts_runtime_candidate','verify_xtts_runtime_candidate','evaluate_xtts_runtime_candidate',
        'verify_xtts_candidate_preservation','audit_xtts_candidate_advisories','inspect_xtts_candidate_advisories',
        'check_xtts_candidate_speech_content','document_xtts_candidate_evaluation']
    for name in helpers:ast.parse((ROOT/f'dev/{name}.py').read_text(encoding='utf-8'))
    checks['helper_syntax_valid']=True
    profile_path=ROOT/'runtime_profiles/xtts-candidate/profile.json'
    assert (profile_path.parent/'.owner').read_text()=='reflow.xtts.candidate.2026-10-13'
    profile=json.loads(profile_path.read_text(encoding='utf-8'))
    assert profile['profile']=='xtts-candidate' and profile['production_default'] is False
    if all(checks.values()):
        profile.update(status='candidate-offline-validated',runtime_verified=True,
            real_model_inference_verified=True,release_eligible=False,security_gate='blocked-known-advisories',
            validation_receipt='../../docs/validation/2026-10-13-xtts-candidate-live-evaluation-audited-network.json',
            dependency_lock_sha256=hashlib.sha256((OUT/'2026-10-13-xtts-candidate-lock-review.json').read_bytes()).hexdigest())
        profile_path.write_text(json.dumps(profile,indent=2),encoding='utf-8')
    doc=ROOT/'docs/XTTS_RUNTIME_CANDIDATE_ITERATION_2026-10-13.md'
    text=f'''# Isolated XTTS runtime candidate — 13 October 2026

## Result and boundaries

The user said “so go ahead” after reviewing the helper/lock results and the proposed next step of separately approved runtime creation and testing. This pass built and tested that isolated candidate. It did not switch the application default, change the model registry or install system tools. The previous approval limited to the helper build remains documented as an earlier phase; this later authorization covers the reviewed interpreter and 85-package candidate.

**Candidate technical acceptance: {'passed' if all(checks.values()) else 'pending/failed checks below'}. Release eligibility: false.** The original shared runtime and optional profiles remain the working setup. Windows portable is the first release target; this pass does not validate Linux/macOS.

The new folder is `runtime_profiles/xtts-candidate`. It uses ordinary Windows x64 CPython 3.13.16, Coqui TTS 0.27.5, CPU Torch 2.9.1, Torchaudio 2.9.1, TorchCodec 0.8.1 and the exact reviewed 85-package lock. All required wheels and the Python archive were verified against their recorded SHA256 values. The locally built Docopt helper was reused. No compiler, Conda, new model, GPU driver or system Python/PATH change was introduced.

## Measured results

| Check | Observed result |
| --- | --- |
| Exact installed package set and versions | 85 packages, matching the reviewed lock |
| Duplicate distribution records | None in the candidate |
| Dependency constraints | All active target requirements satisfied |
| Import paths | Tested engine imports originate inside the candidate |
| Runtime checks | {len(probe['checks'])} checks passed, including CPU convolution and real audio decoding |
| Docopt on Python 3.13 | Real parser assertion passed |
| Existing XTTS checkpoint | Loaded without model downloads |
| Successful speech | {live['output_duration_seconds']:.2f} seconds, {live['output_sample_rate']} Hz, non-silent |
| Model loading | {live['model_load_seconds']:.3f} seconds in the final trial |
| Speech generation | {live['generation_seconds']:.3f} seconds for this one utterance |
| Real token-boundary cancellation | {live['cancellation_seconds']:.3f} seconds |
| Model lifetime | Same loaded model reused for speech and cancellation |
| Output publication | Previous completed speech preserved after cancellation |
| Temporary generation state | Staging output and job workspace removed |
| Original state and models | Five app-state hashes and eight XTTS asset hashes unchanged |
| Production source files | Match the previously tested source hashes |
| Installed candidate size | {install['runtime_bytes']:,} bytes, about {install['runtime_bytes']/1048576:.1f} MiB at installation completion |
| Temporary installation cleanup | {cleanup['bytes']:,} bytes removed |
| Ollama trial | Earlier temporary trial remains absent |

The measured size excludes existing model weights and documentation/notice receipts. Imports can generate additional candidate cache files, so this is the installation-completion measurement rather than a promise of a fixed final footprint. The generation time is a single CPU observation, not a calibrated ETA or a general speed comparison. The candidate is about {live['generation_seconds']/live['output_duration_seconds']:.1f} times slower than real time for this utterance; GPU performance was not tested under this CPU evaluation approval.

## Speech-content cross-check

The unchanged existing Whisper Turbo assets and GPU worker recognized the newly generated audio, rather than a supplied transcript. The expected text was “{live['spoken_text']}” and the observed recognition was “{speech.get('recognized_text','')}”. Word error rate was {speech.get('word_error_rate','unavailable')}; the check {'passed' if speech['passed'] else 'did not pass'}. The recognition worker and its job workspace were released.

ASR similarity helps detect gross gibberish or missing words. It does not certify naturalness, emotion, speaker likeness, source-video timing or all-language pronunciation. This new candidate take has not received a human listening acceptance, and this pass did not render a full dubbed video or change the previously accepted Hindi pipeline.

## Offline guard and retained verification corrections

The first runtime check and first speech trial both completed their functional checks but marked the aggregate result false because the harness demanded zero socket attempts. The captured event was a blocked socket bind; subsequent stack tracing identified urllib3's `_has_ipv6("::1")` import-time capability probe. It was not a model download or an outbound connection.

The verification was corrected to record event/address/stack details, keep every network operation blocked, and separately require no outbound or DNS attempts. Both actual runtime and real speech/cancellation trials were rerun with the corrected checks. Their new labelled receipts passed. The original failed aggregate receipts and logs were retained without editing. This was a harness correction, not an exception allowing network access.

The speech worker used offline Hugging Face flags, explicit existing model paths and job-owned TTS/Hugging Face/Torch/Matplotlib/Numba cache paths. Source/reference media came from the existing `Sample/2.mp4`. New test audio is retained under validation only; no original media was overwritten. All root user-state hashes and original XTTS assets were checked again.

The Python 3.13 startup log includes “Failed to find real location” for its executable. The interpreter still reports the exact expected version and isolated paths, and native package/audio/model execution passes. The warning is retained as a clean-machine/launcher investigation item, not declared solved. Pydub and Docopt also emit invalid-escape SyntaxWarnings under Python 3.13; their actual tested audio/parser operations pass. No installed third-party source was patched merely to hide those warnings.

## Preparation failures and recovery

The initial notice collector mistakenly wrote a wheel license-directory entry as an empty file. Preparation stopped before pip installed packages. Resume handling first encountered the existing empty package destination, then a nested license-directory collision. The helper was corrected to skip directory entries, permit only the explicitly marked incomplete owned candidate with an empty package destination, preserve retry receipts, and remove only the empty notice-file artifacts created by the collector. The working runtime was never an installation target.

All subsequent package installation was offline from the verified local wheelhouse, with hashes required, dependencies already locked and source builds disabled. The existing pip was used in cross-target mode only to unpack the locked wheels. It did not install or upgrade itself. Cross-target console launchers referring to the old build interpreter were removed from the newly owned candidate; this worker uses package imports, not those CLI launchers. A future tool needing a console entry point must generate it against the correct interpreter and test it.

Archive path/link/size checks were retained. Redundant per-entry filesystem resolution was later replaced with lexical member validation for future builds in a fresh owned extraction directory; the completed installation had already used the original stricter checks. No existing candidate can be replaced automatically. Interrupted package installation cannot be resumed over a nonempty destination by this helper.

## Security and redistribution findings

The public OSV scan returned **{scan['match_count']} advisory records** for Torch 2.9.1 and Transformers 4.57.1. Some records are aliases of the same CVE, so this does not mean 16 independent vulnerabilities. The following table groups by CVE. CPU local-version suffixes were removed only for advisory matching, not from the actual package lock.

| CVE | Package | Advisory / affected surface | Published range endpoint |
| --- | --- | --- | --- |
'''
    groups={}
    for record in details:
        cve=next((a for a in record.get('aliases',[]) if a.startswith('CVE-')),record['id'])
        if cve in groups:continue
        groups[cve]=record
    for cve,record in sorted(groups.items()):
        affected=record.get('affected',[{}])[0]
        package=affected.get('package',{}).get('name','unknown')
        summary=record.get('summary') or 'See retained advisory details'
        endpoints=[event for r in affected.get('ranges',[]) for event in r.get('events',[]) if 'introduced' not in event]
        endpoint=', '.join(f"{k}: {v}" for e in endpoints for k,v in e.items())
        text+=f"| {cve} | {package} | [{record['id']}](https://osv.dev/vulnerability/{record['id']}): {summary} | {endpoint} |\n"
    text+=f'''
These findings are an explicit **release blocker for this candidate**. Offline testing with hash-recorded existing assets does not remove or dismiss them. Actual exposure and compatible remediations require review; simply jumping to the highest fixed version can break the Torch/Torchaudio/TorchCodec/Transformers/Coqui compatibility set. No untrusted model/checkpoint or custom remote generation code was tested, no training/chat-template path was exercised, and no service was exposed.

The full raw advisory records, aliases, ranges, descriptions and references are retained. The scan is a point-in-time package advisory check, not security certification or a complete native-DLL/model audit.

Bundled wheel license/notice files were collected for {len(notices)-len(missing)} of {len(notices)} packages. The current extraction did not find bundled notices for **{', '.join(missing)}**; these require exact-source notice/provenance follow-up. The full declared-license inventory and retained texts are available below. This collection does not settle transitive native-library/source-offer obligations, FFmpeg redistribution or model terms. The application's own license remains undecided; no license was assigned to the user's code.

## Changed files and evidence

Only development helpers, this candidate directory and validation/documentation artifacts changed in this pass. No production application source changed, so the previous 766-test backend and 47-contract frontend regression remain the production baseline; they were not rerun as a substitute for the actual new-runtime checks.

- `dev/build_xtts_runtime_candidate.py`: exact pinned archive fetch, safe fresh extraction, owned resume limits, offline cross-target installation, notice inventory, size measurement and temporary staging cleanup.
- `dev/verify_xtts_runtime_candidate.py`: actual candidate package/origin/dependency/arithmetic/decoding/parser checks with a fully blocked network guard.
- `dev/evaluate_xtts_runtime_candidate.py`: actual speech, model reuse, token-boundary cancellation and preserved-output/cleanup checks.
- `dev/check_xtts_candidate_speech_content.py`: real existing Whisper worker cross-check of generated audio.
- `dev/verify_xtts_candidate_preservation.py`: original asset/state/source integrity before and after evaluation.
- `dev/audit_xtts_candidate_advisories.py` and `dev/inspect_xtts_candidate_advisories.py`: public exact-version advisory lookup and retained detailed records; no installed audit framework.
- `dev/document_xtts_candidate_evaluation.py`: this report and consolidated evidence checks.

Evidence: [download receipt](validation/2026-10-13-xtts-candidate-downloads.json), [installation receipt](validation/2026-10-13-xtts-candidate-install.json), [runtime probe](validation/2026-10-13-xtts-candidate-runtime-probe-audited-network.json), [real speech/cancellation](validation/2026-10-13-xtts-candidate-live-evaluation-audited-network.json), [speech recognition](validation/2026-10-13-xtts-candidate-speech-content.json), [notice inventory](validation/2026-10-13-xtts-candidate-notices/inventory.json), [advisory scan](validation/2026-10-13-xtts-candidate-advisories.json), [advisory details](validation/2026-10-13-xtts-candidate-advisory-details.json), [original preservation](validation/2026-10-13-xtts-candidate-preservation-after.json), [staging cleanup](validation/2026-10-13-xtts-candidate-staging-cleanup.json), [consolidated integrity](validation/2026-10-13-xtts-candidate-iteration-integrity.json).

## What this unlocks and what remains

The tests establish that the existing XTTS checkpoint can load, generate and cancel using this clean supported-Python candidate. They remove the uncertainty that a successful metadata lock might still hide an unusable native/audio/model stack. They do not connect the app to this runtime or authorize an automatic default switch.

The next repair must resolve the known advisory versions while maintaining model/audio compatibility, then exercise the isolated worker bridge in a disposable app copy. RVC still needs its separate Windows/Fairseq/OmegaConf solution; desktop and other engine families need their own supported-runtime closure and acceptance. Full representative workflows, fresh-user setup/download retries, resource calibration, native process-crash recovery, clean-machine Windows prerequisites and licensing/portable-CI gates remain open. See the [repair map](RUNTIME_REPAIR_PLAN_2026-10-13.md) and [release readiness](RELEASE_READINESS_2026-10-04.md).

The original working setup remains usable for the previously validated Hindi workflow. This candidate remains an explicitly identified experiment, with production defaults unchanged and release eligibility false.
'''
    doc.write_text(text,encoding='utf-8')
    receipt=dict(passed=all(checks.values()),checks=checks,release_ready=False,
        candidate_functional=True,production_defaults_changed=False,advisory_cve_groups=len(groups),
        document_sha256=hashlib.sha256(doc.read_bytes()).hexdigest())
    (OUT/'2026-10-13-xtts-candidate-iteration-integrity.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2));return not receipt['passed']

if __name__=='__main__':raise SystemExit(main())
