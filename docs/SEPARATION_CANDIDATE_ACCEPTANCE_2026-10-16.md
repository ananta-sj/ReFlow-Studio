# Separate CPU background-separation runtime: implementation and acceptance

Date: 16 October 2026. Result: approved installation and technical trial integration completed. Application release approval remains false.

## Authorized change and measured installation

The user approved the separate separation runtime and tests described in [the prepared runtime plan](SEPARATION_HELPERS_AND_RUNTIME_PLAN_2026-10-16.md). The new `runtime_profiles/separation-candidate` was built from the reviewed 32-package lock, using existing Python 3.13.16, 22 copied distributions, four previously approved local helper wheels and six newly downloaded wheels. All six archives matched the pinned sizes and SHA-256 values. Total new transfer: **365,848 bytes**. No model was downloaded or replaced, and no existing runtime or default was migrated.

| Installation measurement | Result |
| --- | --- |
| Exact installed package closure | 32 distributions |
| Copied package payload files | 16,390, with RECORD hash/size verification |
| Extracted wheel payload files | 268, with archive/RECORD/metadata checks |
| Final candidate size | 615,796,387 bytes, approximately 587 MiB |
| Final candidate file count | 16,694 |
| Candidate `__pycache__` directories | None found at closeout |
| Owned installer staging removed | 365,886 bytes, including its marker |
| Existing model | `models/uvr/955717e8-8726e21a.th` |
| Model SHA-256 | `8726e21a993978c7ba086d3872e7608d7d5bfca646ca4aca459ffda844faa8b4` |
| Accepted runtime identity | `15d81b55cbb9f031475c56e40bdfab4f0663103592b573735f8c726fae454f20` |

The builder refused to replace an existing candidate or staging tree. It copied only reviewed package files, checked the Python bootstrap, verified the six official artifact downloads and all four reused local wheel hashes, and rejected unsafe paths, links, collisions and non-SHA-256 records. External scripts/entrypoints are recorded as omitted; execution uses the bundled worker module. There was no pip dependency resolution or source compilation during installation. [Build receipt](validation/2026-10-16-separation-candidate-build.json) and [build log](validation/2026-10-16-separation-candidate-build.log).

## Application architecture

Settings now exposes **Background separation runtime**, with **Current runtime** and **Isolated CPU runtime (trial)** choices. The current runtime remains the default. Selecting the trial applies to background preservation in audio and video dubbing; it does not redirect recognition, translation, speech or visual engines. Unavailable candidates cannot be saved through the bridge. Reading old settings does not rewrite them, and the new legacy default is removed from historical cue-review digests to avoid invalidating otherwise unchanged reviews.

`core/separation_runtime.py` validates the exact lock, Python bootstrap, 32 unique installed package metadata entries and bound worker-source recipe. It reports an explicit trial identity and checks local model availability. The parent and worker verify the existing checkpoint hash before executing model code. The runtime uses existing shared FFmpeg libraries; they are not a new download or included in the candidate-only size above.

`AudioSeparator(runtime='isolated')` selects the exact candidate interpreter rather than the general worker override. Invalid runtime names and non-CPU isolated requests fail explicitly. Its identity, interpreter and model path are exposed to normal operation manifests. The worker receives a dedicated isolated flag, checks its actual interpreter against the bound recipe, initializes the shared FFmpeg DLL directory, blocks Python network operations, and keeps restricted checkpoint loading enabled. Installation files and current third-party package sources remain unchanged.

Audio/video jobs use their frozen settings. Isolated preflight checks the selected runtime/model contract without importing Demucs in the desktop parent, fixing the audited parent/worker mismatch for this route. Engine readiness can probe native imports/device arithmetic in that candidate and retains clear limits about untested output quality. Missing/broken trial runtimes do not silently fall back to the legacy environment. Cancellation still propagates as `RenderCancelled`, and all subprocesses remain job-owned.

Portable inventory explicitly includes the selected candidate and its lock/recipe. Fixture tests verify that closure and exclusion of personal settings. No complete new portable copy was assembled or physically relocated in this iteration.

## Actual compatibility repair and retained failure

The first real model run failed under restricted loading: the existing checkpoint records `numpy.core.multiarray.scalar`, while NumPy 2 exposes the callable under `numpy._core`. The precise existing callable was added with its old serialized name to the isolated worker's restricted safe-global list. This is limited to the explicitly selected, version-locked trial; unrestricted pickle loading was not enabled. The original checkpoint is hash-pinned, not rewritten.

The initial [failed model receipt](validation/2026-10-16-separation-candidate-real-initial.json), original log and original routing recipe remain retained. The recipe-refresh helper preserves the prior recipe before explicitly rebinding the repaired source. Successful current inference has the new runtime identity above. This repair does not edit NumPy, Torch or Demucs package sources.

The first video harness attempt also failed because its deliberately constructor-free pipeline fixture lacked `temp_dir`. The harness now sets it to the owned job workspace. That failed [initial video receipt](validation/2026-10-16-separation-video-initial.json) and log remain retained separately from the successful corrected test. No production video fix was needed for that setup error.

## Validation evidence

