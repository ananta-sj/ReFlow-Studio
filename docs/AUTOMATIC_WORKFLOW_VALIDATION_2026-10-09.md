# Automatic workflow validation and review repairs — 9 October 2026

## Scope

The user requested validation of the application workflow beyond the approved, manually reviewed Hindi sample. This iteration checks fresh recognition/translation, single-voice native speech generation, timing guards, reviewed-video editing/rendering, cleanup ownership and export. It distinguishes live model runs from stored editorial examples and unit fixtures. No new framework, package, model or runtime is installed.

The prior full render remains a candidate awaiting human acceptance. Approval of source 88.000–99.160 seconds is retained separately; it does not establish approval of its newly placed ending or the automatic pipeline.

## Fresh-input results

### Sample 3: punctuation-only recognition

`Sample/3.mp4` is about 15.935 seconds in its container. Fresh Whisper recognition of the decoded audio returned a single punctuation-only `.` cue, English language probability 0.383944. The old adapter admitted that as a speech line; IndicTrans2 then refused it because source-language confidence was below 0.80. No translation, TTS, review snapshot or output video completed. Owned workspaces were removed. Original evidence is preserved in `validation/2026-10-08-strong-whisper-app-review-8808d47e.json` and `validation/2026-10-09-independent-video-prepare.log`; the original driver had a historical 8 October label despite this run occurring on 9 October.

This did not prove that words were present or absent in the source. It exposed an invalid recognition result being handled as speech and producing a misleading downstream translation error. The new adapter guard now reports **“No spoken words were recognized. Check the source audio or choose another clip.”** for punctuation/emoji-only output. Raw recognizer evidence remains with the provider. Unicode letters/numbers, including Hindi, Chinese and Arabic digits, are preserved. This is not voice activity detection or a general hallucination filter.

### Sample 1: unresolved language and suspicious repetition

Fresh full-video recognition of `Sample/1.mp4` (102.621 seconds) produced suspicious repeated phrases, later lyrical text and a punctuation-only final block. The minimum language confidence was 0.314511. IndicTrans2 refused automatic translation rather than guessing. No dub or final review was published. The recognizer was released and owned workspaces were removed. Receipt: `validation/2026-10-09-strong-whisper-app-review-639aa57e.json`; log: `validation/2026-10-09-independent-spoken-video-prepare.log`.

This is a failed automatic preparation case, not evidence of a working narration dub on a second independent source. No manual language override, invented transcript or replacement translation is used to relabel it as successful. Low-confidence/noisy/musical input remains a release limitation. A punctuation guard cannot fix repetitive lexical hallucinations.

### Live spoken-excerpt automatic test

`dev/verify_automatic_hindi_video.py` runs the real `ReflowPipeline.run('video_dub', ...)` on source `Sample/2.mp4`, seconds 115.600–119.600. This is a fresh excerpt execution, **not a new independent recording**. Existing installed Whisper turbo, IndicTrans2 and the confirmed Abhishek IndicF5 reference are selected in memory; saved app model selection is not substituted into the test. Recognition, translation and speech are live. No previously accepted takes, spoken-draft fixtures, timing edits or manual source/translation text are supplied. The known original source remains hash-protected.

The test uses automatic language selection, voice-only output, Hindi soft subtitles and one speech worker. It intentionally does not validate background separation, multiple speakers, parallel GPU speech, lip synchronization or enhancement. Those require separate evidence. Instrumentation records actual provider results without replacing inference. A successful candidate would prove this bounded automatic path structurally, while human meaning/delivery review remains necessary.

The first attempt failed before inference because the diagnostic driver used `burn_subs` instead of the pipeline's `burn_subtitles`; the driver was corrected, and its failed receipt/log retained. The second attempt reached real recognition, translation and speech initialization but was interfered with by the global cleanup check described below. It was stopped through its specific worker's stop marker and retained as a failed run. It is not a speech-quality failure or a successful automatic render. The final retry runs separately from the broader cleanup suite.

## Application timing editing

The approved sample required editorial timing changes outside the ordinary review screen. Users could edit wording or combine lines, but could not adjust their start/end times. That prevented reproducing even basic timing corrections within the application.

