# Question intonation with following context — 9 October 2026

## Reason for the test

The user reported slightly better clarity with the 0.9/1.1-second question takes, but still unnatural delivery. Neither was accepted. The next hypothesis is phrase context, rather than another duration increase.

Inspection confirmed that both the provider estimator and speech worker split text at Hindi sentence punctuation, question marks and exclamation marks. Consequently a question remains a separate model generation even when followed by a contextual sentence in the original input. This does not prove that splitting caused the unnatural voice, but it makes ordinary multi-sentence input an ineffective test of joint question prosody.

## Implementation

`core/indicf5_duration.py::segment_text` now shares the existing segmentation logic between estimator and worker. Its default preserves the previous sentence list. An explicit boolean `continuous_utterance=True` retains the entire validated text as one model utterance, including question punctuation. Invalid flag types, blank/invalid text, excessive text length and changed segmentation are rejected.

The IndicF5 provider exposes this as a keyword-only per-request option, passes it through owned-job recursion and sends it only when explicitly enabled. Estimation uses the same mode as generation. The worker re-evaluates the option for each call, checks the existing vocabulary/reference/model limits and records the selected mode. Existing output staging, cancellation, gain preparation, profile verification and isolated runtime remain in place.

The installed F5 `infer_batch_process` consumes the supplied text batches directly, so this request genuinely sends one question-plus-context batch to the model. It does not rely on a wrapper that splits the question again internally.

Normal app defaults and UI remain unchanged. This is an opt-in diagnostic capability, not an automatic naturalness fix or a new framework. No package, model, runtime or reference audio was installed or replaced.

## Controlled live trial

Text: **“ऊब गए? जगाने को ये एनिमेटेड चार्ट।”**

The wording is exactly the original question plus the accepted chart line. The baseline control is assembled from the original question PCM, its existing 200 ms sentence gap and the accepted chart phrase PCM. The control is **2.6533 seconds** long.

The continuous request retains that total duration budget through the explicit generation-time floor, rounded to the next model hop. It generates **2.656 seconds** in one model utterance, within one 256-sample hop of the control. It therefore does not test a slower total passage or a wording change; it tests joint generation, model-generated internal phrasing and shared utterance-level gain preparation instead of separate questions and a fixed inserted gap. Those differences can affect both prosody and levels, so no single acoustic cause is asserted in advance.

The voice profile, reference, seed, guidance and synthesis steps are unchanged. The candidate is fresh speech, not a stitched or stretched version of the accepted recording. The following chart line is included for context in this audio-only trial; the accepted chart waveform and video are not replaced.

The same live worker then generated the default isolated question with no continuous option or floor. Its PCM matched the old default question byte-for-byte, confirming that opt-in controls are not sticky and default synthesis remains reproducible.

## Verification

- `docs/validation/2026-10-09-question-context-tests.log`: **102 tests passed** in 53.999 seconds across duration/context validation, IndicF5 integration, speech integrity and cue review.
- `docs/validation/2026-10-09-context-default-duration-regression.json`: all **14 prior default duration predictions** remain unchanged within one 24 kHz sample.
- Actual model result contains exactly one utterance with the complete supplied question-plus-chart text.
- Predicted and actual candidate duration agree; total candidate/control duration differs by less than one model hop.
- Default question PCM regression, full listening-WAV decode, worker release and temporary workspace cleanup passed.
- Original voice profile, accepted video and all three accepted phrase WAV hashes remain unchanged.

Receipt: `docs/validation/2026-10-09-question-context-cba76d9e.json`.

Listening sample: `docs/validation/2026-10-09-question-context-cba76d9e/QUESTION_WITH_CONTEXT_LISTEN.wav`.

The listening file adds 250 ms before and 400 ms after the candidate for audition. This padding has not been applied to a video timeline. The control and default-regression WAVs remain alongside it for reproducibility, but the already-rejected default question is not presented as another candidate.

## Human audio review and video integration

The user answered **“yes”** to “Does the opening sound more natural now?” This accepts the opening audio's naturalness for this trial. The response and listening-file SHA-256 are recorded in `docs/validation/2026-10-09-question-context-user-feedback.json`. It does not establish synchronization or full-video acceptance.

