# Separate Windows desktop candidate — deep acceptance, 14 October 2026

## Decision

**The separate desktop candidate passes its scoped acceptance. The complete application does not pass release approval.** The new environment can load the real Windows interface and application controls, handle media/state/credentials, and operate the existing isolated CPU XTTS worker. Default recognition, translation and other legacy AI stages have not yet been migrated into supported worker environments. It cannot replace the current main runtime for all jobs.

The user's “go ahead… do a very deep check and approval test” authorized the preceding reviewable proposal: the exact 31-package lock, reuse of the owned Python 3.13 bootstrap, separate candidate construction/testing, preservation of current runtimes/defaults, disposable test state, no AI downloads and installer cleanup.

No production default or application source was changed in this pass. The main Python 3.10 runtime and existing engine profiles remain in place. No paid API call, new model, compiler, package manager, system Python/PATH/driver change or publication occurred. Windows remains the first supported release target; this pass says nothing about native Linux/macOS acceptance.

## Construction and verified files

The candidate resides at `runtime_profiles/desktop-candidate`, with an explicit owner marker and a profile bound to the reviewed lock SHA-256 `c5ed102387065f69b75fa1e0ca9a75304e88754dde919dba11b4951aed39c895`. It uses ordinary embedded CPython **3.13.16**, copied from the verified owned bootstrap without copying XTTS's package environment.

All 30 remote wheels were fetched into an owned staging directory and verified against the exact published artifact sizes and SHA-256 hashes. The already-approved proxy-tools wheel was reused and reverified. Installation used existing packaging tools, a local hash-bound artifact list, `--no-index`, `--no-deps`, binary-only target arguments, no compilation and a target directory inside the candidate. Nothing was installed globally or into an older runtime. Remote wheels were not resolved again during installation.

The exact 31-distribution metadata set has no duplicate names and matches every reviewed version. Each imported desktop module originates in the candidate. Torch is absent from that environment, and configuration correctly falls back to CPU while selected missing engines still report errors.

After cross-target installation, freshly generated CLI launchers were removed: these reference the host build interpreter and are not used by Reflow. An initial RECORD verifier treated their missing paths as failures. Its raw receipt is preserved. The correction recognizes only the eight specifically removed launcher records; it does not skip arbitrary missing package files. **All 1,793 remaining hashed installed payload files matched their RECORD hashes and sizes**, including native libraries, code and metadata. The final post-acceptance verification repeats that check and user-state/model preservation.

Notice files were collected for all 31 packages. Collection does not complete license/source obligations or resolve the proxy-tools MIT/BSD metadata discrepancy described in the helper report. Owner licensing, native bundled components, FFmpeg and model terms still require distribution review.

## Acceptance results

| Test scope | Result | What it establishes |
| --- | --- | --- |
| Actual installed candidate backend | 92 checks passed | Exact versions/origins, native imports, media/credential/state operations and application bootstrap |
| Initial native WebView2 smoke | 5 checks passed | Real built frontend mounted; JavaScript called the real Python bridge |
| Corrected native screens/selector walkthrough | 22 checks passed | Six main navigation screens, available isolated XTTS option and actual saved selection |
| Real isolated XTTS parent/child test | 11 checks passed | Speech, worker release, cancellation, completed-output preservation and cleanup |
| Explicit desktop regression suite | 438 tests passed in 53.625 seconds | State, graph, queues, processes, recovery/contracts and desktop behavior in the new environment |
| Broad existing backend-suite attempt | Failed: 518 reported tests, 1 failure and 12 errors | The desktop environment cannot execute every legacy AI-dependent route/test |
| Installed payload and preservation | All six checks passed; 1,793 files verified | Installed hash agreement and unchanged original source/state/models/runtime identity |

The phase check counts are assertions with some overlap, not distinct comprehensive feature tests. The 438-case suite has an explicit retained module list. It must not be presented as an 800-case full-app pass. The earlier 800-case run remains historical acceptance under the old environment.

