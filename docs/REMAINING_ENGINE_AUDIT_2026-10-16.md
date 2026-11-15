# Voice conversion and visual engines: current audit and repairs

Date: 16 October 2026. Decision: narrow repairs and current-engine checks pass; full release remains unaccepted. No package, runtime, framework or model was installed in this iteration.

## What changed

Four production files were repaired:

1. `core/rvc/rvc_handler.py` now preserves `RenderCancelled` during engine/asset initialization, voice-model loading and conversion. It no longer labels a user stop as an engine initialization/conversion failure. Existing temporary preprocessing cleanup and atomic output publication remain active.
2. `core/lipsync_handler.py` preserves the same cancellation exception from its owned worker. Fixed status strings now use plain text, preventing those symbols from causing cp1252 console failures. This does not establish universal console support for arbitrary Unicode filenames or third-party logs.
3. `core/providers/filter/nudenet_local.py` imports the in-process detector only when that fallback is actually used. The isolated filtering route no longer requires OpenCV/NudeNet in the desktop parent just to import its wrapper.
4. `core/providers/enhancer/gfpgan_local.py` defers its Torch-dependent enhancer import until enhancement is requested. Resolving the wrapper no longer imports the heavy engine prematurely. This does not supply an isolated GFPGAN runtime: execution still requires the enhancement dependencies in its selected current process.

No settings/defaults, graph controls, API schema, frontend source, models or installed third-party package source changed. The preceding separation, recognition, translation and XTTS trial integrations remain intact.

## Installed runtime observations

The existing bounded probe was run from both the original portable interpreter and the clean desktop interpreter. These checks import dependencies and test selected-device arithmetic; they do not construct checkpoint-backed models.

| Engine | Original portable launch | Clean desktop launch | What was actually inspected |
| --- | --- | --- | --- |
| NudeNet | Passed | Passed | Existing optional `vision` CPU runtime in both cases |
| F5 | Unverified: 90-second import timeout | Unverified: 90-second import timeout | Existing optional `f5` CPU runtime in both cases |
| MuseTalk | Passed | Passed | Existing optional `musetalk` CPU runtime in both cases |
| RVC | Passed | Failed: Torch missing | Current parent interpreter |
| GFPGAN | Passed | Failed: Torch missing | Current parent interpreter |
| Wav2Lip | Passed | Failed: Torch missing | General worker interpreter |

The two launch modes therefore are not twelve independent runtime installations. NudeNet/F5/MuseTalk deliberately reuse their existing optional profiles. No new GPU test was performed. The desktop failures confirm that the remaining shared-runtime routes cannot yet be advertised as migrated to the clean desktop setup.

[Original-runtime observations](validation/2026-10-16-remaining-engines-legacy.json), [desktop observations](validation/2026-10-16-remaining-engines-desktop.json), and their corresponding `.log` files retain interpreter paths, actual reported versions, diagnostic messages and preservation checks. A successful import probe is not complete engine acceptance.

## Actual filtering from the clean desktop

The revised filtering wrapper was exercised from the desktop interpreter with Torch, OpenCV and NudeNet absent there. The existing desktop legitimately includes NumPy; an initial test wrongly asserted its absence and failed before rendering. The corrected driver tests the relevant missing engine/video dependencies instead. That initial [failed receipt](validation/2026-10-16-clean-visual-boundary-initial.json) and log remain retained.

The actual existing NudeNet worker processed a generated blue, 64×64, one-second clip at three frames per second. Output retained all three frames and dimensions and fully decoded through FFmpeg. A subsequent missing-input failure preserved that previous valid output. The detector's bundled ONNX checkpoint hash was unchanged, all owned stage processes exited, and the enclosing workspace was removed. Both filter and enhancer wrappers resolved without parent engine imports.

This passes **eight checks**. A solid-color negative fixture establishes execution and publication behavior; it does not establish sensitivity, false-positive rates, detection localization or accuracy on people. No content-filter quality approval is claimed. [Actual desktop/worker receipt](validation/2026-10-16-clean-visual-boundary.json), [corrected log](validation/2026-10-16-clean-visual-boundary-corrected.log).

## Actual existing GFPGAN and Wav2Lip checks

Both engines ran on CPU in the original portable environment, with existing local assets and a one-second excerpt from the existing `Sample/2.mp4`, reduced to three frames at 640-pixel width. They did not execute in a new modern runtime.

| Test | Verified result | Observed elapsed time |
| --- | --- | --- |
| GFPGAN | Three frames, one-second output, complete decode; actual face-model forward hook fired three times | 92.329 seconds |
| Wav2Lip | Three frames, one-second output, complete decode and successful normal worker return | 11.875 seconds |

The GFPGAN hook counts actual model calls and does not substitute predictions. The generic `face_model_forward_calls` field in the Wav2Lip receipt is unused; its zero is not a measured count of lip-model forwards. Its acceptance rests on actual worker execution and decoded output. Neither result has new human approval for face quality or lip synchronization.

All three GFPGAN checkpoint hashes and the Wav2Lip checkpoint hash matched before/after execution. Processes exited and owned workspaces were removed. The driver enabled offline flags and blocked parent Python networking; no recovery/download step was requested. Wav2Lip ran its existing local worker and supplied checkpoint. Only numeric/diagnostic evidence was retained; disposable output clips were cleaned with their workspaces.

