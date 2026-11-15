# Accepted Hindi decoding and processing in production

## Evidence and decision

The user accepted the exact raw greedy Hindi question/meeting takes for both
Sujata and Abhishek as entirely Hindi, natural, free of distortion/stutters. The
user subsequently answered “yes” to the same takes after existing loudness-only
normalization and approved RubberBand1.342 pace. Both receipts record acceptance
with exact scope. The earlier sampled varied-text batch remains rejected.

Production now applies the accepted Hindi decoding and cloned-voice processing
route. This is evidence for these voices/passages, not a guarantee on all texts,
references, languages or platforms. No accepted/rejected artifact is overwritten.

## Changes

- `core/tts/tts_handler.py`: resolved Hindi (`hi`) uses do_sample=False and
  num_beams=1. All other languages keep the existing sampling route. Temperature
  remains0.75 in the call but is inactive in greedy decoding; inherited model
  penalties remain unchanged. No fixed random seed is introduced in production.
  Native output rate, explicit-reference authority, staged publication and
  cooperative generation cancellation remain in force.
- `core/pipeline.py`: cloned Hindi actor (`CLONED_USER`) uses existing measured
  `normalize_voice_loudness` instead of the extra AudioEngineer compressor/treble
  overlay. Normalization includes its existing dynamics/peak control. Other
  language/actor mastering routes retain their prior behavior. Hindi tempo1.342,
  word-cutting rejection and cue bounds stay enforced. This processing condition
  follows language/actor and can also apply to other selected TTS providers;
  deterministic decoding applies specifically to local XTTS.
- Three regressions: Hindi decoding/reference routing; English keeps sampling
  defaults; a cloned-Hindi normalization failure retains segment-stage context
  and cleans owned files. Existing cancellation/output preservation/tempo tests
  remain relevant.

No reference-name heuristics, model substitution, new framework/package/download,
speaker model retraining or arbitrary trimming. The current reference-preparation
step is unchanged. In particular, accepted Abhishek diagnostics used the unprocessed
reference; the automatic full pipeline cleans user references. That difference
still needs actual full-pipeline validation and is not hidden by these checks.

## Verification

Focused speech/generation-control checks:64 PASS21.494s,
`validation/2026-10-04-hindi-quality-focused.log`.

`dev/verify_production_hindi_quality.py` executes the actual `_dub_segment` path
with retained approved synthesis supplied by a controlled provider. All four
processed results are byte-for-byte PCM identical to approved listening outputs:
Sujata4.460/5.533s, Abhishek3.076/4.253s. This proves processing integration and
the normal guard in sufficiently spacious cues, not fresh generation or real
subtitle fitting. No inference; receipt `validation/2026-10-04-production-hindi.json`.

`dev/verify_live_hindi_quality.py` additionally exercises the real XTTS adapter,
TTSHandler and segment path on one fresh Sujata question with the exact prepared
reference. Checks fresh raw SHA and final PCM against approved controls. It
does not repeat user-reference cleaning, STT/translation/separation, full-video
mix/mux, real cue timing or desktop playback. Actual result recorded below.

Full backend and owned portable refresh results are recorded below on completion.
No frontend change; earlier83 checks/build retained. No release/commit/push.
The failed real-video baseline and semantic/timing/optional-engine/platform
release gates remain open until a new full workflow validates them.

## Completed production verification

- Complete backend493 PASS93.946s, `validation/2026-10-04-hindi-quality-backend.log`.
- Fresh actual XTTS adapter/handler/segment inference completed59.640s: raw WAV
  SHA matches the approved greedy Sujata question, final4.460s PCM matches the
  accepted processed take exactly. No production random seed was set. This is
  one CPU/reference case, not a cross-platform byte-reproducibility guarantee.
  Receipt `validation/2026-10-04-live-hindi.json`; raw/final retained in
  `validation/2026-10-04-live-hindi-7eee0ce3/`; workspace removed.
- Controlled-provider processing reproduces all four approved PCM takes exactly;
  folder `validation/2026-10-04-production-hindi-922db889/`; workspace removed.
- Owned portable QA application refreshed168 files, no size mismatches. Updated
  source copies checked by the existing refresh workflow. No new visible/audible
  desktop check, fresh-PC/offline-install acceptance or complete video run here.
- Whitespace checks pass. Frontend unchanged; previous83 checks/build retained.

Runtime decoding/processing gap for local cloned Hindi is now addressed. The
reference-preparation difference and full-video source/translation/cue-fit gates
remain explicit. The old44s video failure has not been reclassified as success;
it predates this repair and must be rerun or followed up under current behavior.
