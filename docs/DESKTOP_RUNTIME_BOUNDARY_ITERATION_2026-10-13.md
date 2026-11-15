# Desktop runtime boundary iteration — 13 October 2026

## Purpose and release status

This iteration follows the saved XTTS selection and portable QA work. It corrects dependency ownership before preparing a clean desktop runtime: the desktop must remain usable when an optional AI engine is missing, and job preflight must validate the engine selected for that job.

**Windows release eligibility remains false.** No runtime or package was installed, no model downloaded, no saved engine choice changed, and no application license selected. The existing interpreter is still the unsupported Python 3.10.11 environment with previously documented package conflicts. The isolated CPU XTTS candidate remains an explicit trial. This work does not make the legacy engines healthy by hiding their failures.

## Findings and changes

### 1. Saved XTTS runtime was ignored by job preflight

Rendering already passed the frozen saved runtime to the XTTS provider, but audio/video preflight always imported legacy `TTS.tts.configs.xtts_config` and `TTS.tts.models.xtts`. A valid isolated job could therefore be blocked by an unrelated broken shared installation.

Both media generators now pass `xtts_runtime` from their settings snapshot and the requested/default compute device to preflight. For isolated XTTS, preflight validates the owned profile through `core.xtts_runtime.validate()` instead of importing legacy TTS. GPU selection raises a CPU-only error; an unsupported `other:` adapter follows the existing CPU fallback. Legacy selection continues checking both legacy imports, and an unknown runtime value is rejected. Cloud TTS, IndicF5, F5 actor routes and subtitle-only work retain their independent checks. Preflight still checks other selected stages: this change does not permit Whisper, background separation or visual features to run without their own dependencies.

Files: `core/runtime_checks.py`, `core/pipeline.py`.

### 2. Desktop imports assumed legacy Torch was healthy

`config.py` imported Torch unconditionally, so even browsing Settings or model management could fail before a window was created. Hardware monitoring tolerated an absent module but not a broken native DLL.

Configuration and hardware monitoring now tolerate `ImportError`, `OSError` and `RuntimeError` from the optional Torch setup. Configuration records the failure text as `TORCH_IMPORT_ERROR` and uses CPU as the default when detection fails. A healthy existing Torch installation retains its previous CUDA detection and benchmarking behavior. The pipeline's best-effort VRAM cleanup also tolerates native-library load failure so cleanup cannot spoil an otherwise valid isolated route.

This is startup resilience, not an engine readiness signal. Selected legacy engines still undergo feature checks and fail with an actionable error. Saved hardware preferences are preserved. GPU detection through other existing mechanisms is unchanged; no new GPU library was added.

Files: `config.py`, `core/hardware_monitor.py`, `core/pipeline.py`.

### 3. General integrity status conflated desktop and optional AI engines

The desktop integrity action previously imported Torch, BasicSR, GFPGAN, librosa, SciPy, NumPy and tokenizers as critical desktop requirements. A missing optional enhancement engine could therefore make the desktop's general check fail.

The default check now verifies desktop dependencies: webview, pystray, Pillow, psutil, pydub, requests, filelock, packaging, keyring and tqdm. The old AI list remains available through `check_libraries(include_engines=True)` and the diagnostic CLI's new `--include-engines` option. That explicit list is a legacy shared-library diagnostic, not an exhaustive validation of every model or isolated engine. The bridge response says that desktop imports are verified and selected engines/assets are checked separately.

No diagnostic installs packages. Existing explicit legacy model restoration and installation helper behavior was not invoked in this iteration. Normal startup still does not restore model weights. A clean desktop dependency plan must include the full transitive closure, including tqdm; checking these imports alone is not a package lock or compatibility proof.

Files: `core/integrity.py`, `bridge/api.py`.

## Verification method

`dev/test_desktop_runtime_boundary.py` adds ten regression cases covering isolated selection, invalid profile rejection, CPU-only enforcement and unsupported-device fallback, legacy checks, cloud independence, subtitle independence, frozen media-generator parameters, scoped integrity imports, and two real subprocess bootstrap/export probes. Existing IndicF5 tests verify that its selected route does not require XTTS.

