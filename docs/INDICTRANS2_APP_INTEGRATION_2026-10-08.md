# IndicTrans2 app integration — 2026-10-08

## Scope and accepted baseline

The user approved the full 122.532-second Hindi dub as a usable baseline, with minor fast/slow pronunciation inconsistencies remaining. This is listening acceptance of that specific edited-Hindi take, not release approval, automatic translation acceptance on all inputs, or a claim that its pace is perfect.

Acceptance is hash-bound in `docs/validation/2026-10-08-full-video-user-acceptance.json`, pointing to the prior render receipt, exact spoken draft and output hash. The successful render and its historical `human_quality_accepted: false` receipt have not been overwritten; this separate receipt records the subsequent user feedback. The accepted output and voice settings were preserved.

This iteration connects the already installed IndicTrans2 runtime/checkpoint to the existing app translation resolver and review workspace. No framework, engine package, model, access condition or external service was added. The English-to-Hindi model remains selectable; existing NLLB selection and other translation routes remain available. There is no automatic default switch.

## Backend changes

- `core/indictrans2_manifest.json`: records the previously downloaded model revision and every asset's expected size/hash, plus the reviewed historical processor hash. Revision: `89cd0007fd7b9e0693a2fd4404d187e07dac79fd`.
- `core/vendor/indictrans2/processor.py` and `LICENSE`: copies of the already inspected historical pure-Python toolkit processor and MIT license. Processor revision: `0c607654e8b6cce897a32039df79018a1daff4e2`; SHA256: `354c3299229f8b05602d82d0a84a8c2e98082dce38879a3459ca2fc33ec8f7b8`. Its existing compatibility workaround is now an app dependency; this does not establish official Windows support.
- `core/indictrans2_assets.py`: validates pinned local asset shapes/identities and the reviewed processor; resolves the existing isolated interpreter. Small files are hashed on validation. The 4,462,265,272-byte safetensors file is checked for size initially and fully SHA256-verified in each new worker before loading.
- `core/model_contract.py`: identifies this exact pinned IndicTrans checkpoint separately from NLLB. Arbitrary models advertising the same model type cannot bypass the manifest check.
- `core/providers/translation/indictrans2_local.py`: real provider using the existing job-owned subprocess session. It validates resolved English source, Hindi target, and absence of unsupported free-text instructions before launching inference. Unknown/low-confidence sources, other languages and cross-job session reuse are rejected. One model worker is reused throughout a translation stage. Blank responses are failures, not successful translations. Direct standalone calls create and clean an owned render context.
- `core/indictrans2_worker.py`: offline local-only loading, pinned source verification before model-code execution, safetensors weights, CUDA FP16, eager attention and deterministic five-beam decoding. Requires existing Transformers 4.51.3 and Torch 2.9.1+cu128. Input is never silently truncated; oversized source windows and mechanically unfinished/output-capped translations fail. Cancellation is polled during generation and between session requests. Responses include worker PID, sequence, token counts and EOS completion.
- `core/providers/resolve.py`: the selected IndicTrans2 contract reaches its own provider instead of the NLLB adapter.
- `core/feature_session.py`: reuses the existing subprocess lifecycle; an optional label produces accurate IndicTrans2 errors rather than calling translation a speech failure. Existing F5 label remains the default.
- `core/pipeline.py` and `core/cue_review.py`: explicitly close the translation worker after successful translation stages, including subtitle translation and per-cue retranslation, before subsequent speech work. Failed jobs retain the existing owned-job cleanup callback/process cancellation path. Deleting a Python provider alone would otherwise leave its independent GPU worker alive.
- `core/runtime_checks.py`: verifies the isolated IndicTrans2 interpreter and rejects non-Hindi output in preflight. Resolved source validation occurs once transcription supplies its source-language metadata. No automatic substitution with NLLB is made when the selected IndicTrans2 route cannot handle an input.

The provider does **not** automatically condense translations, apply the accepted draft to new text, change TTS calibration, accelerate speech, or claim expressive/semantic quality from an EOS token. Raw MT may still exceed a speech window. The existing review workflow allows users to edit and audition wording; the native speech gate rejects unreviewable overflows in direct rendering.

## App controls and resource reporting

`bridge/api.py` exposes installed-engine status and an idempotent connection action. Busy rendering/downloads or invalid assets reject connection changes. Connecting adds/reuses an installed translation entry while preserving the active model. Setting it active separately revalidates the asset contract and isolated interpreter.

`frontend/src/lib/api.ts` declares the bridge functions. `frontend/src/pages/Marketplace.tsx` adds a Hindi translation card to the Translation tab, explaining English-to-Hindi scope, NVIDIA GPU use, cue review, and separate activation. Its action connects the existing installation; it does not download anything. This fixed-vocabulary model does not display the free-text instruction editor.

