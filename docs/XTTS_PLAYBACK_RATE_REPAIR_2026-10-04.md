# XTTS playback rate repair and duration controls

## Finding

The bundled XTTS configuration declares a conditioning/input rate of 22050 Hz
and decoder/output rate of 24000 Hz. The installed Coqui `TTS.api` local
checkpoint path uses `Synthesizer(tts_checkpoint=...)`. That constructor assigns
its WAV writer the conditioning `audio.sample_rate`, whereas its directory-load
branch uses `audio.output_sample_rate`. XTTS constructs its HiFi decoder with
`args.output_sample_rate`, and returns decoder waveform samples without converting
them to the conditioning rate. This application's local-checkpoint path therefore
wrote 24000-Hz samples into WAVs labeled 22050 Hz.

The retained failed-retry raw files confirm 22050-Hz headers. A native decoder
sample stream played at that lower rate lasts 24000/22050 = 1.088435 times as
long, and its pitch is multiplied by 22050/24000 = 0.91875. Correcting the header
shortens playback by 8.125% relative to the mislabeled duration; it is not a
pitch-preserving tempo adjustment. These are distinct from the previously repaired
FFmpeg tempo stage. The mismatch does not explain all generation-duration variation.

## Production change

After successful XTTS initialization, including GPU-to-CPU recovery,
`core/tts/tts_handler.py` sets the synthesizer writer's sample rate to the loaded
HiFi decoder's actual `output_sample_rate`. It validates a real integer rate in
8000–192000 Hz and fails clearly on an invalid engine contract. It reads the
loaded decoder rather than hardcoding the default 24000 Hz, preserving custom
decoder rates. No installed dependency or model configuration is edited.

The sampling temperature remains 0.75, generation speed 1.0, Hindi's existing
RubberBand tempo 1.342, and ordinary generation remains unseeded. Voice-reference
cleaning, mastering, cue bounds and word-cutting protection are unchanged.
Existing accepted WAVs remain byte-for-byte intact; they are not automatically
rewritten. New generated speech has a different native pitch/duration and needs
listening review. This repair is not a declaration of newly accepted voice quality.

## Why silence trimming is insufficient

FFmpeg silencedetect on the two failed raw retries, at −40 dB with a 0.15s minimum,
found terminal quiet of approximately 0.622s and 0.700s. The complete raw files
last 8.2322s and 7.82585s. Removing that terminal quiet alone cannot bring either
processed take into the 2.600s cue window. The threshold measures low signal,
not certified digital silence or word boundaries; no trimming was applied.
Installed Coqui also appends 10000 zero samples per synthesized sentence. That
is part of the retained source behavior, not the whole observed tail and not a
reason to delete internal pauses or silence by amplitude threshold.

## Diagnostic controls

`dev/diagnose_xtts_timing.py` uses the existing local model offline. It makes new
listening copies of the earlier Sujata/Abhishek raw samples by relabeling the
unchanged decoder PCM to 24000 Hz, then applies existing mastering and tempo.
It does not resample, retrain, resynthesize these comparison sentences, or modify
their preserved originals. The originals were generated at temperature0.90;
these copies therefore compare playback rate, not the production sampling setting.

Separately, it generates the same uncertain cue-2 Hindi text with seed7 and
production temperature0.75: cleaned reference, identical cleaned-reference repeat,
and the earlier unprocessed full Hindi reference. All three retain raw, mastered
and tempo-processed WAVs. Fixed seeds are diagnostic only, not a production fix.
The unprocessed reference also differs in preparation/sample rate and retained
edge silence; this control assesses that combined preparation difference, not
which particular cleaning operation caused an effect.

Receipts: `validation/2026-10-04-xtts-timing.json` and `.log`.

## Verification and limits

Three regressions cover an actual one-second 220-Hz decoder waveform saved with
the expected duration/pitch, a custom rate through GPU-to-CPU recovery, and invalid
decoder metadata failing before inference. The focused speech/integrity/parallel/
language checks passed81 tests in73.209s. An initial command could not discover
`dev` under portable Python's isolated import path; rerun explicitly added the
workspace/core paths, and the original import-failure log is retained.

The complete backend suite passed490 tests in124.375s. Its log is
`validation/2026-10-04-xtts-sample-rate-backend.log`. Frontend code is unchanged;
the earlier83 checks/build are retained, not rerun. The owned portable QA copy
was refreshed:168 application files, no size mismatches. No new desktop listening
or visual acceptance is implied by that copy check.

### Completed real-engine controls

The loaded decoder and writer both report24000 Hz. The diagnostic completed in
232.766s; model diagnostics and the test suite overlapped, so elapsed times are
not an isolated CPU performance benchmark. Cleaned-reference seed7 synthesis
returned5.291s raw /3.943s processed. The seeded repeat produced exactly the same
raw WAV SHA-256 and duration. The unprocessed-reference seed7 control was6.635s
raw /4.944s processed. None fits2.600s. Dropping reference preparation therefore
did not solve this cue's timing in this control; this does not certify the
cleaned reference's subjective quality or general superiority.

The two long retained native-reference examples shortened from9.393 to8.630s raw
(Sujata) and7.327 to6.731s raw (Abhishek) after correcting their header. Both
retain identical decoder PCM. The first diagnostic applies production mastering;
those clips are diagnostic controls rather than reproductions of the previously
accepted loudness-only mastering choice.

### Listening comparison with the accepted processing stages

`dev/compare_native_playback_rate.py` additionally prepares corrected-rate copies
using the same loudness-only normalization and RubberBand1.342 stages as the
earlier accepted takes, with no added EQ/compression or new inference. Existing
approved takes are copied into the new comparison folder, never overwritten.
Raw sample hashes match the earlier native-reference receipt. These are the
clips presented for listening:

| Voice | Earlier accepted file | Correct native-rate file | Measured LUFS, earlier/native | True peak dB, earlier/native |
| --- | --- | --- | --- | --- |
| Sujata | 6.999s | 6.431s | −16.62 /−16.57 | −1.55 /−1.55 |
| Abhishek | 5.460s | 5.016s | −16.32 /−16.39 | −1.59 /−2.09 |

Integrated loudness is close but the comparisons are not perfectly matched in
all peak/dynamic measurements. Pitch increases to its actual native value;
the earlier user-approved tempo multiplier remains unchanged. Receipt
`validation/2026-10-04-native-playback.json`; comparison folder
`validation/2026-10-04-native-playback-86e10019/`. All19 WAVs across both new
diagnostic folders decode successfully. Owned temporary workspaces were removed.

Neither sample-rate tests nor seeded repeatability establish source transcription
accuracy, natural Hindi delivery, fitting every cue, A/V synchronization or
successful final video assembly. No new package/framework/model/download, commit,
push or release. The real-video baseline remains failed until a complete new run
and human quality review provide contrary evidence.

### Subsequent listening feedback

The user described the corrected voices as “beautiful” and reported a little
echo in Sujata. This supports the playback-rate direction while leaving that
artifact unresolved. See `SUJATA_ECHO_REVIEW_2026-10-04.md`: shorter-window tempo
produced byte-identical audio, and matched-level raw/normalized controls await
listening. No speculative echo filter or global quality acceptance was applied.