The accepted raw joint question/chart waveform has now been placed in an **11.160-second** review video covering source time **88.000–99.160 seconds**. The listening file's leading/trailing audition padding is excluded. The prior interview tail from 88–90 seconds is retained. The joint utterance starts at **90.000**, ends at **92.656**, and is followed by the existing family take at **93.600–95.403** and lighthouse take at **96.640–99.147**. Both later takes retain their exact waveforms and positions. The old separate chart file remains preserved, but this comparison uses the newly accepted joint generation for question and chart.

Assembly reused the previously separated background and existing mix behavior. No new speech, source separation, package installation or model download was performed. The source and prior review/three phrase files retain their hashes. Full output decoding passed, video/audio streams are present, duration is 11.160 seconds, and the owned temporary workspace was removed.

Reproduction script: `dev/assemble_accepted_question_context_video.py`.

Render receipt: `docs/validation/2026-10-09-accepted-intro-video-b971e66b.json`.

Video: `docs/validation/2026-10-09-accepted-intro-video-b971e66b/ACCEPTED_INTRO_SHOT_REVIEW.mp4`.

Video SHA-256: `dc8cf56987ca0f633084c6e6fd8468fc78e501f57072cfd9bc377a2b0726d101`.

Human review of the opening's delivery in context and phrase-to-shot synchronization is pending. This remains a short diagnostic render; production defaults and the full video are unchanged. Structural checks cannot establish naturalness or matching visual intent, and no release approval is implied.

## In-video feedback and longer native trial

The user subsequently reported: **“ऊब गए? appears and goes instantly... i had to rewind just to hear it”** for the short video. Therefore the prior standalone naturalness response is retained as historical evidence, but the opening is **not accepted for video use**. The hash-bound feedback is recorded in `docs/validation/2026-10-09-intro-video-user-feedback.json`. No successful intelligibility or synchronization claim follows from the earlier “yes.”

The next controlled trial keeps the same Hindi wording, joint utterance, voice reference, seed, guidance and synthesis steps, but supplies a **3.2-second native generation budget** instead of 2.656 seconds. This increases available generated time by about 20.5%; it does not apply post-generation stretching or claim that the question alone receives that increase. The experiment checks whether joint pacing improves audibility. The following family take still starts at 93.600 seconds, so the maximum allowed diagnostic budget is 3.5 seconds and the assembled passage must finish before that take. Family and lighthouse waveforms and positions remain protected.

`dev/verify_question_context.py` now accepts an optional explicit `--budget`; its no-argument control is unchanged. `dev/assemble_accepted_question_context_video.py` accepts `--candidate-context` to render a completed experimental receipt without implying prior human approval. Candidate receipts mark opening audio acceptance false. Both scripts still validate assets, preserve prior outputs, fully decode their media, release workers and clean owned workspaces. These are evaluation-script options; no production speech defaults, UI, frameworks or packages change.

The live trial completed at exactly **3.200 seconds / 76,800 frames at 24 kHz**, agreeing with estimation. It is one generated utterance with the same text. The subsequent default question remained byte-identical to the historical default, and the profile and protected three-shot artifacts remained unchanged. Worker release, listening WAV decode and temporary workspace cleanup passed. Speech receipt: `docs/validation/2026-10-09-question-context-96ddf6e4.json`; generation log: `docs/validation/2026-10-09-question-context-3p2.log`. Raw generated WAV SHA-256: `0b0bd18701d8f5e451d80b36bd604fd200573512188042ffa93d1ef7e03f7f33`.

The new preview places this raw take at **90.000–93.200 seconds**, leaving **400 ms** before the unchanged family take. Family remains at 93.600–95.403 and lighthouse at 96.640–99.147. Render receipt: `docs/validation/2026-10-09-accepted-intro-video-7e9e6ffd.json`; assembly log: `docs/validation/2026-10-09-question-context-3p2-video.log`. The folder's historical `accepted-intro-video` prefix identifies the assembler; the new receipt explicitly marks opening audio and video human acceptance **false**. The filename does not confer approval.

This comparison tests native joint pacing, not isolated question-duration control. Until the user reviews it, intelligibility, naturalness and phrase-to-shot synchronization remain unverified. The previous preview and all original media remain available.

## 3.2-second review: question rejected, remainder accepted

