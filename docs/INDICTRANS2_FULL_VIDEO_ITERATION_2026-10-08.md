# IndicTrans2 full-video Hindi review — 8 October 2026

## Why this iteration exists

The user reviewed the 19-input comparison and found both engines useful, with IndicTrans2 sometimes preferable to NLLB's literal wording. This was preliminary text feedback, not acceptance of every output or permission to silently change the app's defaults. The user approved a full-video review using IndicTrans2's text and the previously accepted IndicF5 voice settings.

The source is the entire `Sample/2.mp4`, duration 122.531701 seconds. Earlier accepted moving-video listening tests covered only the first 52 seconds. This run covers the full source rather than labelling that excerpt as full-video validation.

## Stages and actual implementation

1. Existing local Whisper large-v3-turbo recognizes the complete source with English explicitly selected, using the existing GPU evaluation profile. No recognition model is downloaded or replaced.
2. Timed phrases are grouped into translation inputs. The original recognition blocks and raw timed cues remain in the receipt for inspection.
3. Pinned IndicTrans2 runs offline in its separate evaluation profile, with FP16 CUDA, eager attention, five beams, no sampling, and explicit input/output completion guards.
4. The existing application video-dubbing pipeline consumes those measured timed source/translation receipts as fixtures and runs the real IndicF5 provider, real CPU background separation/mixing, stem publication, subtitle muxing, final media decode, and cleanup checks.

Recognition and translation are real model executions before the render, but their application resolvers are substituted with the resulting fixtures during rendering. This is a staged full-media integration test, not proof that IndicTrans2 has been integrated into the production Marketplace or that the normal application ASR/translation resolver chain uses it. No registry/default settings are changed.

## Transcript preparation and boundary issue

Initial complete recognition produced 15 grouped cues. At 60 seconds, a recognition-block boundary split this sentence:

> I think what we want to hear is actually what's happening and not what other people think of it.

The recognizer ended the previous block with `not.` and began the next with lowercase `what`. Translating these fragments independently would lose context. Full-video preparation now joins a group at a 30-second block boundary only when it starts lowercase and the preceding group ends in `and`, `or`, `but`, `because`, or `not` followed by a period. The artificial boundary period is removed, all recognized words remain in order, and the joined timing spans both groups. The receipt retains both constituent groups as `recognition_boundary_joins`.

The initial recognition receipt and interrupted translation attempt are not presented as final results. Fresh recognition after this adjustment produced 14 translation inputs, including the final timed tail. This is a diagnostic preparation heuristic, not a production transcription algorithm change. The source wording beyond the previously reviewed excerpt still needs human review; ASR punctuation does not guarantee correct sentence boundaries.

Final source receipt: `docs/validation/2026-10-06-indicf5-video-cues-9493ecb5.json`. The legacy filename date comes from the reused helper; this run was performed on 8 October. Future full-source runs now use an 8 October full-video prefix.

Original source SHA256: `f104d7dfd83109a71655ccfeddec7d2055295d8cba02901e2c3075c3fb41d88c`.

## Translation result

All 14 inputs translated successfully with natural EOS termination below the 256-position decoder window. Input truncation is disabled; oversized inputs fail rather than silently losing words. The model's raw generated Hindi is used without editorial rewriting so this remains a valid engine/dubbing evaluation.

Receipt: `docs/validation/2026-10-08-indictrans2-full-video-translation.json`.

The raw text has known unresolved wording issues. In addition to the earlier film-term/sarcasm errors, the longer section translates `sound bites` as `ध्वनि काटने` and `punter` as `पंचर`. These are translation problems to review, not evidence of voice-generation language drift. The closing `Thank you` becomes `थैंक यू`, an English expression written in Devanagari. That is generated translation text, distinct from audible leakage of the source audio. No claim of fully natural or fully correct Hindi is made.

## Voice and background controls

