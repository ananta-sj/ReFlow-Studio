# Hindi voice coverage after accepted Sujata reference control

## Acceptance and production distinction

The user accepted the6.049s cleaned-reference Sujata take with “beautiful”.
`validation/2026-10-04-hindi-accepted-examples.json` records exact asset hashes,
settings and listening scope alongside the previously accepted native Abhishek
example. Sujata's experiment receipt now records acceptance. New takes do not
inherit acceptance just because their settings match. No all-text/video guarantee.

These diagnostic examples use temperature0.90, seed1234, native24000-Hz output,
loudness-only normalization and RubberBand1.342/pitch1. Sujata uses the cleaned
17.528s reference; Abhishek uses his full unprocessed reference. The normal app
still uses temperature0.75, unseeded sampling and additional voice mastering.
No diagnostic profile is silently promoted to runtime defaults. Cue fit and
source/translation correctness remain separate unresolved gates.

## Varied-text test

`dev/verify_hindi_voice_coverage.py` loads the existing CPU model once and generates
three passages per voice, sequentially with two OpenMP threads:

| Order | Hindi | Intended meaning / focus |
| --- | --- | --- |
| 1 | क्या आप मेरी आवाज़ साफ़ सुन पा रहे हैं? | Can you hear my voice clearly? Question intonation and opening consonants. |
| 2 | यह रिपोर्ट अभी पूरी नहीं हुई है। | This report is not finished yet. Preserve “नहीं” and a clear ending. |
| 3 | कल सुबह दस बजे बैठक शुरू होगी, इसलिए कृपया समय पर पहुँचें। | Meeting tomorrow morning at ten; arrive on time. Spoken time, longer clause and pause. |

These are authored diagnostic sentences, not translations of a video. Sampling,
reference and processing are fixed per voice. No rewritten punctuation or tempo
increase to force fit. One fixed seed tests text coverage, not arbitrary-sampling
reliability. No real subtitle window is imposed or certified to fit.

Each raw/normalized/final WAV is retained. Gain-only comparison targets−16.5LUFS
subject to peak headroom; achieved levels are recorded, not assumed matched.
No added EQ/compression, gate, fade or word cut. Each review WAV joins three full
takes with900ms digital-silence separators. These are listening aids, not source
cue timing or a full-video mix. Individual takes remain separately inspectable.

## Verification and evidence

Retained reference hashes verified before/after. Generated speech must decode
with nonzero signal, mono24000-Hz format, finite loudness and existing peak
tolerance. Final duration within100ms of raw duration/1.342. Full FFmpeg decode
checks cover raw/normalized/final and review WAVs. Text, hashes, actual times,
loudness, synthesis time and real-time factor recorded per take.

Receipt/log: `validation/2026-10-04-hindi-coverage.json` / `.log`.
Completion results are appended below. Mechanical checks are separate from human
word accuracy, naturalness and listening acceptance. No recognition/waveform
metric is treated as proof that time, negation and all words are preserved.

Only diagnostic code, acceptance records, media and docs changed. No production
settings/model/new package/framework/download. Prior490 backend checks retained,
not rerun for diagnostics. Accepted/source files preserved. Full-video, cue-fit,
source semantics, optional-engine and platform gates remain open. No commit,
push or release.

## Completed batch

Elapsed204.703s; model load14.969s once; six synthesis calls totaled174.092s.
All six completed, mechanical checks passed, owned workspace removed. The20
generated raw/normalized/final/review WAVs received full decode checks. Reference
hashes still match. No automatic human acceptance, semantic certification or
subtitle-fit inference is recorded.

| Voice | Passage | Raw seconds | Final seconds | Synthesis seconds | Final LUFS | True peak dB |
| --- | --- | --- | --- | --- | --- | --- |
| Sujata | Question | 5.611 | 4.181 | 20.593 | −16.85 | −1.55 |
| Sujata | Negation | 5.153 | 3.840 | 21.703 | −16.50 | −2.57 |
| Sujata | Time/pause | 7.094 | 5.286 | 36.484 | −17.68 | −1.55 |
| Abhishek | Question | 5.195 | 3.871 | 34.938 | −16.55 | −1.55 |
| Abhishek | Negation | 8.214 | 6.121 | 38.687 | −16.50 | −2.02 |
| Abhishek | Time/pause | 5.889 | 4.388 | 21.687 | −16.51 | −1.84 |

Review folder `validation/2026-10-04-hindi-coverage-509b2ff0/`.
Sujata review15.107s, Abhishek16.180s including two900ms separators each.
Levels are not perfectly matched: Sujata's time/pause take is1.18LU below the
target because true-peak safety takes priority. No extra compression was added
to force loudness. Duration checks establish the chosen tempo operation, not
natural delivery or complete word preservation.

Abhishek's short negation take is6.121s, longer than his4.388s longer sentence
and Sujata's3.840s rendering of the same negation. This is a listening-review
flag, not proof of hallucination, silence, repeated words or defective speech.
Do not trim, automatically accelerate, discard or mark the take accepted to
hide that observation. CPU cost is for this specific batch and warm local
environment, not a portable-system performance guarantee or proof of GPU speed.

## Next decision

Listen to both review WAVs for clear opening words, preserved “नहीं” and ten
o'clock, natural endings/pause and especially the long Abhishek second take.
Only then choose which settings/takes should enter a concrete production
quality profile. The application must be tested using that actual profile rather
than treating these standalone diagnostics as default-runtime quality evidence.
The existing real-video baseline still fails; no new accepted final video.

## Subsequent listening rejection

The user reports distortion and stutters in both presented voices. The batch is
rejected and neither diagnostic profile is promoted. Mechanical success above
does not imply speech quality. Exact raw negation controls now isolate synthesis
from output processing; see `HINDI_COVERAGE_REJECTION_2026-10-04.md`. Earlier
individually accepted clips remain preserved and accepted within their own scope.