The user reported **“well ऊब गए? feels unnatural rest everything is so good”**. Record: `docs/validation/2026-10-09-intro-3p2-user-feedback.json`, bound to video SHA-256 `40ee3e82bf0b2c0ff7336a5f98de43beefd017f7a1230a7fdf1551bd59a38c61`. This accepts the remaining short passage while rejecting the opening question's naturalness. The additional native duration therefore did not resolve the question delivery. No full-video or release acceptance follows.

The next hypothesis is conversational wording: **“बोर हो गए?”** instead of **“ऊब गए?”**. Both ask whether the viewer is bored, but the colloquial loanword changes diction and phonetics. This is an editorial experiment, not evidence that the original Hindi phrase is wrong. The new request retains the following chart text and the 3.2-second native budget, with the same voice profile, seed, guidance and steps. It does not increase duration again or install anything. The evaluator's optional `--question` records the changed wording rather than claiming a matched-wording control; its default is unchanged.

The candidate is for standalone audio review only. The newly generated chart context must not replace the accepted chart delivery without further review. The 3.2-second video, family/lighthouse takes and all prior media remain preserved. If the question is accepted, its actual phrase boundary and available shot window must be checked before isolating/integrating it; a model generation with context does not itself provide an accurate question boundary.

The live conversational-wording candidate completed successfully at **3.200 seconds**, with one generated utterance. Speech receipt: `docs/validation/2026-10-09-question-context-555a3e23.json`; log: `docs/validation/2026-10-09-conversational-question.log`. Listening file: `docs/validation/2026-10-09-question-context-555a3e23/QUESTION_WITH_CONTEXT_LISTEN.wav`, SHA-256 `48b1f1db753a8262e18bcf34401add8489ca98e038580108aab7bacc6ff5f4f0`. Default isolated-question PCM regression, asset/profile preservation, full listening-file decode, worker release and workspace cleanup passed. A separate SHA-256 check confirmed that the latest reviewed 3.2-second video is still byte-identical. Human acceptance of this new wording/delivery is pending; it is not integrated into video.

## Conversational wording accepted; delivery still rejected

The next user response was **“yes but delivery is the issue not natural”**. Record: `docs/validation/2026-10-09-conversational-question-user-feedback.json`, bound to the conversational sample's listening hash. This accepts the wording as an option while rejecting delivery naturalness. It does not authorize treating the sample as a finished replacement.

The current provider/worker route exposes reference conditioning, generation seed, guidance, steps, segmentation and duration; it has no explicit emotion/style request. Gain preparation uses a uniform measured gain per utterance and does not add dynamic expression. The confirmed Abhishek reference transcript is declarative sports narration. Reference style is a possible limitation, not an established cause of the question failure. Historical guidance/steps/reference experiments from 6 October already exist, including rejected Abhishek longer takes, so none of those settings is presumed to guarantee naturalness here.

The next narrow test is a **seed-7 alternate reading**, retaining the conversational text, 3.2-second native budget, reference waveform/transcript, guidance 2.0 and 32 steps. It tests stochastic delivery variability rather than a specific emotional-control repair. `dev/verify_question_context.py --seed` writes a separate validated evaluation profile with the same resolved reference path; it never modifies the original profile. The evaluator then restores the original profile for the default-question PCM regression within the same worker session. The new seed is not a production recommendation or an automatic naturalness rule. No video or previously accepted speech is replaced, and no dependency is added.

The seed-7 candidate completed at **3.200 seconds**, exactly matching its duration estimate. Receipt: `docs/validation/2026-10-09-question-context-f38f4769.json`; log: `docs/validation/2026-10-09-question-delivery-seed7.log`. Listening WAV: `docs/validation/2026-10-09-question-context-f38f4769/QUESTION_WITH_CONTEXT_LISTEN.wav`, SHA-256 `1f08469c1ec1ba424ddf344388208c7652eb90d6393019002e2e09eda706150a`. Original-profile/default-question PCM regression, listening-file full decode, protected phrase/profile checks, worker release and cleanup passed. The reviewed 3.2-second video's SHA-256 was checked separately and still matches. The generated output differs from the seed-1234 candidate, but different samples are not evidence of improved expression. Naturalness remains pending human review, and this take is not integrated into video.

## Seed-7 question accepted; splice assessment

The user responded **“yes ok”** to the question about conversational delivery. `docs/validation/2026-10-09-question-seed7-user-feedback.json` records this as narrow approval of the alternate question delivery, bound to the listening file. It does not establish video synchronization, approval of a different chart rendition, or release readiness. The prior reviewed chart delivery remains the target to preserve.