Each subprocess installs an import blocker before loading the real application modules. It blocks Torch, TTS, Transformers, Whisper, Demucs, enhancement, RVC and other AI imports. One case simulates missing libraries; the other makes Torch raise a native DLL `OSError`. The real configuration source executes with a disposable file location so all derived settings, model registry and output paths stay under an owned test folder. The process then imports `main`, the actual bridge and pipeline, runs desktop integrity, retrieves four templates, exports a source-language subtitle file, and exercises VRAM cleanup. Only optional Torch was attempted; no blocked AI library was loaded. Temporary test state is removed.

These probes use the existing Windows interpreter and simulate unavailable AI imports. They do **not** start a native window, install Python 3.13 desktop packages, measure GUI rendering, test WebView2 on a clean machine, perform neural translation, or generate new speech. The source subtitle export preserves the English cue and timing; it does not assess dubbing quality.

The focused run passed 67 tests. Its first launch failed to discover `dev` because the embedded interpreter excludes the workspace from its default path. The corrected runner explicitly adds the project and core directories, matching the existing regression launcher. Both logs are retained. This was a test-launch error, not an application failure.

The complete regression result and protected-state verification are recorded in the final evidence section below. Two standalone scripts that can download/mutate models remain excluded from unittest execution, as in the previous iteration. Apparent model-download messages in the regression log come from mock fixtures, not live model downloads. Frontend code is unchanged; no new frontend build or native GUI acceptance is claimed.

## Protected state and packaging

`dev/verify_desktop_runtime_boundary.py` binds the final test run and subprocess receipts to current production/test source hashes. It checks the five saved user-state hashes, the eight original XTTS asset hashes, the isolated XTTS profile identity, and continued absence of the temporary Ollama trial. It does not rewrite any of those protected files.

The earlier `dist/portable-xtts-trial-2026-10-13` QA copy is retained as its previously tested snapshot. It has not been refreshed with this iteration's edits. Its historical live-speech and cancellation results remain historical; they must not be presented as acceptance of the latest source. The new integrity receipt lists source differences relevant to that earlier snapshot. No new assembled footprint is claimed.

## Work still required

1. Resolve and review an exact clean desktop package closure, artifact hashes, licenses and installation cost; obtain the required installation approval before creating that candidate. The desktop roots listed in the runtime repair plan are proposals, not an installed environment.
2. Exercise desktop imports and native interactions in that actual candidate. Verify startup, model management, Settings, recovery, batch controls and selected-engine errors on a clean Windows machine.
3. Migrate remaining AI workers off the unsupported/conflicting shared environment. RVC's old Fairseq/NumPy/OmegaConf constraints need a separately reviewed Windows solution. This iteration leaves those packages untouched.
4. Refresh or assemble a new portable QA artifact only after the candidate and source are settled; validate that artifact, rather than reusing earlier snapshot acceptance.
5. Complete representative full workflows with long/noisy/music/multiple-speaker media, optional stages, downloads/retries/offline operation and resource estimates. Preserve the previously accepted Hindi quality baseline.
6. Resolve owner licensing and third-party/model distribution obligations before publishing. Other platforms remain experimental.

## Evidence

- Initial test discovery failure: `validation/2026-10-13-desktop-runtime-boundary-focused.log`.
- Corrected focused run: `validation/2026-10-13-desktop-runtime-boundary-focused-with-path.log`.
- Complete backend run: `validation/2026-10-13-desktop-runtime-boundary-backend.log`.
- Source, state, model and runtime identity receipt: `validation/2026-10-13-desktop-runtime-boundary-integrity.json`.

Final results: **800 complete backend tests passed in 139.631 seconds**. Both real subprocess bootstrap/subtitle-export probes passed within that run. All six consolidated integrity checks passed: backend acceptance, both probe modes, five original saved-state hashes, eight original model-asset hashes, unchanged isolated XTTS runtime identity, and continued absence of the owned Ollama trial. No installation or native-window acceptance occurred.

The preserved XTTS runtime identity is `85a69c83e2310e8e53303987947f2313cb4c6aa70627eeccae3b85b564fd8163`. The previous portable evidence's tracked production-source hashes now differ for `core/pipeline.py` and `bridge/api.py`. The other files changed in this iteration were not all included in that earlier receipt's source list; this is not an exhaustive portable file comparison. The new receipt records every current changed production file. No copied QA artifact or historical receipt was updated.