### Native dependencies, audio and credentials

Real Python.NET/CLR loading and `System.Windows.Forms` imports passed on this computer. The candidate imported all expected GUI/state/media helpers from its own installed packages. NumPy/SoundFile wrote and decoded a one-second 24 kHz tone with bounded sample error; pydub decoded the same non-silent clip through the Python 3.13 audioop replacement. No neural model was involved in those checks.

The Windows credential backend stored/read/deleted a randomly named disposable value under a test-only service. It neither enumerated nor read existing user API credentials. The actual PythonBridge initialized with temporary config-derived paths, loaded the graph, returned source/target languages and four pipeline templates, persisted temporary Settings/UI preferences, kept a fresh model registry empty, and exported a source-language subtitle file.

The default audio route correctly reported missing `faster_whisper` during feature preflight; desktop integrity did not falsely promise that recognition was installed.

### Real hidden Windows interface

A hidden **Edge WebView2** window loaded the actual built `frontend/dist/index.html` through a file URI with the actual bridge. Native storage and all application state paths were disposable. JavaScript bridge calls retrieved settings, languages, templates and integrity results.

The expanded walkthrough invoked the actual Dashboard, Nodes, Assets, Marketplace, Logs and Settings navigation buttons, verified their active state, opened the Radix XTTS selector, selected its enabled “Isolated CPU runtime” option, and confirmed through the bridge that the choice was saved. This validates live DOM/React/bridge behavior, not static source matching.

The first expanded fixture left first-run onboarding incomplete, allowing its wizard to cover the pages. Although underlying DOM checks passed, that receipt is insufficient as unobstructed page acceptance. A separate corrected fixture marks onboarding complete **only in temporary state**, verifies the wizard overlay is absent, and repeats the screen/selector checks. Both receipts remain retained. No production onboarding behavior was altered.

These hidden-window checks are not a manual visual layout review, a complete first-run wizard test, an interactive mouse/keyboard/accessibility evaluation, or proof of WebView2/CLR availability on a clean Windows machine. The current machine already had its native prerequisites; none were installed here.

### Actual isolated speech and cancellation

The accepted portable speech/cancellation contract was reused through asserted one-occurrence path substitutions under the candidate's Python 3.13 parent. Temporary config/settings/jobs replace the portable-copy state paths, and new evidence filenames preserve historical results. The existing model/reference media were explicitly reused, with no weights copied into the desktop candidate and offline policy enabled.

Actual speech was generated and decoded as non-silent audio. The owned speech worker exited at the end of its stage while the enclosing job remained active. A subsequent generation was interrupted after a real token boundary; the caller acknowledged cancellation in **0.018 seconds**, the previously completed output was unchanged, and the workspace/test settings were removed. This is caller acknowledgement, not a general cold-start, rendering-speed or complete process-exit benchmark. Speech naturalness was not newly reviewed by the user; no voice-quality or timing adjustment was made.

Retained output: `validation/2026-10-14-desktop-candidate-speech.wav`, SHA-256 `85b89909e63d3774fe86a1a31cc466c3d086b44c3ef26af93460f3452e64caa3`. The child runtime retains identity `85a69c83e2310e8e53303987947f2313cb4c6aa70627eeccae3b85b564fd8163`.

## Broad-suite failures and approval limits

The broad launcher requested the existing full suite, excluding the two standalone scripts that can download/mutate models. Only 518 cases/placeholders were reported because several modules failed during import; unimported cases were not executed. The result is retained unchanged: **one failure and twelve errors**.

- Ten module import errors reach the legacy TTS handler or translator and require absent Torch: cancellation, IndicF5 integration, IndicTrans2 integration, model contracts, parallel speech, source language, speech integrity, speech language, transcription metadata and translation integrity.
- Generation-control testing requires absent Transformers.
- Visual-contract testing requires absent OpenCV.
- The output-integrity media test expected a later media-validation error, but audio preflight correctly stopped earlier because default Whisper is absent.