`dev/inspect_question_boundaries.py` uses the already-installed, pinned offline Whisper recognizer to obtain diagnostic Hindi word timestamps for the accepted-question waveform and the reviewed-rest waveform. It also records 10 ms RMS spans below −38 dBFS lasting at least 30 ms, with input hashes. Word timestamps are not forced alignment, and low energy is not proof that a sound is dispensable. Both signals must support a phrase junction before any splice is attempted. If the new question cannot fit before the unchanged chart onset, the timing conflict must be reported rather than hidden by stretching, overlap or truncation.

The diagnostic completed using the pinned recognizer revision `41f01f3fe87f28c78e2fbf8b568835947dd65ed9`, without new downloads or packages. Results: `docs/validation/2026-10-09-question-splice-boundary.json`; log: `docs/validation/2026-10-09-question-splice-boundary.log`. The reviewed rest has a low-energy interval **0.850–1.590 seconds**; the accepted question has one at **0.760–1.340 seconds**. ASR places the accepted question's final word end at approximately **1.080 seconds**. It also assigns part of the next word to the pause, illustrating why ASR alone is insufficient. The reviewed chart's first word starts at approximately **1.480 seconds** by ASR. Its acoustic low-energy span ends at 1.590 seconds. These are diagnostic bounds, not exact phonetic alignment or human quality evidence.

`dev/splice_accepted_question.py` searches **1.170–1.230 seconds** within the shared pause for a minimal-amplitude join. It selected sample **28,814 at 24 kHz**, or **1.200583 seconds**, with a junction amplitude difference of **one PCM16 unit**. The question prefix is copied sample-for-sample from the accepted seed-7 take; the remainder from that point onward is copied sample-for-sample from the previously reviewed 3.2-second take. No overlap, fade, normalization or time stretch is applied to the splice. The complete 3.200-second output is verified after writing. This preserves the chart waveform at its original sample positions, including its following pause. Its actual phrasing still needs listening review after the edit.

Splice receipt: `docs/validation/2026-10-09-question-only-splice-53f89903.json`; script log: `docs/validation/2026-10-09-question-only-splice.log`. Spliced WAV SHA-256: `b1cf4076d4e21fb921c01547dd71a9dc0715a29a38874752d04763ae954cd4fc`.

The short review video now uses this spliced passage at **90.000–93.200 seconds**, with the same interview tail, family take at 93.600, lighthouse take at 96.640, source picture window and reused background. The existing mix is reapplied and AAC is re-encoded, so exact-sample preservation is asserted for the speech splice, not the compressed final video's complete audio stream. No new speech or separation is performed during this integration. Source/prior protected artifacts retain their hashes; all final media decodes, streams and 11.160-second duration checks pass, and the temporary render workspace is removed.

Render receipt: `docs/validation/2026-10-09-accepted-intro-video-d71ce40e.json`; assembly log: `docs/validation/2026-10-09-question-only-splice-video.log`. Video: `docs/validation/2026-10-09-accepted-intro-video-d71ce40e/ACCEPTED_INTRO_SHOT_REVIEW.mp4`; SHA-256 `d897e336ee7c5d954f5c5766d36ca3ad9205818c227279960a69b8dbc33a9734`. The receipt distinguishes this question-only splice from joint synthesis. Short-video human review is pending. Production defaults, full-video output and release status remain unchanged.

## Short-video approval and full-video transition check

The user then answered **“yep it's good”** to the question about natural opening delivery and matching shots. `docs/validation/2026-10-09-question-only-video-user-feedback.json` binds this approval to the short video's hash and source window **88.000–99.160 seconds**. This establishes human acceptance for that specific comparison, including the question splice. It does not establish acceptance of a new full-video render or release readiness.

Full-video integration requires rebuilding the following sentence placements: in the old composite cue, “रिपोर्ट ख़त्म होने को है।” began around 97.749 seconds, overlapping the newly accepted lighthouse take through 99.147. Pasting the short master over the old full master would either overlap speech or leave the tail of a partially overwritten sentence. Before integration, the existing offline recognizer is therefore inspecting source audio **99.160–119.500 seconds** for diagnostic ending-phrase anchors. The accepted short section and all old recordings remain preserved.