- Voice: existing confirmed Abhishek IndicF5 reference profile and its exact prepared reference audio.
- Speech device: existing isolated GPU speech worker; the normal render uses CPU for background separation.
- No additional tempo tuning, reference replacement, TTS engine installation, voice training, or new model default.
- Background route enabled, with separate background/original-vocal/dubbed stem exports for examination.
- Subtitles included without burn-in; lip sync, enhancement, and content filtering disabled for this controlled comparison.
- One speech worker should be reused and released before the pipeline finishes.

The previous listening acceptance of source-dialogue suppression applies to the earlier 52-second render. It does not automatically accept leakage, background preservation, delivery, or intelligibility in this new two-minute render.

## Render evidence and checks

Render log: `docs/validation/2026-10-08-indictrans2-full-render.log`.

The renderer writes a new `docs/validation/2026-10-08-indictrans2-full-video-<id>.json` receipt and evidence directory. Its `completed` and `automatic_pipeline_pass` fields are authoritative for automated completion. Until those are true, no finished video is claimed.

Checks include source hash preservation; complete cue generation; reference/provider identity; single worker reuse and release; video/audio/subtitle stream presence; duration within 150 ms of the full source; complete video/audio decode; equal stem timelines; output hashes; and removal of temporary job workspace after evidence publication.

The existing subtitle muxer still labels attached subtitles as English even when their text is Hindi. This is a known metadata issue, not a translation quality judgment or a release-ready claim. It must be corrected and verified before release.

## Changes in this iteration

- `dev/prepare_indicf5_video_cues.py`: full-source and source-only options; duration probing; recording the full final tail; block-boundary continuation handling; full-source filename prefix and context flag correction. Default excerpt behavior remains available.
- `dev/compare_indictrans2_evaluation.py`: full-cue receipt option; carries the exact source wording/timings/hash into evaluated translations; separate receipt name to preserve the 19-input comparison.
- `dev/verify_indicf5_app_video.py`: paired source/IndicTrans2 receipts for review renders; validates correspondence; derives duration and expected cue count from the source instead of hard-coding 52 seconds/eight cues; distinguishes evaluated text from human-approved editorial fixtures.

## Human review needed next

Watch the full render and identify timestamps for awkward Hindi, unnatural/stuttering speech, hurried or cut words, synchronization problems, and audible source dialogue. Separate translation problems from voice delivery and background leakage. Review the sections after 52 seconds especially carefully because they have not previously been accepted. The first full render is a candidate for this review, not approval to replace NLLB or ship the application.

## Actual first render outcome: timing guard stopped the job

The full-source separation completed, and the pipeline reached real IndicF5 synthesis. The first Hindi cue required 7.381 seconds at the accepted native delivery, but only 6.400 seconds were available before the next cue. The pipeline stopped rather than cutting audible words, accelerating the accepted voice, or mixing overlapping dialogue. No successful full-video artifact was produced.

Failure receipt: `docs/validation/2026-10-08-indictrans2-full-video-f468235f.json`. Inspect `completed: false`, the exact timing error, and workspace cleanup status. Successful isolated translation does not establish dubbing feasibility.

The next concrete diagnostic compares the raw IndicTrans2 opening with the already human-approved concise editorial opening, using the same confirmed Abhishek profile and no tempo changes. `dev/compare_full_video_opening_timing.py` verifies the prior editorial acceptance hash, generates both through the real provider, measures their native durations, publishes the samples/receipt, and releases the worker. This is explicitly a translation/wording comparison, not a change to the voice recipe or a raw IndicTrans2 improvement.

Raw opening: `जल्द ही, एक मानक समाचार रिपोर्ट दृश्य भाषा ने खुद को स्थापित कर लिया, जिसे कोई भी तुरंत पहचान सकता है।`

Previously accepted concise opening: `जल्द ही खबरों को दिखाने का एक तय अंदाज़ बन गया, जिसे हर कोई पहचान लेता है।`

Next required work is duration-aware spoken-Hindi adaptation and a new full render once the adapted wording is reviewable. The raw model outputs remain preserved for comparison. Human review must acknowledge any condensed nuance; the app must not silently claim edited wording is raw model output.

