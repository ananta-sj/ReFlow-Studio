# IndicF5 integration review — October 6, 2026

This is a code review and implementation checklist while user-voice evaluation
runs. No production integration is implemented or implied by this document.
The official-reference Hindi sentence has passed listening; the confirmed
Sujata/Abhishek excerpts are original recordings, not accepted synthesized
voices. Their generated versions still require listening.

## Findings that matter for integration

| Area | Current behavior | Required treatment before an IndicF5 video test |
| --- | --- | --- |
| Runtime | `core/optional_runtime.py` recognizes vision, f5 and musetalk; evaluation uses a separate IndicF5 profile | Explicit isolated engine identity and readiness checks; do not replace generic F5 imports |
| Checkpoint contract | `core/model_contract.py` uses `F5TTS_v1_Base` and English/Chinese for the generic F5 adapter | Distinct IndicF5 architecture, vocabulary and checkpoint namespace loading; do not relabel the existing recipe |
| Voice selection | `CLONED_USER` is excluded from `actor_uses_f5` and uses the selected TTS provider | An explicit selectable IndicF5 speech route must work with user references without silently falling through to XTTS |
| Reference handling | Pipeline prefers `clean_ref_wav`; provider interfaces do not carry confirmed reference text | Carry the exact chosen audio, transcript and hash together; regeneration/cleaning/trimming must not silently invalidate this pair |
| Mastering | Gain-focused Hindi handling currently applies to cloned-user branch; other branches receive additional mastering | Evaluate and preserve the candidate's accepted processing; do not automatically add the earlier compressor/EQ overlay |
| Timing | `_dub_segment` applies 1.342 tempo to every Hindi target | The tempo was accepted for earlier XTTS takes; native-speed IndicF5 has different delivery. Separate engine-specific delivery settings from cue-fit limits |
| ASR | Generic F5 reference helper uses Transformers pipeline and upstream reference preprocessing | Exact confirmed reference text should bypass ASR. Evaluation encountered optional-codec loading failure; automatic reference handling needs its own execution and matching checks |
| Worker reuse | Existing job-scoped F5 sessions reuse a loaded model and cache transcripts | Preserve reuse and cancellation for IndicF5 while keeping runtime/recipe/reference identities distinct |
| Performance | First official-reference test took 695.515 seconds overall on CPU | Do not reuse an XTTS speed estimate. Measure shorter-reference and repeated-cue behavior; limit heavy concurrent inference |

## Evidence and caveats

The evaluation loader accounted for all 447 checkpoint tensors, loading 364
speech-model and 83 vocoder tensors strictly. That behavior belongs to the
IndicF5 checkpoint, whose known compilation namespace prefixes differ from the
generic recipe. The same checkpoint cannot be assumed compatible simply
because both packages export `f5_tts`.

The confirmed reference excerpts are 6.600 and 5.730 seconds, instead of the
full 17.528 and 19.775-second recordings. Sample equality and full decoding
passed. Their shortening is reference preparation, not a tempo adjustment to
generated speech. Whether this improves inference speed must be measured.

Hindi character-vocabulary inclusion does not establish pronunciation or
intelligibility. Language preflight must represent the chosen engine's actual
supported routes and reject unsupported ones; advertised model languages still
need separate product acceptance tests. The current test covers Hindi only.

## Implementation sequence after candidate listening

1. Obtain listening acceptance for the actual generated Sujata and Abhishek
   controls, then varied text and longer Hindi passages.
2. Introduce an explicit engine/asset/runtime contract with the tested loading
   path and verified reference-pair metadata. Keep model access/downloads out
   of cue inference once assets are available locally.
3. Carry the selected speech route through preflight, job-scoped worker reuse,
   cancellation, reference preparation and staged audio publication.
4. Make delivery and mastering policy depend on the accepted engine settings;
   retain the guard that refuses to cut audible words to fit a cue.
5. Calibrate CPU estimates with real measured inference, and exercise failure,
   cancellation, offline operation and portable path handling.
6. Run a new complete video test with reviewed recognition and translation,
   native-rate speech, timing, subtitles, background preservation and human
   final listening. Retain historical failures as distinct evidence.

Relevant code: `core/pipeline.py`, `core/speech_language.py`,
`core/providers/resolve.py`, `core/providers/voice/f5tts_local.py`,
`core/model_contract.py`, `core/optional_runtime.py`, `core/feature_worker.py`
and `core/feature_session.py`.