The review screen now has **Line starts at / Line ends at** fields in seconds. Wording and timing save together through the existing revision-checked bridge call. Unsaved timing participates in the same dirty-state protection as text, and original-line playback requires saved edits. Discard restores both timing and wording. The preparation button now says “media” because videos are supported.

`ReviewStore.edit` accepts optional start/end values while remaining compatible with old text-only calls. It validates finite numeric values, source bounds, start-before-end and non-overlapping lines. It recomputes affected speech windows and candidate fit flags. Fitting accepted recordings retain their files/hashes; moving a line does not synthesize, stretch or truncate its speech. A timing change that would cut any accepted line, including the preceding line whose window shrinks, is rejected atomically. Text changes still invalidate only that line's takes. Invalid/stale/no-op edits preserve the record appropriately. The last timing edit retains previous/new bounds and prior revision as provenance.

This does not add automatic shot alignment, arbitrary sentence splitting or expressive speech controls. Listening again after moving a line remains necessary; stored waveform acceptance does not prove synchronization at another position.

## Cleanup interference and repair

The broad test suite contains a legacy `Janitor.sweep` call using the project's global temporary directory. Running it concurrently with live inference exposed that it could remove another render's pending files. The live TTS request then had no response to read. Windows reported a locked worker log during the sweep, but this did not prevent deletion of other files. Running the suite concurrently was therefore not independent of the live render. The interrupted run is retained; subsequent live and broad checks are performed separately.

`Janitor.sweep` now preserves the complete `temp/jobs` tree, whose lifetime belongs to each `RenderContext`. It clears only legacy top-level temporary entries. It verifies that the absolute cleanup target remains inside its configured project root and refuses root deletion, links and reparse points before recursive removal. Managed/orphan job workspaces are not declared obsolete or silently globally deleted.

`FeatureSession.call` now detects a removed pending request/session folder, requests stop for its owned job and reports an explicit failure promptly instead of waiting up to an hour for a lost response. `close` can stop an owned worker when its folder is missing, without recreating the deleted workspace. Existing owned process shutdown and cleanup still drain handles. Real fixture-process tests exercise request removal and cleanup behavior.

No user's originals, retained media or installed model files were targeted by this repair. The previously interrupted worker was signalled through its known job-specific stop file, not a global process-kill command.

## Changed source files

- `core/transcription.py`, `core/providers/stt/whisper_turbo_local.py`: lexical-speech validation and retained raw evidence.
- `core/cue_review.py`, `bridge/api.py`: atomic optional timing edits with bounds, accepted-take and revision protections.
- `frontend/src/lib/api.ts`, `frontend/src/components/shared/CueReviewPanel.tsx`: bridge arguments, timing fields and unsaved-state handling.
- `core/janitor.py`, `core/feature_session.py`: managed-job preservation and removed-request failure/shutdown.
- `dev/test_cue_review.py`, `dev/test_whisper_turbo_integration.py`, `dev/test_feature_session.py`: regressions for these behaviors.
- `dev/test_suite.py`: the real credential check uses a unique dummy key rather than risking reuse of a fixed test key.
- `dev/verify_indictrans2_app_review.py`: explicit dated labels and recording raw recognition/release evidence even when postprocessing fails.
- `dev/verify_automatic_hindi_video.py`: live pipeline validation driver with explicit excerpt/provenance boundaries.

## Verification so far

- Focused recognition, metadata/language, IndicF5 integration and cue-review checks: **136 passed**, 71.925 seconds. Log: `validation/2026-10-09-review-workflow-focused-tests.log`.
- Frontend TypeScript/Vite production build passed. Existing bundle-size warning remains; no dependency was added. Log: `validation/2026-10-09-review-workflow-frontend-build.log`.
- Existing architecture UI contract checks: **18 passed**. Log: `validation/2026-10-09-review-workflow-ui-contracts.log`.
- Initial full backend module run: **571 checks**, 569 passed and two environment-access errors (sandbox-local sockets and Windows credential access). Log: `validation/2026-10-09-review-workflow-backend-suite-retry.log`. The initial discovery invocation also failed before tests because `dev` is a namespace directory; explicit module loading corrected the invocation. Its log is preserved.
- The two real OS-access checks were rerun with authorized host access and **both passed**. They use loopback-only HTTP and a unique dummy credential. Log: `validation/2026-10-09-os-permission-checks.log`. No production key is read or printed by the credential test.
- Final targeted cleanup/session/cancellation/recognition/review checks: **66 passed**, 23.259 seconds. Log: `validation/2026-10-09-workspace-safety-tests.log`.