Opening timing comparison completed: raw IndicTrans2 is 7.381333 seconds; the previously accepted concise opening is 5.290667 seconds. Both use the same Abhishek profile, without tempo changes. Receipt: `docs/validation/2026-10-08-opening-timing-9a9026b4.json`.

A separate 14-cue spoken draft is now prepared in `docs/validation/2026-10-08-full-video-spoken-hindi-draft.json`, with a side-by-side review document at `docs/FULL_VIDEO_SPOKEN_HINDI_DRAFT_2026-10-08.md`. It retains raw translations in `raw_translation`, labels each wording's origin, carries source hashes/times, and explicitly marks full-draft acceptance and speech-duration verification as false. The first eight lines reuse the earlier accepted editorial wording; the remaining six are new assistant proposals. Compression, tone changes, and the transliterated wordplay are listed for human review.

The new review render uses this separate spoken draft. Its log is `docs/validation/2026-10-08-spoken-hindi-full-render.log`, and its output receipt prefix is `2026-10-08-spoken-hindi-full-video-`. The renderer marks `editorial_text_fixture_used: true` and `evaluated_indictrans2_text_used: false`, so its result cannot be mistaken for raw IndicTrans2 quality. It still uses the same live voice provider and background route. Read the resulting completion/timing fields before claiming a finished video.

### Second attempt: unsupported punctuation and early-validation repair

The first spoken-draft render generated and fitted cues 1–11, then stopped at cue 12 because its em dash (`U+2014`) is absent from the pinned IndicF5 vocabulary. The existing worker correctly rejected unsupported text, but this happened too late to avoid separation/model-loading work. Failure receipt: `docs/validation/2026-10-08-spoken-hindi-full-video-c6ee8f66.json`. Log: `docs/validation/2026-10-08-spoken-hindi-full-render-unsupported-punctuation.log`. The temporary workspace was cleaned; these 11 successful intermediate takes were not published as a completed video.

The draft's em dash was replaced with an ordinary comma. Its prior JSON is retained as `2026-10-08-full-video-spoken-hindi-draft-before-punctuation-fix.json`. No letters, words, voice settings or tempo were changed by this punctuation correction.

`core/providers/tts/indicf5_local.py` now validates speech and confirmed-reference characters against the actual vocabulary before selecting/starting a worker. Unknown codepoints produce a clear error; the provider does not silently delete or substitute them. The worker's own validation remains in place. The full-video diagnostic additionally validates all draft lines before separation. All 14 inputs and the reference pass this preflight with the real vocabulary.

Two regression tests cover rejection before worker startup while preserving an existing output, and reference-character rejection/supported-text acceptance. The combined IndicF5 integration/control suite passed all 20 tests. The first test invocation encountered Windows sandbox temporary-directory rename restrictions in registry tests; rerunning with TEMP/TMP inside the workspace resolved those environmental failures. Both logs are retained; final evidence is `docs/validation/2026-10-08-indicf5-character-preflight-tests-final.log`. The targeted diff whitespace check also passed.

The corrected full render completed with identical voice/background settings. Its successful receipt and the remaining human review limits are recorded below.

### Early native-duration preflight

`core/providers/tts/indicf5_local.py` now predicts the fixed native waveform length using the existing worker's UTF-8 pace calibration, 256-sample synthesis hops, sentence segmentation, and configured inter-sentence silence. It validates the prepared reference as nonempty mono 24 kHz audio and rejects sentences exceeding the model's frame limit. This predicts waveform duration, not inference time, intelligibility, emotional delivery, or lip synchronization.

`core/pipeline.py` checks every cue before generating speech when the provider preserves native delivery, supplies a duration estimator, and the cast uses the selected cloned-user voice. A later overflowing cue therefore fails before earlier speech generation. Existing gap allowance and final-cue end constraints remain in effect. Other providers and per-actor conversion routes are excluded. Normal video processing still performs upstream separation/transcription before this TTS check; it does not eliminate their cost. Cancellation is checked between predicted cues.

