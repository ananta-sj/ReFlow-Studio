"""Bind import repairs, metadata-only recognition lock and preserved user state."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    lock_path = OUT / '2026-10-15-recognition-candidate-lock-review.json'
    lock = json.loads(lock_path.read_text())
    scan = json.loads((OUT / '2026-10-15-recognition-candidate-advisories.json').read_text())
    full = (OUT / '2026-10-15-import-boundaries-full-backend.log').read_text(encoding='utf-8')
    desktop = (OUT / '2026-10-15-import-boundaries-desktop-local-translation.log').read_text(encoding='utf-8')
    states = json.loads((OUT / '2026-10-10-control-paths-state-integrity.json').read_text())['state']
    assets = json.loads((OUT / '2026-10-13-xtts-candidate-preservation-before.json').read_text())['assets']
    previous = json.loads((OUT / '2026-10-13-desktop-runtime-boundary-integrity.json').read_text())
    checks = dict(full_backend_passed=bool(re.search(r'Ran 802 tests.*?\nOK', full, re.S)),
                  desktop_local_translation_passed=bool(re.search(r'Ran \d+ tests.*?\nOK', desktop, re.S)),
                  metadata_target_closure_valid=lock['metadata_closure_valid'] and not lock['issues'],
                  advisory_query_no_current_matches=scan['complete'] and scan['match_count'] == 0,
                  existing_boundary_sources_preserved=all(sha(ROOT / name) == value for name, value in previous['source_sha256'].items()),
                  saved_state_preserved=all(sha(ROOT / name) == row['current'].lower() for name, row in states.items()),
                  original_xtts_assets_preserved=all(sha(ROOT / name) == value for name, value in assets.items()),
                  no_recognition_runtime_installed=not (ROOT / 'runtime_profiles/recognition-candidate').exists(),
                  ollama_trial_absent=not (ROOT / 'temp/ollama-eval-c_lslq8w').exists())
    sources = ['core/llm_translator.py', 'core/stt/stt_handler.py', 'dev/test_engine_import_boundaries.py',
               'dev/prepare_recognition_runtime_lock.py', 'dev/check_desktop_candidate_lock.py',
               'dev/audit_desktop_dependency_projection.py', 'dev/document_recognition_migration_plan.py']
    receipt = dict(passed=all(checks.values()), checks=checks, backend_tests=802,
                   desktop_local_translation_tests=int(re.search(r'Ran (\d+) tests', desktop).group(1)),
                   source_sha256={name: sha(ROOT / name) for name in sources},
                   lock_sha256=sha(lock_path), packages=len(lock['packages']),
                   active_edges=len(lock['edges']), artifact_bytes=lock['artifact_download_bytes'],
                   install_authorized=False, runtime_installed=False, release_ready=False,
                   source_checkpoint_bytes=(ROOT / 'models/f5/reference-asr/model.safetensors').stat().st_size)
    (OUT / '2026-10-15-recognition-plan-integrity.json').write_text(json.dumps(receipt, indent=2))
    text = '''# AI worker boundaries and recognition-runtime proposal — 15 October 2026

## Outcome

Two unused Torch imports were removed from production code. The full existing runtime regression run passes **802 tests**, including two new subprocess import-boundary cases. No package, runtime or model was installed or downloaded in this iteration. Default engines, saved state and original model assets are preserved. Release eligibility remains false.

The next runtime proposal is the existing **faster-whisper CPU recognition worker**, using a separate supported Python environment. Its complete metadata-only lock has 24 packages and 31 satisfied active dependency links. No source helper build is required. This is a reviewable installation proposal, not authorization to install it or evidence of actual inference in the new environment.

## Actual runtime findings

| Stage/route | Current boundary | Remaining requirement |
| --- | --- | --- |
| Default faster-whisper | `WhisperLocalProvider` spawns `run_stt.py`; `worker_python()` defaults to the parent interpreter | Select and validate a feature-owned recognition interpreter; preflight must check that same worker |
| Whisper turbo | Existing explicit profile through `whisper_turbo_assets` | Preserve the accepted checkpoint and profile while separately migrating its unsupported Python/runtime |
| NLLB local files | Lazy Torch/Transformers model load inside the parent | Persistent owned translation worker, model-once lifecycle, cancellation and target-language acceptance |
| Default Ollama/M2M100 | Parent HTTP wrapper with local model fallback | HTTP route must not require unrelated neural libraries; actual M2M100 fallback still requires its own supported runtime |
| IndicTrans2 | Existing explicit isolated session | Supported-runtime/portable recipe migration remains; profile text alone is not a readiness certificate |
| Demucs background separation | `run_demucs.py` subprocess, currently using the generic parent worker resolver | Its own supported runtime and matching preflight; preserve checkpoint checksums, deterministic shifts and stem validation |

Do not change the global worker resolver to one feature's candidate: Wav2Lip and other workers use it too. Each migrated stage needs an explicit selection checked consistently by provider, preflight, readiness and execution evidence. Current defaults must remain working until replacement acceptance passes. RVC, vision and other specialized profiles retain their separately documented migration/licensing gates.

## Production repairs

`core/llm_translator.py` imported Torch at module load but never used it. That made even an HTTP-only Ollama route depend on the legacy neural environment. Removing that import allows the wrapper to load and execute its existing HTTP logic without Torch. Local M2M100 initialization still imports Transformers and requires its neural dependencies; nothing was removed from that actual feature boundary.

`core/stt/stt_handler.py` also imported Torch without using it. The actual inference engine is faster-whisper/CTranslate2; removing the unused import avoids incorrectly requiring the speech-generation framework for this CPU recognition worker. CPU/int8, beam size five, VAD and transcription-language metadata behavior remain unchanged. No new engine/framework or transcription algorithm was introduced. [Official faster-whisper architecture and CPU usage](https://github.com/SYSTRAN/faster-whisper).

Two new real subprocess tests deliberately block every Torch import. One imports the real translator and exercises it with mocked HTTP inventory/translation replies; the other imports the actual recognition handler with a stub faster-whisper engine and checks its CPU/int8/VAD contract and returned language metadata. Both assert that no Torch import was attempted. These are boundary/contract checks, not live model quality tests or calls to a connected Ollama service.

## Regression results and retained failure

The first focused desktop run requested the whole translation-integrity module plus the new cases: **47 tests, two errors**, retained in `2026-10-15-engine-import-boundaries-focused.log`. Both errors enter actual NLLB generation requiring Torch. This is an unmigrated local AI route, not a reason to strip a necessary Torch import from NLLB or add it to the desktop candidate.

The two boundary cases then passed alone in the desktop candidate. A separately scoped run of the existing `LocalTranslationTests` class and those cases passed; its exact test count appears below. All 802 backend cases passed under the existing main runtime in 119.891 seconds. The full run includes the NLLB tests with their required environment. The two standalone scripts capable of live model/state mutation remain excluded as before. Test-fixture download log lines do not represent real downloads.

No new human naturalness test, live translation service call, recognition inference, full-video validation, resource calibration or native UI walkthrough was performed. The previous desktop native acceptance remains historical; these two source import removals do not constitute a new portable assembly.

## Exact recognition candidate

Target: ordinary Windows x64 CPython **3.13.16**, separate owned `runtime_profiles/recognition-candidate`, reusing the verified existing 22,062,362-byte bootstrap without copying another profile's site-packages. Preserve the main and desktop runtimes, saved selections and all current model assets.

Root: **faster-whisper 1.2.1**, retaining the current recognition engine family. Transitive native packages include CTranslate2 for CPU inference, PyAV for audio decoding and ONNX Runtime for VAD. Torch is not in this package closure. PyAV's bundled native media libraries still require their own notice/native review; this does not replace the app's existing FFmpeg muxing/mixing executable. [Official requirements](https://github.com/SYSTRAN/faster-whisper#requirements).

| Package | Exact version | Download bytes | Required by |
| --- | --- | ---: | --- |
'''
    for row in lock['packages']:
        text += f"| {row['name']} | {row['version']} | {row['bytes']:,} | {', '.join(row['parents']) or 'Recognition root'} |\n"
    text += f'''
All 24 exact artifact URLs/hashes, Python constraints, parents and dependencies are retained in [the target lock review](validation/2026-10-15-recognition-candidate-lock-review.json) and [hash-bound review lock](validation/2026-10-15-recognition-candidate-review.lock.txt). The lock's `install_authorized` and runtime acceptance fields remain false.

Published artifact sizes total **{lock['artifact_download_bytes']:,} bytes ({lock['artifact_download_bytes']/1048576:.2f} MiB)**. This is a download budget, not an extracted size or a complete portable-app footprint. The binary-only metadata resolver used the existing packaging tools, Windows/Python target arguments and a guard blocking remote archive transfers and builds. Independent reachability/extra/constraint/tag checks exclude `exceptiongroup` and `tomli`, which were selected for the older host but are not required for Python 3.13. All 31 target links are satisfied. No package archive was downloaded; hashes are published values awaiting actual byte verification.

The exact-version OSV scan completed for all 24 packages with **zero current package matches** at `{scan['checked_at']}`. This does not certify native bundled libraries, model data or future advisories. Full artifact notices and native compatibility remain installation acceptance work.

## Offline model reuse for the proposed evaluation

The working local Whisper turbo checkpoint exists at `models/f5/reference-asr`, with its pinned file manifest. The safetensors payload is **{receipt['source_checkpoint_bytes']:,} bytes**. No complete CTranslate2 `model.bin` was located under project models; the external Systran cache namespace has no snapshot directory. No download is inferred from that incomplete cache.

The existing main runtime already imports **CTranslate2 4.6.3** and exposes its Transformers converter. Proposed evaluation may convert the existing local turbo checkpoint into a separate owned CTranslate2/int8 representation, using these existing tools with networking blocked and `trust_remote_code=False`. Verify all original checkpoint hashes first, preserve the checkpoint, retain the converted model's provenance/hashes, and measure output size and memory. This conversion has not been run and compatibility is not yet proven. Its output may require substantial additional disk space, estimated around a gigabyte; reserve space and measure rather than claim an exact footprint. No additional model download or new conversion tool is proposed.

After approved package installation, validate import origins/versions, metadata closure, native PyAV/CTranslate2/ONNX operations and actual offline recognition on existing media. Compare language, wording, time bounds and cancellation/output preservation against the working baseline. Test the public recognition provider/worker boundary with the explicit candidate interpreter before considering any selected-route/default change. If the existing checkpoint cannot be converted with owned tools, stop that dependent test and report the specific blocker; do not fetch a substitute model or install conversion dependencies automatically.

## Next approval scope

The reviewable next action is **only** the exact 24-package recognition candidate, existing-bootstrap reuse, offline conversion of the existing checkpoint into an owned evaluation directory, and real CPU recognition/worker tests using current media. Preserve working runtimes/settings/models/defaults, block model/network calls during inference/conversion, collect artifact notices and remove owned installer staging after verification. This does not authorize a new translation/separation runtime, extra packages, GPU drivers, model downloads, paid calls, default migration or release publication.

NLLB/M2M100/IndicTrans2 and Demucs need their own exact supported-runtime recipes and worker acceptance. The next plans must account for modern Transformer compatibility, cancellation, model lifetime and owned media paths; do not assume the XTTS dependency lock automatically supports every other model. Full workflows, clean Windows native onboarding, RVC/visual engines, resource/parallel calibration and licensing remain release gates.

## Final preservation and evidence

All nine final integrity checks pass: full backend regression, scoped desktop local translation, valid target closure, advisory acceptance, prior boundary source hashes, five saved-state hashes, eight original XTTS asset hashes, absence of a new recognition installation and continued absence of the Ollama trial. Only the two intentional production imports changed; their new source hashes and planning/test tool hashes are bound in the current receipt.

Scoped desktop test count: **{receipt['desktop_local_translation_tests']}**. Final plan receipt: `validation/2026-10-15-recognition-plan-integrity.json`. Other retained evidence includes root metadata, guarded resolver request/report/log receipts, target lock/budget, exact-version advisory results, the initial failed desktop-focused run, corrected desktop runs and the 802-test regression log, all under `docs/validation/2026-10-15-*`. Historical validation receipts were not overwritten.
'''
    (ROOT / 'docs/RECOGNITION_MIGRATION_PLAN_2026-10-15.md').write_text(text, encoding='utf-8')
    print(json.dumps(receipt, indent=2))
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