[GFPGAN receipt](validation/2026-10-16-installed-gfpgan-real.json), [GFPGAN log](validation/2026-10-16-installed-gfpgan-real.log), [Wav2Lip receipt](validation/2026-10-16-installed-wav2lip-real.json), [Wav2Lip log](validation/2026-10-16-installed-wav2lip-real.log).

These timings include relevant CPU engine startup/loading and are single observations under the current machine workload, not throughput guarantees. They reinforce the need for later performance/resource calibration.

## Why RVC remains incomplete

The registry contains **37 voice entries**, with **zero installed voice entries**. The scoped inventory found no `.pth` conversion checkpoint in `models/rvc` or at installed, explicitly registered voice paths. This is not a claim that no such file exists anywhere on the computer; unregistered personal directories were not exhaustively searched. The voice entries also are distinct from installed speech-generation/TTS models, so this finding does not mean the existing Hindi speech profiles disappeared.

RVC imports successfully in the original runtime, but real conversion cannot be accepted without a suitable selected voice checkpoint. The cancellation tests use clearly marked disposable fixtures and mocked inference boundaries; they are not evidence of actual RVC speech conversion. No replacement voice model was downloaded or invented to make the feature appear tested.

Installed RVC metadata pins `rvc-python==0.1.5`, `fairseq==0.12.2`, `numpy<=1.23.5` and `omegaconf==2.0.6`; Fairseq requires an older Hydra/OmegaConf family. Those constraints conflict with the modern environments already prepared for other engines. The original runtime also contains stale/duplicate metadata for several packages. Inventory records duplicates rather than choosing an old metadata entry as the authoritative running version or removing files. Any RVC migration needs an independently reviewed dependency/runtime design and an actual voice checkpoint; a shared-runtime package upgrade is not a safe shortcut.

[Scoped voice/model/package inventory](validation/2026-10-16-remaining-engines-inventory.json) records dependency declarations, duplicate/malformed metadata and known visual-asset existence/size checks. Size inventory is explicitly not cryptographic validation of all MuseTalk assets, nor proof of modern-runtime compatibility.

## F5 startup diagnosis

After the two 90-second probe timeouts, a separate offline import was run with a 75-second outer limit and a 40-second standard-library stack dump. It also timed out, with no model construction, followed by owned-process exit and workspace cleanup. The sampled main thread was inside Transformers' `create_import_structure_from_path` / `define_import_structure`, reached through `f5_tts.infer.utils_infer` and `f5_tts.api`.

This identifies a sampled startup location, not a complete causal profile or proof that all F5 failures have the same cause. A timeout remains **unverified**, rather than being converted into a pass, a broken-installation certainty, or an audible voice-quality judgment. No installed package was edited, timeout simply raised, or new dependency added as a workaround. [Bounded diagnosis](validation/2026-10-16-f5-import-diagnosis.json), [captured stack](validation/2026-10-16-f5-import-stack.log).

## Regression, preservation and cleanup

- **896 backend tests passed** in **196.811 seconds** in the original working interpreter. The historical standalone download/state-mutating scripts remain excluded from unittest discovery, as previously documented.
- **21 focused tests passed** in **1.240 seconds** in the clean desktop interpreter, including four new cancellation cases. The suites overlap and should not be added together.
- New RVC cases cover asset initialization, model-load cancellation and mid-conversion cancellation while preserving the prior output and removing preprocessing/pending files. The Wav2Lip case preserves the exact stop exception through a cp1252 console and preserves existing output. These specific handler tests simulate inference failures; the shared owned-process framework has separate real subprocess tests.
- Protected saved-state hashes, the preceding integration source hashes and built frontend hashes match their baselines. All five isolated runtime identities—XTTS, NLLB, recognition, M2M100 and separation—remain unchanged.
- The new real visual runs verify their relevant checkpoint hashes; diagnostic/model-generation workspaces are removed. No broad cache/model deletion, package installation, model download or default promotion occurred.

[Full regression log](validation/2026-10-16-remaining-engines-full-backend.log), [focused log](validation/2026-10-16-remaining-engines-focused.log), and [final current-source/preservation acceptance](validation/2026-10-16-remaining-engines-acceptance.json). The earlier acceptance snapshot before the supplemental F5 diagnosis remains retained separately.

Validation helpers added: `dev/test_optional_cancellation.py`, `dev/evaluate_clean_visual_boundary.py`, `dev/evaluate_installed_visual_engine.py`, `dev/audit_remaining_engine_inventory.py`, `dev/diagnose_f5_import_timeout.py`, and `dev/finalize_remaining_engine_audit.py`. Their current hashes and the four repaired production files are bound in the final receipt. The existing `dev/verify_optional_engine_readiness.py` was reused without overwriting its older dated results.

## Remaining work and next decisions

GFPGAN and Wav2Lip have actual current-engine execution evidence but still require clean runtime ownership/routing, portable dependency closure, broader visual/quality cases and performance checks. NudeNet's worker route now works from the desktop; its existing optional profile still needs modern reproducible packaging and broader detector quality acceptance. MuseTalk passes dependency imports and its expected assets are present by size, but this iteration performs no new full MuseTalk render. F5 startup remains unresolved. RVC needs an actual selected voice checkpoint and a separately reviewed runtime plan.

No new package/model approval is requested on the strength of incomplete metadata alone. Prepare exact packages, artifacts, storage estimates and tests before a later installation request. Broader Hindi/long/noisy/multispeaker workflows, automatic recognition accuracy, download/offline recovery, calibrated parallel/resource use, fresh relocated portable and clean-machine/manual acceptance, and licensing remain release gates. The application is not declared release-ready.
