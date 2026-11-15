# Overnight dub diagnosis — 14 November 2026

## Evidence from the failed batch

The exported episodes were not complete Hindi dubs. Episode 1 contained 363 source dialogue cues, but only eight were synthesized successfully. The remaining 355 cues retained original speech: 169 lacked a reliable character reference, 182 exceeded their timing windows and four needed translation review. Episode 2 had eight successful cues out of 380; episode 5 had 21 out of 337. This was a pipeline completion/quality-control defect, not evidence that CPU synthesis would sound better than CUDA.

Episode 1 logged 375 synthesis calls totaling 5,159.745 seconds, and 7,921.032 seconds across cue processing. Failed takes had a median generated/source duration ratio of 2.28. The short girl reference was only 2.492 seconds. Whole-scene speaker clusters mixed named characters, causing most uncertain references to be rejected.

## Changes and measured performance

- Runtime validation now happens once per job for speech and translation checkpoint keys. The old validation took approximately 5.8 seconds on repeated calls. A new job still validates independently, and code-change guards remain active.
- XTTS reuses conditioning within a model session when the reference and conditioning parameters are unchanged. Changed reference files invalidate the entry.
- CUDA XTTS uses scoped FP32 cuDNN settings. A controlled decoder test dropped from 123 seconds to 0.154 seconds warm, and 0.223 seconds in a fresh process. These are phase measurements, not an end-to-end episode speedup claim. FP16 was evaluated and rejected because it produced silence.
- Duration-bounded GPU synthesis rejects a take without an end-of-speech token before decoding/publishing unfinished audio. It permits an alternate take; it does not cut a word to meet the deadline.
- Missing character references are checked before translation and speech. Unresolved dialogue prevents final export and pauses the batch. Failed jobs expose review information without requiring a misleading completed video.
- Caption-level source embeddings and longer clean reference assemblies replace whole-scene cluster routing where labelled source captions are available. This remains under evaluation, not accepted as reliable character matching.

## Verification and limitations

All four actual CUDA stages passed the installed-runtime checks. The frontend production build passed. The focused regression suite initially passed 52 tests; the added translation validation-cache test also passed with its full 21-test suite.

The full-source identity evaluation only resolved 162 of 363 source cues and therefore failed the acceptance requirement. The raw embedding test accepted 11 held-out named cues, rejected 45 and made zero confident errors. The PLDA-coordinate comparison accepted 17 correctly, rejected 37 and confidently misassigned two. That alternative was rejected; production matching still uses raw vectors. Lowering thresholds solely to increase coverage is not a valid fix. Inspection of the source detector also showed a mother's short reply inside the daughter's continuous turn, so continuous-turn reference fallback was not adopted.

The real bounded-synthesis check rejected an unfinished take without creating the requested output file. The same model session then completed a 4.267-second alternate take in 7.313 seconds. Its first call, including model startup and the rejection, took 101.328 seconds. This validates rejection and recovery, not the naturalness of that speech. The focused delivery/review suite passed 103 tests; all ten repair tests passed after adding missing-readback protection. Missing verification rows cannot silently pass the export gate.

Natural Hindi delivery, faithful translation and reliable multi-character matching have **not** been established for a complete episode. Do not restart an unattended multi-episode batch on the basis of the runtime or unit checks alone.

## Output cleanup

Removed 10,086,441,593 bytes from the root `outputs` directory. Original episodes, installed models and active runtimes were preserved. Text-only batch evidence was saved under `docs/diagnostics/overnight-20261114-metadata`; the queue was paused and links to deleted exports were cleared. Historical diagnostic archives were not treated as current output files.

## Continued repair and scene acceptance result

The subsequent controlled test found a concrete source-embedding bug: zero-padding a cue to six seconds, even with a zero pooling mask on the padding, changed its voice vector drastically. Identical-audio cosine comparisons ranged from -0.147 to 0.321 instead of approximately one. The installed WeSpeaker model normalizes filterbanks before masked pooling. Caption embeddings now use exact-duration clips, independent of neighbouring batch members. The actual speaker-runtime verification was rerun successfully, including variable-duration cue extraction.

Named voice profiles now combine longer named samples instead of splitting one character's delivery styles into separate reference identities. Sub-1.5-second samples cannot build profiles. Generic SDH roles such as different children or guests remain separate, and inline caption handoffs cannot contaminate a single-character anchor. Unlabelled short replies use stricter matching. One bounded corroboration pass can use two already-confident nearby examples or a consistent multi-caption utterance; newly promoted assignments never recursively train more assignments.

The updated cached-real-source evaluation assigns 184 of 363 cues. In the fourteen-line mother/daughter scene, eleven are assigned and three remain explicitly uncertain. Holding out caption labels produces ten correct assignments, 45 rejections and zero wrong assignments. This is not sufficient coverage to declare full-episode character matching solved. These are routing results, not proof of completed synthesis or natural acting.

Two automatically selected, distinct character turns were then synthesized through the actual CUDA translation and pipeline speech/timing code, using freshly separated source references. The resulting audio lengths were 5.275 seconds in a 7.090-second cue and 5.249 seconds in a 5.255-second cue. Word-readback similarities were 0.891 and 0.986. The first speech call, including loading, took 152.125 seconds; the second took 15.266 seconds.

**The scene was rejected.** NLLB changed the daughter's statement about Father speaking before he died into a statement about the listener speaking before dying, and used masculine Hindi for her. The mother translation also lacked conversational context. Timing and readback success cannot establish meaning or naturalness. An installed M2M100 trial and an English-subtitle-to-NLLB trial also showed meaning or style errors, so neither was adopted as a replacement. Rejected auditions and their temporary source workspace were cleared; no accepted dub was published.

The final focused regression run passed 125 tests. The episode queue remains paused. An isolated context-aware text-model trial is described in `DIALOGUE_MODEL_EVALUATION_PROPOSAL_2026-11-14.md`; it requires user approval before any downloads. That proposal does not solve remaining voice assignments or guarantee emotional acting.
