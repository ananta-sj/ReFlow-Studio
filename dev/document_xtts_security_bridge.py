"""Reviewable next candidate plan and actual session-bridge iteration receipt."""
import ast
import hashlib
import json
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/validation'

def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))

def main():
    old=read('2026-10-13-xtts-candidate-lock-review.json')
    revised=read('2026-10-13-xtts-security-cpu-lock-review.json')
    budget=read('2026-10-13-xtts-security-cpu-download-budget.json')
    scan=read('2026-10-13-xtts-security-cpu-advisories.json')
    session=read('2026-10-13-xtts-candidate-session.json')
    preserved=read('2026-10-13-xtts-candidate-preservation-after.json')
    network=read('2026-10-13-metadata-only-security-cpu-revision-receipt.json')
    prior={p['name']:p for p in old['packages']}
    selected={p['name']:p for p in revised['packages']}
    added=[p for p in revised['packages'] if p['name'] not in prior]
    changed=[p for p in revised['packages'] if p['name'] in prior and p['version']!=prior[p['name']]['version']]
    parents={name:set() for name in selected}
    for edge in revised['edges']:parents[canonicalize_name(Requirement(edge['requirement']).name)].add(edge['parent'])
    sizes={p['name']:p['bytes'] for p in budget['packages']}
    plan=dict(installation_authorized=False,replacement_runtime_installed=False,
        target_profile='runtime_profiles/xtts-security-candidate',
        preserve_profiles=['build/windows-portable','runtime_profiles/xtts-candidate'],
        reused_python='3.13.16 from the verified candidate bootstrap, no system interpreter',
        reused_models='Existing local XTTS checkpoint and explicit reference files; no model downloads',
        packages=len(selected),active_dependency_edges=len(revised['edges']),
        changed_packages=[dict(name=p['name'],before=prior[p['name']]['version'],after=p['version']) for p in changed],
        added_packages=[dict(name=p['name'],version=p['version'],requested_by=sorted(parents[p['name']])) for p in added],
        artifact_download_bytes=budget['total_artifact_bytes'],installed_disk_size_verified=False,
        advisory_scan_matches=scan['match_count'],model_compatibility_verified=False,
        require_user_approval_before_replacement_package_downloads=True,
        acceptance=['Exact version/hash/origin/duplicate metadata and target dependency checks',
            'Actual shared-FFmpeg audio decoding and resampling','Existing XTTS speech and token cancellation offline',
            'Persistent session reuse, invalid request handling, output preservation and worker cleanup',
            'Existing Whisper recognition cross-check; naturalness is a separate listening gate',
            'Package notice collection, installed footprint measurement and owned staging cleanup'],
        release_ready=False)
    (OUT/'2026-10-13-xtts-security-upgrade-review.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    checks=dict(metadata_target_closure_valid=revised['metadata_closure_valid'],
        target_edges_satisfied=all(e['satisfied'] for e in revised['edges']),
        exact_archive_sizes_verified=budget['complete'],advisory_scan_complete=scan['complete'],
        no_known_osv_matches=scan['match_count']==0,
        resolver_no_archive_requests=network['exit_code']==0 and all(r['allowed'] for r in network['requests']),
        real_session_bridge_passed=session['passed'],original_state_assets_and_sources_preserved=preserved['passed'],
        replacement_installation_not_claimed=not plan['replacement_runtime_installed'],release_not_claimed=not plan['release_ready'])
    helpers=['inspect_xtts_security_replacements','prepare_xtts_security_resolution','resolve_runtime_plan_metadata_only',
        'check_xtts_candidate_closure','measure_xtts_lock_metadata','audit_xtts_candidate_advisories',
        'xtts_candidate_worker','verify_xtts_candidate_session','document_xtts_security_bridge']
    for name in helpers:ast.parse((ROOT/f'dev/{name}.py').read_text(encoding='utf-8'))
    checks['helper_syntax_valid']=True
    text=f'''# XTTS security replacement and session bridge — 13 October 2026

## Outcome and scope

The existing validated offline candidate passed a real test through Reflow's existing `FeatureSession` interface. A separate replacement lock is ready for review. **No replacement package archives were downloaded and no installed runtime or production default changed in this pass.** The user's earlier request requires explanation and approval before adding packages/tools; replacement installation is the next approval step, not inferred from metadata preparation.

The replacement plan targets Windows portable and ordinary CPython 3.13.16. It reuses the verified interpreter bootstrap and existing XTTS model assets in a new owned `runtime_profiles/xtts-security-candidate` directory. The current working shared runtime and validated `xtts-candidate` remain comparison baselines. There is no new TTS/translation model, agent service, compiler, package manager or framework proposed. The library upgrade introduces the transitive support packages explicitly listed below.

## Actual persistent worker verification

This used the existing parent `FeatureSession` class with a development-only XTTS worker and the already installed CPU candidate. It did not substitute generated waveform fixtures or edit supplied audio. The candidate worker loaded the existing XTTS checkpoint once, answered two actual speech requests, rejected an unsupported `source` language, and cancelled a longer utterance after a real token boundary.

| Session check | Observed result |
| --- | --- |
| Two speech requests | Passed; nonempty generated WAV files |
| Worker lifetime | Same worker PID {session.get('worker_pid')} for both successful calls |
| Model lifetime | Same model identity, one load |
| Invalid speech language | Rejected; no output created |
| Stop to worker exit | {session.get('stop_seconds')} seconds |
| Previous completed output | Hash preserved after cancellation |
| Incomplete publication | No staged output left in the parent job |
| Worker/process ownership | Session thread finished; parent workspace removed |
| Total observed test time | {session['elapsed_seconds']} seconds |

The offline worker blocks socket connections, DNS and binds, uses explicit local models, and places TTS/Torch/Hugging Face/Matplotlib/Numba caches inside the caller's job folder. Its internal render workspace is also nested inside that folder, so an outer job owns cleanup even if the worker is stopped. Requests use the existing atomic JSON-file session protocol and bounded error diagnostics. The worker validates that output WAV destinations belong to the caller's job workspace.

This is **real session-interface acceptance**, not a production provider switch, native UI acceptance, full video render, resource calibration or approval to ship the old advisory-affected candidate. The development worker remains outside the production provider registry. All original XTTS assets, five saved app-state files and previously tested production sources remain hash-identical.

## Why these versions are proposed

| Library | Previous candidate | Proposed candidate | Reason |
| --- | --- | --- | --- |
| PyTorch | 2.9.1+cpu | 2.14.1+cpu | Published Windows CPU build beyond the prior advisory ranges |
| TorchAudio | 2.9.1+cpu | 2.11.0+cpu | Stable ABI supports Torch 2.11 and later; retains existing audio APIs |
| TorchCodec | 0.8.1 | 0.17.0+cpu | Current compatible decoder family for Torch 2.11+ and Python 3.13 |
| Transformers | 4.57.1 | 5.19.0 | Beyond the prior reported affected ranges; major generation API change requires actual XTTS testing |
| Coqui TTS | 0.27.5 | 0.27.5 | Same currently published engine and existing checkpoint; no engine replacement |

Compatibility sources: [TorchAudio's official installation matrix](https://docs.pytorch.org/audio/stable/installation.html), [TorchCodec's compatibility matrix](https://github.com/meta-pytorch/torchcodec#compatibility-with-torch-versions), [Coqui installation requirements](https://coqui-tts.readthedocs.io/en/latest/installation.html). These sources and compatible Windows wheel tags support planning; they do not prove Coqui's customized GPT generation wrapper works unchanged with Transformers 5.19. That remains an explicit evaluation risk. No declared requirements were stripped or bypassed to manufacture a clean dependency result.

The final **{len(selected)}-package** CPU lock has **{len(revised['edges'])} satisfied active target dependency links**. Required extras were propagated to a fixed point; Python/Windows markers and wheel tags were checked independently of the Python 3.10 resolver host. Host-only `async-timeout`, `exceptiongroup` and `tomli` were excluded. An exact-version public OSV lookup returned **zero matches** for this reviewed lock at the recorded scan time. That is a point-in-time advisory result, not certification of native DLLs, model files, runtime behavior or future vulnerabilities.

## Download and storage impact

The full proposed wheel set totals **{budget['total_artifact_bytes']:,} bytes ({budget['total_artifact_bytes']/1048576:.1f} MiB)**, including the already retained 13,857-byte local Docopt wheel. Reusing that wheel leaves {budget['total_artifact_bytes']-13857:,} bytes of remote package archives. No new Python or model download is proposed. Installed disk size and peak staging overlap are unmeasured; they will be recorded after an approved separate installation. The previous 85-package candidate occupied about 960 MB after installation, so the replacement should be planned as another substantial runtime rather than described as a small patch.

All URLs, filenames and SHA256 values are recorded in the JSON and hash-bound text locks. Torch/TorchAudio/TorchCodec are explicitly pinned to CPU local versions. The review text lock contains a workspace-specific local Docopt URL; installation must deliberately rebind that owned wheel without changing its hash. Temporary wheel staging would be removed after verification while retaining source/notice/evidence records and both comparison runtimes.

## Changed library versions

'''
    text+='| Package | Before | After | Requesting dependency |\n| --- | --- | --- | --- |\n'
    for p in changed:text+=f"| `{p['name']}` | {prior[p['name']]['version']} | {p['version']} | {', '.join(sorted(parents[p['name']])) or 'Explicit runtime root'} |\n"
    text+='\n## New transitive support packages\n\nThese are required by the revised libraries, not separate product features. HTTP/client/certificate packages support the Hugging Face client; terminal formatting/argument helpers support its command interface. They do not imply API use, a connected account or a model download. Offline evaluation will keep network operations blocked.\n\n| Package | Version | Archive bytes | Required by |\n| --- | --- | ---: | --- |\n'
    for p in added:text+=f"| `{p['name']}` | {p['version']} | {sizes[p['name']]:,} | {', '.join(sorted(parents[p['name']]))} |\n"
    text+='''
## Retained planning corrections

The initial CPU-index lookup expected TorchCodec's plain version 0.17.0 and did not match the published local version 0.17.0+cpu. The first dry run selected that CPU version, but the review checker deliberately rejected the non-exact root match and the size helper's corresponding PyPI URL returned 404. Those reports remain retained. The root was then made explicitly `0.17.0+cpu`; all three CPU index hashes were captured, a separately labelled metadata-only resolution completed, and closure, size and advisory checks passed. No archive was transferred during these attempts.

The root plan now contains only current name/version/purpose entries rather than stale wheel metadata copied from the older library versions. Label/prefix parameters were added to existing helpers so the old candidate's lock, receipts and checks remain intact. Source builds, runtime installation and archive GETs remained disabled in every resolver attempt.

## Changes and evidence

Added `dev/inspect_xtts_security_replacements.py` and `dev/prepare_xtts_security_resolution.py` for metadata-only candidate selection; added `dev/xtts_candidate_worker.py` and `dev/verify_xtts_candidate_session.py` for actual isolated session testing; added this documentation helper. Existing resolver/closure/budget/advisory helpers gained labelled-plan/output support. No production module was changed, and no new audit framework was installed. Tests used the existing interpreted libraries and existing FFmpeg.

Evidence: [replacement review](validation/2026-10-13-xtts-security-upgrade-review.json), [exact dependency lock](validation/2026-10-13-xtts-security-cpu-lock-review.json), [hash-bound text lock](validation/2026-10-13-xtts-security-cpu-review.lock.txt), [metadata-only receipt](validation/2026-10-13-metadata-only-security-cpu-revision-receipt.json), [download budget](validation/2026-10-13-xtts-security-cpu-download-budget.json), [advisory scan](validation/2026-10-13-xtts-security-cpu-advisories.json), [session acceptance](validation/2026-10-13-xtts-candidate-session.json), [worker log](validation/2026-10-13-xtts-candidate-session-worker.log), [preservation](validation/2026-10-13-xtts-candidate-preservation-after.json), [iteration integrity](validation/2026-10-13-xtts-security-bridge-integrity.json).

## Approval boundary and remaining work

Next proposed action: create the separate replacement runtime, download/install only this reviewed 99-package hash-bound closure, reuse the verified Python bootstrap and existing weights, run the actual package/audio/XTTS/session/recognition checks, measure disk use and remove owned installer staging. Preserve both current runtimes, original state and model files; do not change app defaults or publish a release. Any extra package, compiler, source build, new model or alternative engine discovered necessary must be explained and reviewed before addition.

Approval is requested because the user explicitly asked to know what is being added and why before package/tool changes. The new support packages and major Transformer API change were not part of the earlier exact 85-package installation approval. Until approval arrives, the replacement remains metadata-only; the working app and validated candidate remain unchanged.

Successful evaluation would still leave the production provider/readiness/cache identity wiring, all other runtime families, licensing/notices, full workflow and clean-machine/native Windows release gates. The app is not release-ready. See the [runtime repair map](RUNTIME_REPAIR_PLAN_2026-10-13.md) and [release status](RELEASE_READINESS_2026-10-04.md).
'''
    doc=ROOT/'docs/XTTS_SECURITY_AND_WORKER_PLAN_2026-10-13.md'
    doc.write_text(text,encoding='utf-8')
    receipt=dict(passed=all(checks.values()),checks=checks,new_packages=len(added),changed_packages=len(changed),
        replacement_installed=False,production_sources_changed=False,release_ready=False,
        document_sha256=hashlib.sha256(doc.read_bytes()).hexdigest())
    (OUT/'2026-10-13-xtts-security-bridge-integrity.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2));return not receipt['passed']

if __name__=='__main__':raise SystemExit(main())