`dev/verify_indicf5_app_video.py` additionally checks all characters and durations before separation for these staged, already-translated review inputs. The successful third render had already started before the duration-preflight addition, so it did not exercise this new prediction gate. Its unchanged synthesis was independently checked afterward.

Prediction evidence: `docs/validation/2026-10-08-native-duration-preflight.json`. Both previously generated opening comparisons match their predictions exactly. All 14 adapted cues predict a fit. Cue 11 has the tightest long-cue margin: 21.229333 seconds of generated speech in a 21.340000-second available window, including the allowed gap to the next cue. This numerical fit does not prove that individual words align with the source images.

`dev/verify_full_video_native_duration.py` compares all 14 published waveforms with predictions, checks each cue's hash against its worker receipt, and rehashes both the output video and unchanged source. It completed successfully; every native duration matches within one audio sample and fits its window. Evidence: `docs/validation/2026-10-08-full-video-native-duration-verified.json`.

Regression validation after the duration change: **113 tests passed in 99.571 seconds** across `dev.test_indicf5_integration`, `dev.test_indicf5_controls`, `dev.test_speech_integrity`, and `dev.test_output_integrity`. Three new cases check later-cue rejection before any simulated synthesis, gap allowance/final-cue constraints plus actor-route exclusion, and invalid prepared-reference rejection before worker selection. Evidence: `docs/validation/2026-10-08-indicf5-native-preflight-tests.log`. The embedded portable interpreter ignores ordinary PYTHONPATH settings, so the successful invocation inserted the project/core paths explicitly; earlier discovery-only attempts could not import `dev`. TEMP/TMP remained inside the workspace for Windows registry publication tests. Targeted whitespace checks passed. These tests do not substitute for human listening or a fresh automatic ASR/MT render.

### Completed full-video review artifact

Successful receipt: `docs/validation/2026-10-08-spoken-hindi-full-video-887151ac.json`.

Video: `docs/validation/2026-10-08-spoken-hindi-full-video-887151ac/outputs/source_DUBBED_HI_ff6628498abc/source_DUBBED_HI_ff6628498abc.mp4`.

- Full source duration: 122.531701 seconds. Output audio: 122.530000 seconds; video stream: 122.480000 seconds; subtitle stream: 122.531000 seconds. These are within the render's 150 ms source-duration tolerance.
- All 14 real IndicF5 cues completed; one GPU speech worker served all cues and was released.
- Real CPU separation, voice/background mixing, attached subtitles, and three stem exports completed. Background/original vocals span 122,532 ms; dubbed stem spans 122,530 ms.
- Complete video/audio decode passed, source hash is unchanged, and the temporary job workspace was removed after publication.
- Pipeline reported 11 minutes 39 seconds; receipt elapsed time, including surrounding verification/publication, was 730.75 seconds.
- Output SHA256: `4335ea70518ab74318fc791fd2c9ca4f3ef8b6451437227fdb3659e28e4ab849`.

This artifact uses **edited spoken Hindi**, with the first eight lines drawn from prior accepted editorial wording and six new adaptations. It is not a demonstration of unedited IndicTrans2 translation. Live ASR and automatic translation resolution inside the normal app were not exercised by this staged render. Persistent model selections/settings were not changed. No new packages or models were added during this full-video iteration.

`human_quality_accepted` and `separation_quality_verified` remain false. Listening review must assess naturalness, stutters/distortion, the new Hindi adaptations, source-dialogue leakage, synchronization, and the retained/transliterated closing joke. The attached Hindi subtitles are still incorrectly tagged `eng`; this remains an open metadata defect. Automated completion does not establish release readiness.

## Download housekeeping

The successful 4,462,265,272-byte model was rehashed against the pinned remote SHA256. Only after this replacement verification was the named interrupted 3,221,225,472-byte Xet transfer removed. The earlier nonzero partial was preserved until then. Receipt: `docs/validation/2026-10-08-indictrans2-verified-replacement-cleanup.json`. The verified model, voice models/references, source video and accepted renders remain present.
