# Optional workflow import inspection — 9 October 2026

## Purpose and authorization

This iteration follows the optional-engine dependency checks. The user authorized continued development while deferring live model calls. Work therefore uses installed environments, offline imports, tiny CPU arithmetic, synthetic/mocked regression fixtures and documentation. There are no installations, new models, checkpoint loads, model inference or remote API calls. The accepted editorial video is not regenerated.

The objective is to explain incomplete import checks and ensure a dependency pass measures the interfaces the application actually calls. It is not a voice-quality comparison or a demonstration that arbitrary videos finish successfully.

## Retained diagnostic observations

`dev/diagnose_optional_imports.py` starts the existing F5 and MuseTalk interpreters sequentially in owned temporary workspaces. Each child uses the standard fixed probe route, offline flags, private caches, a Python socket-connect audit block, progress timings and stack snapshots every 30 seconds. Each route retains its existing 90-second limit. The temporary workspace is cleaned after completion or timeout. No persistent model cache is cleared or warmed deliberately; normal operating-system caching can still affect import times. Fresh private caches and offline behavior can add startup work, so these measurements are dependency-inspection observations, not normal rendering benchmarks.

The original source-bound receipt is `validation/2026-10-09-optional-import-diagnostic.json`. It records unchanged settings/registry and captured probe sources during that run. Separate stack logs preserve the incomplete attempt rather than replacing it with a later passing observation.

| Route | Observation before the workflow-check change | Time |
| --- | --- | --- |
| Generic F5 | Timed out while importing `f5_tts.api`; unverified | 90.172 s |
| MuseTalk | Dependency and tiny CPU calculation passed | 48.922 s |

F5 reached Torch at startup, torchaudio at 11.000 seconds, torchcodec decoders at 11.453 seconds and the F5 API at 25.578 seconds. The 30-second stack snapshot shows Hydra/OmegaConf imports and filesystem metadata lookup; the 60-second snapshot shows Transformers constructing its lazy import structure while F5 imports its inference utilities. The installed F5 model package also imports its trainer from its package initializer. These are observations of import work, not proof of a deadlock, antivirus interference, corrupt packages or a specific filesystem bottleneck. No third-party package source was modified to bypass those dependencies.

MuseTalk reached OpenCV at 35.125 seconds and the CPU check at 47.329 seconds, finishing in 48.922 seconds. Its environment reports Torch 2.7.1+cpu and Transformers 4.39.2. The previous 90-second timeout and this later passing run establish variable observed startup time. They do not explain the original delay or validate lip-sync rendering. The offline Transformers cache-migration warning was retained; no online migration or model download was attempted.

Logs: `validation/2026-10-09-f5tts-import-stacks.log` and `validation/2026-10-09-musetalk-import-stacks.log`. The warnings are diagnostic data, not instructions to remove offline mode or upgrade/install packages.

## Production correction

Previously the MuseTalk checker imported third-party dependencies and selected model classes but did not import the bundled workflow. A missing workflow dependency could therefore remain undetected even when its listed packages passed. The checker now adds the same bundled source directory used by `feature_worker.musetalk`, imports `scripts.inference`, verifies its resolved origin stays under that source directory, and requires a callable `main`. It does not call `main`, parse render arguments, create a face detector, construct a model or load weights. Inspection of the current source confirmed checkpoint-backed objects are created inside functions/constructors, not at module import.

The generic F5 checker now requires callable `F5TTS` and `F5TTS.infer` interfaces after its imports. It does not instantiate the class or invoke `infer`. Missing interfaces fail explicitly rather than allowing an import-only pass. The timeout/device contract and Dashboard behavior are unchanged. This is generic F5, distinct from the previously checked IndicF5 Hindi route.

Modified production file: `core/runtime_probe_worker.py`. Diagnostic additions: `dev/diagnose_optional_imports.py`; the backend receipt runner accepts a separate `optional-workflow` label. No frontend or dependency declaration changed.