These failures were not repaired by adding unapproved AI dependencies or suppressing feature preflight. Some test modules couple unrelated checks to a legacy handler import; future ownership work should separate desktop tests from those engine-specific fixtures. More significantly, the actual default AI routes still need supported workers before this candidate becomes a complete app runtime.

The separately identified desktop suite then passed all 438 cases. It covers the available desktop/state/queue/process contracts. AI behavior exercised with mocks remains contract testing; it does not establish actual inference quality for the missing engines.

## Warnings, footprint and cleanup

Python 3.13 emits existing pydub regex escape warnings; the source was not patched merely to hide them. Other fixture warnings/deprecations remain in the logs. None failed the scoped backend/native/audio/speech checks.

Final candidate logical file size: **91,376,775 bytes**, about **87.14 MiB**. This excludes application source/frontend, FFmpeg, all models and other engine profiles; it is not the size of a complete portable release or disk allocation. The installed candidate is retained for comparison and has `production_default=false`, `release_eligible=false` and `full_app_runtime_migrated=false`.

The owned installer staging directory was verified inside the workspace, checked for its owner marker/reparse paths, and removed after verification: **24,693,387 bytes**. The earlier approved helper source/wheel/notices and acceptance evidence remain intentionally retained. The Ollama evaluation remains absent.

Final checks confirm that the original five saved-state files, eight XTTS assets, previous production/boundary source hashes and isolated-runtime identity remain unchanged. No custom reference voice, user output or original model was deleted.

## Changed artifacts and evidence

New development tools: `build_desktop_candidate.py`, `evaluate_desktop_candidate.py`, `verify_desktop_candidate_speech.py`, `verify_desktop_candidate_files.py` and `finalize_desktop_candidate_acceptance.py`. They build/test the candidate with owned/disposable paths; production app code is unchanged. Added artifacts include the separate runtime, package notice inventory, test receipts/logs, one speech WAV and this report. The runtime/acceptance profile is explicit about its limited scope.

Key evidence under `docs/validation`:

- `2026-10-14-desktop-candidate-downloads.json`, `...-install.json` and install/build logs.
- `2026-10-14-desktop-candidate-backend.json`, `...-native.json`, `...-native-controls.json`, `...-native-controls-ready.json` and corresponding logs.
- `2026-10-14-desktop-candidate-speech.json`, `.log` and `.wav`.
- `2026-10-14-desktop-candidate-full-backend.log`: broad failed run; not replaced by the scoped pass.
- `2026-10-14-desktop-candidate-desktop-suite.log` and `...-suite-modules.json`: the explicit 438-test pass.
- `2026-10-14-desktop-candidate-file-integrity.json`: initial launcher-verifier failure; `...-final.json` and `...-after-acceptance.json`: corrected payload/preservation checks.
- `2026-10-14-desktop-candidate-notices/inventory.json` and retained notices.
- `2026-10-14-desktop-candidate-staging-cleanup.json` and `...-acceptance.json`: cleanup and scoped acceptance decision.

## Next architecture work

Define and validate supported worker ownership for default Whisper, NLLB/M2M100, Demucs, RVC and the remaining visual stages. Preserve each working route until its replacement passes; prepare exact package plans and obtain installation approval for any new dependencies. Existing IndicF5/IndicTrans2/specialized profiles need their separate supported-runtime/portability acceptance as well.

Then exercise full video/audio/subtitle jobs, optional stages, long/noisy/music/multiple-speaker inputs, download/retry/offline onboarding and recovery against a fresh portable artifact on clean Windows. Verify resource estimates and bounded parallel execution with real workloads. Resolve owner/third-party/native/model licensing before publication. Until those gates pass, the current candidate is approved for further development/testing, **not release or default migration**.