The connection stores checkpoint file size, revision, language scope and actual translation device. Resource estimates route translation to `cuda:0`, even with a CPU workspace, and warn that startup, duration and memory are uncalibrated. Auxiliary GPU stages now select a GPU device for the memory estimate instead of being hidden behind the workspace's CPU selection. The existing file-size/memory heuristic is conservative for FP16 loading and is not a measured peak. Stage budgets remain planning estimates and may overcount sequential model allocations; this iteration does not claim a calibrated hardware benchmark.

## Verification

`dev/test_indictrans2_integration.py` exercises language/instruction validation before worker launch; same-job reuse and stage release; blank response and cross-job failures; resolver selection; explicit stage release; idempotent connection/active-selection preservation; busy/missing-asset failures without registry mutation; and auxiliary GPU routing/memory reporting from a CPU workspace.

Targeted suite: **97 tests passed in 36.087 seconds** across new IndicTrans2 integration, existing IndicF5 integration/controls, translation integrity/completion and cue review. Log: `docs/validation/2026-10-08-indictrans2-app-tests.log`.

After resource reporting changes: **42 tests passed in 1.248 seconds** across IndicTrans2 integration and architecture contracts. Log: `docs/validation/2026-10-08-indictrans2-app-resource-tests.log`. Counts overlap; they should not be added as unique tests. TEMP/TMP were placed inside the workspace and project/core paths explicitly inserted for the embedded interpreter.

Frontend TypeScript/Vite build passed. Log: `docs/validation/2026-10-08-indictrans2-app-frontend-build.log`. The existing large-chunk warning remains a performance consideration, not a compilation failure. Targeted diff whitespace checks passed; Git also printed its ordinary LF-to-CRLF conversion warning for the Marketplace file.

## Real app review check and limits

`dev/verify_indictrans2_app_review.py` runs real app transcription, selected IndicTrans2 translation, cue-review preparation and real confirmed Abhishek IndicF5 candidate generation. Only model selection is isolated in a diagnostic registry; transcription/translation text and speech are not fixtures. Persistent app model selections are not changed. Source hashes, stage progress, candidate text/duration/fit/audio paths, cleanup and failures are saved.

The first additional source, `Sample/3.mp4`, produced no dialogue from the existing tiny CPU recognizer. The second, `Sample/1.mp4`, produced the same result. They failed before translation/speech and published no prepared review or completed dub. Original source files were preserved and job workspaces cleaned. Receipts: `2026-10-08-indictrans2-app-review-bbc6d208.json` and `2026-10-08-indictrans2-app-review-20749810.json`. Logs: `2026-10-08-indictrans2-app-review-no-dialogue.log` and `2026-10-08-indictrans2-app-review-second-no-dialogue.log`, all under `docs/validation`.

Those failed receipts' `live_asr/live_translation/live_tts` fields describe configured routes, not completed stages: their error/events/cues show that neither MT nor TTS was reached. A no-dialogue result from this small recognizer is not proof that the original source contains no speech.

A 25-second section of the known spoken `Sample/2.mp4` is now used to exercise the normal live review route without prepared source or translation text. This is an integration check on an existing source, **not** independent second-video quality validation. Its final result is recorded below once available.

### Live review timestamp defect and repair

The first 25-second attempt performed real ASR and translated four of five cues, then failed review timing validation. Receipt: `docs/validation/2026-10-08-indictrans2-app-review-8fcdfd04.json`; retained log: `2026-10-08-indictrans2-app-review-timestamp-failure.log`. The temporary job and translation worker were cleaned on failure; no prepared review or candidate audio was published.

`dev/inspect_app_review_timeline.py` reproduced the exact normal recognition result independently before translation. Evidence: `2026-10-08-app-review-timeline.json` and retained `2026-10-08-app-review-timeline-24k.wav`. The decoded source duration is 25.007917 seconds, while the final recognized cue ends at 25.040000 seconds: a 32.083 ms excess. Existing `require_media_bounds` permits 50 ms of ASR rounding, but the review manifest requires exact bounds. Thus this was a mismatch between accepted transcription timing and review constraints, not proof of a bad IndicTrans2 translation.

`core/cue_review.py` now validates the full timeline before expensive MT work. Its `review_transcription_bounds` helper clamps only an end beyond the decoded duration that already passes the existing 50 ms transcription tolerance. It copies the result without changing source text/language metadata, records cue index/original end/new end/reason in `timestamp_adjustments`, and rejects genuine out-of-bounds/overlapping or empty windows. No original recognition receipt is rewritten, and no audible source samples are removed. Two regression cases cover recorded small rounding and rejection of larger errors/overlaps.

