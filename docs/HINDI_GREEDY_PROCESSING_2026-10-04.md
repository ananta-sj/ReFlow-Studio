# Processing gate on accepted greedy Hindi speech

The user answered “yes” to both two-sentence raw montages being entirely Hindi,
free of distortion/stutters and natural. Greedy-coverage receipt records acceptance
of those exact four gain-only takes. Prior Abhishek negation acceptance remains
separate. Earlier rejected sampled takes and approved raw files are preserved.

## Follow-up

`dev/verify_greedy_hindi_processing.py` reuses the four exact decoder waveforms,
verified against saved hashes. No inference/reference/text/seed changes. Applies
existing measured loudness normalization then the production RubberBand1.342/
pitch1 helper with its gain-only peak protection. No extra AudioEngineer mastering
compressor/EQ, gate, fade or word cut. Loudness normalization itself includes
dynamic limiting; this does not claim there is no dynamics processing anywhere.

This tests the two stages together. Intermediate normalized WAVs remain for
isolation if needed. Each review has the question then meeting-time utterance
with900ms silence between them. No source-video timing or background mixing.

## Results

| Voice | Passage | Native raw seconds | Final seconds | LUFS | True peak dB |
| --- | --- | --- | --- | --- | --- |
| Sujata | Question | 5.985 | 4.460 | −17.84 | −1.89 |
| Sujata | Meeting | 7.425 | 5.533 | −17.34 | −1.55 |
| Abhishek | Question | 4.129 | 3.076 | −16.37 | −2.18 |
| Abhishek | Meeting | 5.707 | 4.253 | −16.91 | −2.02 |

Four mechanical timing/peak checks pass, ten intermediate/final/review WAVs
decode, workspace removed. Durations within100ms of raw/1.342. Duration does
not certify naturalness or complete words. Levels/dynamics differ; no perfect
match claimed or extra post-tempo normalization/compression to force uniformity.

Receipt/log `validation/2026-10-04-greedy-processed.json` / `.log`;
folder `validation/2026-10-04-greedy-processed-d2a35976/`. Processed listening
pending; raw approval is not transferred automatically. Runtime sampling and
mastering defaults still differ, so promotion and actual-pipeline validation
remain necessary. No production/new package/model/download/commit/push/release.
Prior490 backend checks retained without rerun for diagnostics. Full-video,
cue fit, semantics and other release gates remain open.

## Subsequent acceptance and promotion

User answers “yes” to both processed montages remaining natural/clear without
distortion/stutters. Exact four-take processed acceptance recorded. Production
integration and fresh/retained verification are documented in
`HINDI_QUALITY_PRODUCTION_2026-10-04.md`; earlier pending/default-gap statements
above describe the pre-promotion point in this chronological iteration.