The completed live output and configuration/package-copy updates are recorded below; the earlier test results are retained as dated checkpoints. Current results do not establish Linux/macOS support, clean-machine first use, all engines, all languages, general voice naturalness or release readiness.

## Completed live automatic excerpt

The separate retry completed successfully in **125.547 seconds** through the real automatic `video_dub` path. Receipt: `validation/2026-10-09-automatic-hindi-video-95a5a0e6.json`; log: `validation/2026-10-09-automatic-hindi-video-final.log`. Recognition identified English with actual language-token probability **0.9995605** and returned the sign-off words. IndicTrans2 generated Hindi; IndicF5 freshly synthesized **2.336 seconds / 56,064 frames at 24 kHz**. There were no substituted transcript/translation strings, reused recordings, timing edits or manual language override. Recognition and translation workers were released between stages, the speech worker was released after generation, and the owned workspace was removed.

The fresh speech WAV hash `6f6a7fd544d94a70bfef0bd0b3ef4facf67443faab1dffcc86d1e9d84f625a57` happens to reproduce the historical sign-off take because reference, wording and deterministic synthesis settings match. Instrumentation confirms a live provider call with a new worker PID; equality is not evidence that the saved take was copied into synthesis.

Output: `validation/2026-10-09-automatic-hindi-video-95a5a0e6/source-excerpt_DUBBED_HI_566a5dc87aff.mp4`, SHA-256 `a9475a10e1636774bea42e12ad41e6768c84bca4d57c286d7e377d665d476692`. The complete video decodes, contains video/audio/soft-subtitle streams, has Hindi subtitle language `hin`, and lasts **4.000 seconds**. The original source hash is unchanged.

This proves a short, clean, one-cue mechanical pipeline. It is not a whole-video timing/wording pass, a test on another independent speech recording, human approval of the fresh result or background preservation evidence. The raw full-video preparation audit still has only **3/14** translations fitting their native windows; eleven require wording or timing review. That remains the larger automatic-dubbing limitation.

## Saved-engine connection and automatic voice reference

The audited app registry had no selected STT, translation, TTS or voice engine. The successful live excerpt selected installed engines in memory, so that alone would not configure the application. `dev/connect_tested_hindi_stack.py` prepares to connect the already-installed Whisper turbo, IndicTrans2 and confirmed Abhishek IndicF5 GPU profile through the existing app connection/activation APIs, after the first complete final check run. It refuses to overwrite any independently changed selection, preserves the original registry as a backup and records identifiers, paths and hashes. It downloads/installs nothing and leaves voice calibration/seed unchanged.

`dev/verify_automatic_hindi_video.py --use-saved-engines` is the subsequent validation route. It does not install a fixture registry or override model entries and asserts that the persisted selection remains unchanged during rendering. The completed configuration and subsequent saved-settings run are recorded below.


### Completed configuration and final reference handling

The app connection completed through the existing APIs. Receipt: `validation/2026-10-09-tested-hindi-app-selection.json`. The prior empty selections are preserved in `validation/2026-10-09-model-selection-before.json`. Active connections are Whisper turbo (`a8ecd3d7-c58d-4baa-8a6b-165d06d856b8`), IndicTrans2 English-to-Hindi (`46071594-480f-4035-ae8c-2e0701a19c73`) and confirmed Abhishek IndicF5 GPU (`b7bc4114-0308-453c-93dc-a4e33b37700e`). No package, model download or calibration change was made.

The saved voice exposed a further usability failure: an omitted reference upload previously fell back to source vocals, which cannot match the confirmed Hindi profile. `core/providers/resolve.py::confirmed_reference` now loads and validates the selected confirmed profile. Automatic audio/video dubbing and review preparation use its exact recording when no upload is supplied. An explicit upload must exist and match either the confirmed WAV or the recorded original-source hash; the canonical confirmed WAV is used in either case. Profile integrity and human-confirmation validation remain mandatory. Other speech engines retain their existing reference preparation. The Marketplace connection message explains the automatic reference behavior.