### Windows verification-runner encoding repair

The first full run reached all 729 tests but reported five errors caused by `UnicodeEncodeError` in status printing (reference cleanup, janitor cleanup and visual/lip-sync paths). The standalone runner set `PYTHONIOENCODING` after Python had already opened its own stdout/stderr using Windows cp1252. That environment update only affects future child processes. The application entry point already reconfigures its streams as UTF-8; the runner did not previously mirror that initialization. This is an observed verification-harness fault, not evidence that the normal application entry point has the same defect.

`dev/verify_dialogue_backend.py` now reconfigures available stdout/stderr streams with UTF-8 and replacement for invalid characters, matching `main.py`, before executing tests. It also includes its own source hash in the final evidence inventory. Production audio/janitor/lip-sync behavior was not changed to address this harness failure. The first failed run remains available as `validation/2026-10-09-optional-workflow-backend-first-run.json/.log`; it is not overwritten or relabeled as passing. The rerun tests the corrected runner without depending on an external shell encoding override.

## Regression validation and evidence limits

Three new tests verify that the F5 synthesis interface is required without engine construction, that the bundled MuseTalk workflow is imported without calling it, and that missing/shadowed workflow modules fail before the device calculation. Mock objects exercise checker behavior; they do not establish that actual model packages render successfully. The first focused run exposed a fixture error: a plain mock did not implement tensor matrix multiplication. Replacing that tensor fixture with an arithmetic-capable mock corrected the test without changing production behavior. Both the initial failed log and passing final log are retained.

Final focused validation passed **35 tests in 1.500 seconds**, recorded in `validation/2026-10-09-optional-workflow-focused-final.log`. Actual checks of the changed worker and the full regression totals are recorded below. No new browser/build validation is claimed because frontend source did not change.

### Installed check after the correction

`validation/2026-10-09-optional-workflow-diagnostic.json` records the changed worker with its own source hashes and unchanged captured files. The stronger MuseTalk route passed in **39.797 seconds**, reaching the bundled workflow import at 38.110 seconds and CPU arithmetic at 38.391 seconds. No workflow/model constructor or inference function was invoked. This supplies actual source-import evidence in addition to mocked regression coverage. It does not establish a performance improvement: timing varies between these retained runs.

Generic F5 remained incomplete at **90.172 seconds**, after starting the API import at 26.954 seconds. Its second stack log shows additional progress into Transformers generation imports. The API interface check was therefore not reached; there is no actual passing claim for generic F5. The receipt's `timed_out: true` governs that incomplete observation; its last partial child result is deliberately retained as `checking`, not promoted to success. Logs are `validation/2026-10-09-optional-workflow-f5tts-import-stacks.log` and `validation/2026-10-09-optional-workflow-musetalk-import-stacks.log`. The fixed 90-second budget was not increased.

## Remaining work

Final full validation passed **729 tests across 41 modules in 107.656 seconds**, with zero failures or errors, using the corrected runner. Receipt/log: `validation/2026-10-09-optional-workflow-backend-complete.json/.log`. The prior five encoding errors are preserved in the first-run receipt, which also recorded unchanged settings and sources. Final source hashes still match the tested inventory; saved registry/settings remained unchanged during the suite; the accepted editorial video SHA-256 remains `0e4dc4a51253b5b4a0172ec2842647f0f2b643480135d6c27e4876b0442bf0a2`. These preservation checks are recorded in `validation/2026-10-09-optional-workflow-evidence-integrity.json`.

Generic F5 import completion remains open until an actual bounded check completes. MuseTalk now has a passing bundled workflow import and CPU arithmetic observation, while checkpoint compatibility, rendering and CUDA support remain unverified by this iteration. Neither dependency check proves timing fit, speaker quality or full-video acceptance. Release remains pending. Further installations, dependency upgrades, inference or external model calls require the user's separately scoped authorization.
