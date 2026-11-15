# Hindi varied-text rejection and raw-stage controls

## Decision

User feedback on both three-sentence review montages:
“both voices have some distortion and stutters”. The varied-text listening batch
is rejected, despite successful file/timing/peak checks. Neither profile is ready
to be promoted as reliable production quality. This does not revoke acceptance
of the specific earlier clips; those exact files and their hash ledger remain.
No claim that all six individual sentences have the same failure, or that a
particular stage caused it, follows from this montage-level report.

`validation/2026-10-04-hindi-coverage.json` records batch rejection, feedback and
scope. The copied case-report inside the original evidence folder remains the
pre-listening execution snapshot; the top-level receipt contains the later
listening decision. Preserve rejected audio as failure evidence, not successful
quality examples.

## Raw-stage isolation

`dev/isolate_hindi_coverage_artifacts.py` prepares the exact raw negation take
for each voice: “यह रिपोर्ट अभी पूरी नहीं हुई है।” The phrase was the longest
Abhishek anomaly and is directly comparable across voices. Raw SHA-256 must
match the rejected batch's saved synthesis. No new inference, changed random
seed, altered text or reference, EQ, compression, loudness normalization,
tempo processing, pitch change, fade, gate or word cutting. Gain-only comparison
attenuation is applied while keeping the complete native24000-Hz mono waveform.

| Voice | Native raw duration | Final control LUFS | True peak dB | Comparison gain |
| --- | --- | --- | --- | --- |
| Sujata | 5.153s | −18.47 | −1.55 | −1.61dB |
| Abhishek | 8.214s | −17.99 | −2.68 | −2.77dB |

Controls deliberately lack the1.342 tempo operation and therefore sound slower
than the rejected processed takes. This is a stage test, not a new pace choice.
Integrated levels differ0.48LU because gain is constrained by peak headroom;
not a perfect loudness/peak/dynamics match. Native format, full decode, exact
unchanged duration, source hashes and measured peak tolerance pass. Owned
temporary workspace removed.

Receipt/log `validation/2026-10-04-hindi-raw-controls.json` / `.log`;
folder `validation/2026-10-04-hindi-raw-controls-8cc1a42c/`.

## Sampling-path inspection

Installed XTTS synthesize builds sampling settings from checkpoint config and
updates them with explicit call kwargs. The rejected diagnostic used explicit
temperature0.90, while inherited config remains length_penalty1.0,
repetition_penalty5.0, top_k50 and top_p0.85; inference defaults to do_sample=True.
These values reach autoregressive GPT generation. Repeated seed1234 makes the
same setup reproducible; it does not prevent poor generations on new text.
No repetition penalty, temperature or sampling mode is changed in response to
this rejection before establishing whether these exact raw takes also fail.
The installed inference function's repetition_penalty default10.0 is superseded
by the loaded config5.0; simply reading the function signature would misreport
the actual route. The generation defaults are not themselves a demonstrated bug.

## Required next evidence

Listen to the two exact raw controls. Distortion/stutters already in raw would
direct investigation toward synthesis/conditioning/sampling; raw clean but
processed affected would direct investigation toward loudness/tempo processing.
Those are conditional directions, not proven causes or a certified fix. Earlier
Sujata opening distortion was heard in raw on a different passage; that does
not establish the source of all new batch artifacts.

No expensive six-take parameter sweep, speculative cleanup filter or production
promotion is used to substitute for this distinction. No production/new package/
model/download changes. Previous490 backend checks retained, not rerun for
diagnostic-only code/media. Full-video, cue fitting and semantic acceptance
remain open; release remains not ready. No commit, push or release.

## Subsequent raw listening result

The user reports another-language opening followed by Hindi in the exact
Abhishek raw control. That utterance's failure exists before output processing.
Raw routing explicitly selected Hindi; no UI/STT language selection participated.
No new Sujata raw verdict was supplied. See `HINDI_LANGUAGE_DRIFT_2026-10-04.md`
for one bounded greedy-decoding control, without a silent production promotion
or a guessed identification of the other language.