Regression coverage adds absent-upload, matching-upload, wrong/missing-upload and changed-profile-audio checks; review preparation verifies sample-exact preservation without an upload. **43 focused checks passed in 21.988 seconds** (`validation/2026-10-09-default-reference-tests-workspace.log`). The first attempt used sandbox-owned OS temporary storage and encountered access errors; its failed log is retained, and the successful retry used the writable project temporary root. The final frontend build passed (`validation/2026-10-09-default-reference-frontend-build.log`) with the existing bundle-size warning.

Before this reference follow-up, the complete backend suite passed **573 checks in 80.273 seconds** (`validation/2026-10-09-review-workflow-backend-final-isolated.log`). An earlier final attempt exposed the cleanup test itself using global temporary storage; its fixture was corrected to an isolated root before that successful run. The production cleanup protects managed jobs independently of this test correction.

The QA portable application copy was refreshed after the reference/UI changes: **186 application files**, no size mismatches, one stale generated frontend asset removed. Dated receipt: `validation/2026-10-09-default-reference-portable-refresh.json`. The refresh driver still writes a legacy 4 October receipt filename, so a dated snapshot was preserved immediately. This copy excludes personal model selections and downloaded weights; it does not establish clean-machine installation or operating-system portability.


### Saved-settings live validation completed

`dev/verify_automatic_hindi_video.py --use-saved-engines` completed in **121.844 seconds**, receipt `validation/2026-10-09-automatic-hindi-video-be95b2d4.json`, log `validation/2026-10-09-saved-engines-default-reference-live.log`. It used the real persisted app registry and supplied **no reference upload**. No fixture registry, transcript, translated text, recorded speech or editorial timing was provided. The app automatically resolved the confirmed Abhishek recording from its active voice profile.

The output `validation/2026-10-09-automatic-hindi-video-be95b2d4/source-excerpt_DUBBED_HI_a0822470d3d4.mp4` fully decodes, contains Hindi subtitles and lasts 4.000 seconds. Its SHA-256 is `a9475a10e1636774bea42e12ad41e6768c84bca4d57c286d7e377d665d476692`, matching the earlier deterministic live output. Recognition, translation and speech workers released successfully; the owned workspace was removed. The original source and persisted registry remained unchanged during rendering.

This specifically verifies the saved engine/reference setup through the automatic application backend. It does not certify GUI interactions, full-video shot alignment, fresh human naturalness approval, another independent recording, multi-speaker dubbing or background preservation. The two other source files tried earlier did not produce usable automatic review preparation; their failure evidence remains above. No new installation was needed.


### Final complete regression and settings post-check

After the automatic reference changes, the complete backend suite passed **576 tests in 83.190 seconds**, exit zero. Log: `validation/2026-10-09-default-reference-backend-final.log`. Host access was used only for the existing localhost HTTP and unique dummy Windows-credential checks. Expected fixture failures appear in diagnostic output but the runner reports `OK`.

The post-suite registry hash check caught a separate test isolation error in `dev/test_model_contracts.py`: `ModelRegistry(str(test_path))` passed a path into the constructor's warning-callback parameter, leaving the actual registry path active. It added a dummy uninstalled `pending` voice entry while testing activation rejection. The test now patches `core.model_registry.REGISTRY_PATH` to its isolated fixture and constructs `ModelRegistry()` normally. Only the known dummy entry created by this run (`65ab6cb2-ae2e-4484-91ae-553cbf335090`) was removed through the registry API. The resulting file hash exactly matches the configured registry before the suite: `30cb8bca62eaf4bf562b3a603c6cf11c1e4a1f73b569526fbc1e302ce20b9a6e`. Receipt: `validation/2026-10-09-registry-test-isolation.json`. Prior user entries and active engine selections were preserved; the old backup was not restored wholesale.


The corrected model-contract test module then passed **12 checks in 0.224 seconds**, with an explicit before/after byte comparison proving the real registry remained unchanged (`validation/2026-10-09-registry-isolated-contract-tests.log`). This final follow-up changes test isolation only; the 576-test production-code result, live output and refreshed application copy remain applicable.