After this repair, **111 tests passed in 29.052 seconds** across IndicTrans2 integration, cue review, translation integrity/completion and architecture contracts. Log: `2026-10-08-indictrans2-app-final-tests.log`. A separate newly added model-identity test also passed, proving modified model Python code is rejected despite unchanged byte length and same-size modified safetensors are rejected by full worker verification. Log: `2026-10-08-indictrans2-asset-identity-tests.log`. These counts overlap earlier suites.

The live diagnostic now records completed ASR/MT/TTS flags separately, retains the real recognizer transcript and raw MT responses, and observes the actual translation worker's shutdown before TTS. Instrumentation calls the original providers and does not replace generated text.

The small normal CPU recognizer's exact wording differs from the stronger recognition used to prepare the accepted full dub. For example it transcribes “Me has this report” and “Next day, walkie-talkie preamble from the altar,” and the excerpt ends mid-sentence. Language confidence is 0.987904 for English, which does not imply accurate words. This diagnostic therefore cannot establish the accepted full dub's transcription quality in the automatic app workflow. Stronger recognition integration/verification remains needed.

### Completed live app review result

Receipt: `docs/validation/2026-10-08-indictrans2-app-review-525f718f.json`. Completed in 438.782 seconds. All five real ASR-derived cues were translated by one IndicTrans2 worker (PID 18192, request sequences 1–5, all EOS-complete). Its actual shutdown was observed before Hindi TTS. All five candidate voices generated and were published into a diagnostic review. Source hash remained unchanged, persistent app registry was untouched, and every owned workspace was removed. Background separation was disabled in this narrow integration check; the earlier accepted full render already exercised that route.

| Cue | Available seconds | Native audio seconds | Fits |
|---|---:|---:|---|
| 1 | 6.640 | 8.021 | No |
| 2 | 2.600 | 1.717 | Yes |
| 3 | 5.200 | 5.291 | No |
| 4 | 5.240 | 6.848 | No |
| 5 | 5.320 | 10.027 | No |

This is successful **review preparation and candidate generation**, not a successful automatic final dub. Four raw lines overflow; there are no accepted takes or final-video publication. Review retains their complete native audio and marks them as non-fitting. The user must be able to correct recognized source wording, combine split sentences where appropriate, retranslate, shorten translated wording and audition candidates before final assembly. This run demonstrates why the accepted edited draft cannot simply be replaced by raw automatic MT.

The successful retry's fresh recognition ended at 25.000 seconds and needed no timestamp adjustment; its manifest records an empty adjustment list. The earlier independently reproduced 32.083 ms excess remains preserved, and the new tolerance behavior is covered by regression tests. No claim is made that the retry exercised a nonempty rounding adjustment.

Additional output verification: all five candidate WAV hashes match their saved records; cue 2's WAV is byte-identical to the corresponding accepted full-dub cue (`83dfc305843598715ffdafdf1c8b3c5509229912274d7c0387d2964d8c2e264c`); the accepted full video hash still matches its original receipt. Evidence: `docs/validation/2026-10-08-indictrans2-app-review-output-checks.json`. This confirms voice recipe/sample preservation for that cue, not human acceptance of the other new takes.

Prepared review record: `docs/validation/2026-10-08-indictrans2-app-review-525f718f/cue-reviews/1ff36fed6ec748deb42030b2d6a5590c/review.json`. It is diagnostic evidence under validation storage, not automatically inserted into the user's normal review library. The app's new model connection controls and existing review controls are available through the rebuilt frontend; native UI interaction itself was not automated in this iteration.

## Remaining work

- Human listening review and translation review of freshly generated automatic candidates.
- A successful genuinely different spoken-video comparison; the two additional existing samples did not produce a transcript with the current recognizer.
- Calibrate recognition/translation/startup/VRAM behavior on representative inputs; broader language coverage needs separate validation.
- Direct unedited translations may not fit native speech timing; review/editing remains necessary. The previously accepted edited draft is not a general automatic shortening algorithm.
- Existing Hindi subtitle stream metadata is still tagged `eng` in the prior video output and remains a release defect.
- General release validation across nodes, platforms, optional engines, packaging and the full feature matrix is not established by this integration iteration.
- The connection card uses the installation already present on this machine. The portable builder currently excludes model weights and exposes only the older optional-profile choices; it does not yet provision the IndicTrans2/IndicF5 evaluation profiles on a fresh machine. The legacy executable packaging also needs explicit worker/data/runtime verification. No new distributable or installer was built in this iteration.