| Check | Result and scope |
| --- | --- |
| [Full backend regression](validation/2026-10-16-separation-routing-full-backend.log) | **891 tests passed**, 122.606 seconds; historical standalone download/state-mutating scripts excluded |
| [Final focused desktop checks](validation/2026-10-16-separation-routing-focused-complete.log) | **46 tests passed**, 7.877 seconds; overlaps the backend suite |
| [Candidate native acceptance](validation/2026-10-16-separation-candidate-native.json) | **48 checks passed**: actual Python/interpreter, exact unique closure, 12 native/module origins and CPU arithmetic |
| [Real separation acceptance](validation/2026-10-16-separation-candidate-real.json) | **12 checks passed**: actual stems, repeated outputs, runtime evidence and active-child cancellation |
| [Native interface acceptance](validation/2026-10-16-separation-routing-native.json) | **22 checks passed**: actual WinForms/WebView2 bridge, six-screen navigation and selector persistence with disposable state |
| [Real short video](validation/2026-10-16-separation-video.json) | **9 checks passed**: actual separation, recognition, XTTS, subtitle/audio/video output, manifest and worker release |
| [Frontend build](validation/2026-10-16-separation-routing-frontend-build.log) | TypeScript/Vite passed; build 6.63 seconds; existing build warnings retained |

The real separation driver ran from the clean desktop interpreter, verified Torch/TorchAudio/Demucs are absent there, and deliberately set an invalid global worker override. The explicit candidate route still ran. It processed the same one-second source excerpt twice in fresh owned child processes. Both produced stereo 44.1 kHz playable vocal/background WAVs, with exact duration and **16-bit PCM** output. This validates the actual writer, despite TorchAudio's warnings about its encoding arguments. Output hashes matched across the two runs. Observed stem RMS values were 1,547 and 25; those are measurements, not a speech-removal quality score. The two calls took **23.331** and **23.434 seconds**, including startup/model loading.

A third separation call observed an actual registered active child, requested stop, received `RenderCancelled`, and released its process. Cancellation returned in **0.111 seconds**. This tests process cancellation during an active invocation, not a neural inference boundary or a universal latency guarantee. The enclosing workspace was removed. [Complete corrected real-run log](validation/2026-10-16-separation-candidate-real-corrected.log).

## Real video workflow and performance limit

The video test used the first six seconds of the existing moving-frame `Sample/2.mp4`, with actual background separation, existing converted Whisper recognition, existing XTTS reference/model and normal post-processing/muxing. All three AI stages used their explicit isolated CPU choices from disposable saved settings. No speech, transcript or translation fixtures replaced those models. The global worker override remained invalid, so the test could not accidentally rely on it.

Output contained video, audio and subtitle streams, fully decoded without FFmpeg errors and retained an exact **6.0-second** timeline. The completed manifest records the actual separation interpreter and runtime identity. Owned stage workers exited and the job workspace was removed. The test's target was **source language (English)**: it did not exercise translation or establish Hindi-dubbing acceptance. Audible background quality, original-dialogue leakage and speech naturalness have not received new human approval.

The complete test took **213.997 seconds** for six seconds of media, with startup and CPU speech generation included. That is approximately 36 times the media duration in this test. It is a material performance limit, not an interactive-speed result or a broad benchmark; other tests were also running on this machine. GPU options and long-video throughput still require separate calibration.

[Generated video](validation/2026-10-16-separation-video/source_DUBBED_SOURCE_977bfebc8056/source_DUBBED_SOURCE_977bfebc8056.mp4), [completed run manifest](validation/2026-10-16-separation-video/run_records/cf7087b29c114579bfebef619ff955a8/manifest.json), and [full corrected log](validation/2026-10-16-separation-video-corrected.log) are retained for inspection. Keeping this output is test evidence, not a request to resume repeated subjective voice-tuning loops.

## Notices, cleanup and preservation

Installed notice files were collected for **31 of 32 distributions** under `validation/2026-10-16-separation-candidate-notices`. ANTLR remains the one installed-notice gap; its separately collected official version-tag supplement from the helper stage was rechecked. The final receipt distinguishes that supplement from files actually shipped in the wheel. Owner licensing, model and FFmpeg terms, and final distribution preparation remain unresolved; notice collection does not grant distribution clearance.

The owned installer staging path, marker and exact seven-file contents were checked before individual file removal and directory removal. No recursive deletion of an inferred path, existing model, sample, user output or working runtime was performed. The final scan found no candidate `__pycache__` directories. Preserved evidence includes the build/failed-run/native/video receipts, package notices and source hashes.

After all tests, protected saved-state hashes, the existing Demucs checkpoint and prior XTTS/NLLB/recognition/M2M100 runtime identities matched their baselines. The new profile is marked technically validated for trial use, with production-default/release-eligibility flags still false. [Final current-source, preservation, size and cleanup receipt](validation/2026-10-16-separation-candidate-acceptance.json).

## Changed files and remaining release gates

Production: `core/separation_runtime.py`, `core/audio_separator.py`, `core/run_demucs.py`, `core/settings.py`, `core/pipeline.py`, `core/cue_review.py`, `core/runtime_checks.py`, `core/engine_readiness.py`, `bridge/api.py`, `frontend/src/lib/api.ts`, `frontend/src/pages/Settings.tsx`, and `packaging/build_portable.py`.

Build/validation: `dev/build_separation_candidate.py`, `dev/prepare_separation_routing_recipe.py`, `dev/evaluate_separation_candidate.py`, `dev/evaluate_separation_native.py`, `dev/evaluate_separation_video.py`, `dev/evaluate_separation_settings_native.py`, `dev/test_separation_runtime.py`, and `dev/finalize_separation_candidate.py`. Their current hashes and the built frontend hashes are in the final receipt. Do not rerun the one-shot builder over the existing candidate or refresh a drifted worker recipe without new relevant validation.

This closes the approved separation installation and integration step. It does not close RVC/visual runtime migration, automatic recognition accuracy/Hindi–Urdu ambiguity, broad translation/speech quality, representative Hindi and long/noisy/music/multispeaker workflows, original-dialogue leakage review, download/offline onboarding recovery, resource/parallel/GPU performance calibration, fresh relocated portable/clean-machine/manual-accessibility acceptance, or licensing decisions. Windows portable remains the primary release target; other platforms remain experimental. The application is not declared release-ready.
