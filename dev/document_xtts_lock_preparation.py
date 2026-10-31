"""Write the approved helper/lock completion report and verify preserved state."""
import ast
import hashlib
import json
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/validation'

def main():
    lock=json.loads((OUT/'2026-10-13-xtts-candidate-lock-review.json').read_text(encoding='utf-8'))
    budget=json.loads((OUT/'2026-10-13-xtts-download-budget.json').read_text(encoding='utf-8'))
    helper=json.loads((OUT/'2026-10-13-docopt-helper/receipt.json').read_text(encoding='utf-8'))
    sizes={row['name']:row for row in budget['packages']}
    parents={row['name']:set() for row in lock['packages']}
    for edge in lock['edges']:
        parents[canonicalize_name(Requirement(edge['requirement']).name)].add(edge['parent'])
    plan=json.loads((OUT/'2026-10-13-runtime-repair-plan.json').read_text(encoding='utf-8'))
    roots={canonicalize_name(row['name']):row['why'] for row in plan['xtts_candidate_roots']}
    text='''# XTTS helper build and dependency-lock preparation — 13 October 2026

## Outcome and authorization

The user approved **only the helper build and dependency-lock preparation**. That work is complete. No runtime was installed, no existing package was upgraded or removed, and no AI model was loaded or downloaded. Windows portable remains the first release target; this pass does not establish release readiness.

The target is ordinary Windows x64 CPython 3.13.16 with CPU PyTorch. The reviewed closure contains **85 packages and 128 active dependency links**, all satisfied according to published metadata and target wheel tags. This is a proposed XTTS worker, not a replacement for the current shared runtime, a resolved desktop environment or a repaired RVC environment.

## Approved Docopt build

The indirect dependency chain is `coqui-tts → num2words → docopt`. Docopt is an argument parser, not a speech model. Version 0.6.2 has a source archive but no published wheel, which prevented the initial binary-only resolver from completing.

- The downloaded source was exactly **25,901 bytes**. Its SHA256 matched the previously reviewed PyPI value: `49b3a825280bd66b3aa83585ef59c4a8c82f2c8a522dbe754a8bc8d08c85c491`.
- Archive members were checked for traversal, absolute targets, links, devices and excessive count/size before extraction into an owned workspace temporary folder.
- The retained setup declares a single Python module and no native extension or installation dependency. The build used the existing Python 3.10.11, setuptools 80.10.2 and wheel 0.47.0. No compiler, new packaging tool or build environment was installed.
- The command was `python -B -X utf8 setup.py bdist_wheel --dist-dir <retained-evidence-directory>`. It produced `docopt-0.6.2-py2.py3-none-any.whl`, **13,857 bytes**. Its SHA256 is `f9303dca1215f1dd0f784ab91347fa6e95df44396f3f19c9079f0faa1efa20b6`.
- Wheel metadata name/version, module/source byte equality, safe wheel paths, included license and all hashed RECORD entries were checked. A real `--quiet` argument-parsing assertion passed with the wheel on the existing interpreter's import path; it was not installed.
- The first verification assumed LF metadata lines; the wheel used different line endings. That assertion failed after the build. Validation was corrected to parse email-style headers, the build reran, and all checks passed. This was a validation error, not a package-install failure.
- Both owned temporary build folders were removed. The verified source archive, wheel, setup recipe, MIT notice, successful build log and receipt are intentionally retained for review/reproducibility.

The universal wheel tag permits selection for the proposed target, but **execution on Python 3.13 is untested**. The new interpreter was not downloaded under this approval. Actual packaging-tool versions are recorded as imported from the existing runtime, whose broader package metadata remains inconsistent; that runtime is not certified by this build.

## Resolution history and network boundary

Historical failed direct-URL and missing-Docopt attempts remain in the validation folder. After adding the approved local wheel, the resolver progressed to Colorama but the PyTorch mirror offered an archive without usable separate metadata. The network guard blocked that archive GET before transfer. Its failure log/receipt remain retained.

The CPU mirror was then limited to `torch`, `torchaudio` and `torchcodec`. Other packages resolve from PyPI. The final dry run completed using package index pages and separate wheel metadata; remote archive GETs remained blocked. `--dry-run`, `--ignore-installed`, `--no-cache-dir`, `--only-binary=:all:` and explicit CPython 3.13/Windows x64 target arguments were used. The approved local wheel was bound to its recorded hash. No source build was permitted within the resolver itself.

Pip's cross-target resolution can still evaluate some environment markers against the host Python. Independent checking therefore evaluated required extras to a fixed point, target Python/OS markers, version constraints, root pins, wheel tags and artifact SHA256 availability. The initial dry run selected 86 packages; `async-timeout` is required only for older Python and was excluded from the target lock after reachability analysis. The retained raw report preserves this difference. All 128 active target dependency links are satisfied.

Each selected transitive package is listed below with its requesting parent(s), so its reason is reviewable. For example, `aiohttp` is required through the `fsspec[http]` extra. The candidate does not request Coqui's `[all]`, server or notebook extras. Trainer/tensorboard dependencies are still required by the selected base package and were retained; removing them without changing/validating the package recipe would not be a correct dependency lock.

## Download and disk budget

'''
    total=budget['total_artifact_bytes']
    text+=f'The 85 selected package artifacts total **{total:,} bytes ({total/1048576:.1f} MiB)**, including the already-built local Docopt wheel. If that wheel is reused, remote package archives would total **{total-13857:,} bytes**. These are planned download sizes, not downloads performed in this pass. PyPI JSON verified exact filenames/hashes/sizes; official PyTorch HEAD responses provided the CPU wheel sizes. The mirror denied the first HEAD requests with HTTP 403; primary-host HEAD requests succeeded. No response body containing a package archive was fetched.\n\n'
    text+='''This total excludes the Python interpreter archive, extracted package size, installed runtimes, temporary installation overlap and existing model weights. Exact installed disk usage requires an approved staged installation and measurement. CPU packages were chosen for this first dependency evaluation; GPU testing would require separately reviewed matching artifacts. Existing weights and FFmpeg libraries would be reused only after their paths and compatibility are verified.

## Exact candidate package inventory

The JSON lock retains each artifact URL, filename, SHA256, declared license fields, requested extras and every active dependency link. The text lock binds exact artifact URLs and hashes. Its Docopt `file:` URL is specific to this workspace; a portable installer must deliberately rewrite that reference to the retained owned wheel, preserving the hash. This review lock is not an approved installation command.

| Package | Version | Archive bytes | Reason / requesting packages |
| --- | --- | ---: | --- |
'''
    for item in lock['packages']:
        name=item['name']; reason=roots.get(name) or ', '.join(sorted(parents[name]))
        text+=f"| `{name}` | {item['version']} | {sizes[name]['bytes']:,} | {reason} |\n"
    text+='''
## Files changed and retained evidence

- `dev/build_approved_docopt_helper.py`: the bounded source download, safe extraction, isolated existing-tool build, wheel/parser checks and owned temporary cleanup.
- `dev/resolve_runtime_plan_metadata_only.py`: hash-bound local helper input, separate labelled evidence, restricted CPU mirror and archive-transfer guard.
- `dev/check_xtts_candidate_closure.py`: independent target marker/extras/version/tag checks, host-only package exclusion and review locks.
- `dev/measure_xtts_lock_metadata.py`: package size/hash metadata and CPU archive HEAD measurement only.
- `dev/prepare_runtime_repair_plan.py`: records the scoped helper approval, completed metadata closure and download budget while retaining `install_authorized=false` and `release_ready=false`.
- `dev/document_xtts_lock_preparation.py`: this completion inventory and state/source/cleanup integrity receipt.
- The repair plan and release-readiness document now reflect completion of this bounded step.

Evidence: [Docopt receipt](validation/2026-10-13-docopt-helper/receipt.json), [successful build log](validation/2026-10-13-docopt-helper/build.log), [MIT notice](validation/2026-10-13-docopt-helper/LICENSE-MIT), [guarded failed mirror receipt](validation/2026-10-13-metadata-only-with-docopt-receipt.json), [successful metadata-only receipt](validation/2026-10-13-metadata-only-scoped-mirror-receipt.json), [raw resolution report](validation/2026-10-13-xtts-scoped-mirror-resolution-report.json), [target review lock](validation/2026-10-13-xtts-candidate-lock-review.json), [hash-bound text lock](validation/2026-10-13-xtts-candidate-review.lock.txt), [download budget](validation/2026-10-13-xtts-download-budget.json), [completion integrity](validation/2026-10-13-xtts-lock-preparation-integrity.json).

## Remaining gates and next bounded step

No production runtime/defaults, settings, graph, hardware profile, model registry, preferences, voices or accepted output media were intentionally changed. Previous production-source hashes and all five protected state hashes are checked again below. The earlier temporary Ollama trial remains absent. Full backend tests were not repeated because this pass changes planning/build helpers and documentation, not production code.

Before installation: review this exact candidate, complete package notice/vulnerability review, define owned interpreter/staging locations and obtain a separate approval for interpreter/package downloads and isolated candidate creation. Package metadata license fields are inventory clues, not completed redistribution/legal clearance. The application license remains the owner's unresolved decision.

After an approved staged installation: verify installed metadata consistency and import origins; measure installed disk size; run CPU/audio decoding and existing XTTS weights offline; check cancellation/output preservation/cleanup; compare voice quality and timing; then validate the app-worker bridge in a disposable copy before considering a default switch. RVC's Windows/Fairseq/OmegaConf conflicts, desktop and other profile closures, fresh-user setup, clean-machine validation and remaining full-workflow release gates are unchanged. See the [repair plan](RUNTIME_REPAIR_PLAN_2026-10-13.md) and [release status](RELEASE_READINESS_2026-10-04.md).
'''
    doc=ROOT/'docs/XTTS_DEPENDENCY_LOCK_PREPARATION_2026-10-13.md'
    doc.write_text(text,encoding='utf-8')
    baseline=json.loads((OUT/'2026-10-10-control-paths-state-integrity.json').read_text(encoding='utf-8'))
    state={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==row['current'].lower() for name,row in baseline['state'].items()}
    production=json.loads((OUT/'2026-10-12-windows-release-backend-complete.json').read_text(encoding='utf-8'))
    # Locate the recorded map without guessing or silently omitting source checks.
    maps=[value for value in production.values() if isinstance(value,dict) and value and all(isinstance(v,str) and len(v)==64 for v in value.values())]
    changed=[]
    for mapping in maps:
        for name,digest in mapping.items():
            file=Path(name) if Path(name).is_absolute() else ROOT/name
            if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=digest.lower(): changed.append(name)
    network=json.loads((OUT/'2026-10-13-metadata-only-scoped-mirror-receipt.json').read_text(encoding='utf-8'))
    helpers=['build_approved_docopt_helper','resolve_runtime_plan_metadata_only','check_xtts_candidate_closure','measure_xtts_lock_metadata','prepare_runtime_repair_plan','document_xtts_lock_preparation']
    for name in helpers:ast.parse((ROOT/f'dev/{name}.py').read_text(encoding='utf-8'))
    checks=dict(protected_state_unchanged=all(state.values()),
                recorded_production_sources_unchanged=bool(maps) and not changed,
                helper_syntax_valid=True,helper_build_and_parser_passed=helper.get('build_passed') and helper.get('smoke_passed'),
                temporary_build_workspace_removed=helper['temporary_workspace_removed'],
                ollama_trial_remains_absent=not (ROOT/'temp/ollama-eval-c_lslq8w').exists(),
                complete_target_closure=lock['metadata_closure_valid'] and not lock['issues'],
                all_dependency_links_satisfied=all(e['satisfied'] for e in lock['edges']),
                package_download_sizes_verified=budget['complete'],
                successful_resolver_no_remote_archive_transfers=network['exit_code']==0 and all(r['allowed'] for r in network['requests']),
                runtime_install_not_authorized=not plan['install_authorized'],runtime_not_installed=not plan['runtime_installed'],
                python313_execution_not_claimed=not helper['target_python_execution_verified'],release_not_claimed=not plan['release_ready'])
    receipt=dict(passed=all(checks.values()),checks=checks,state=state,changed_production_sources=changed,
                 production_hash_maps_found=len(maps),packages=len(lock['packages']),active_edges=len(lock['edges']),
                 document_sha256=hashlib.sha256(doc.read_bytes()).hexdigest(),release_ready=False)
    (OUT/'2026-10-13-xtts-lock-preparation-integrity.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))
    return not receipt['passed']

if __name__=='__main__':raise SystemExit(main())
