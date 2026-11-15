# Controlled voice reference comparison — 4 October 2026

## Purpose and method

Investigate the retained short Hindi cue that overflows its 2.600-second slot.
Use existing offline CPU XTTS, unchanged production speech settings and approved
1.342× Hindi pace. No production defaults, models, dependencies or accepted takes
are modified. `dev/compare_review_reference.py` records the experiment.

All three runs use “मेरे पास यह रिपोर्ट है।”, seed 1234 (Python, NumPy and Torch),
temperature 0.75 and sentence splitting. Load one model instance, then compare
the saved full reference, a cleaned first-cue excerpt from the same source, and
a repeat of the short-reference case. Both references are hash-checked against
retained source assets before preparation. The excerpt is a candidate reference,
not a human-verified clean speaker sample. Raw, mastered and paced WAVs are kept.
Mastering uses existing compression/EQ/loudness processing; it is identical across
cases. No word trimming or extra acceleration is permitted.

The installed model config and XTTS implementation cap reference conditioning
at 30 seconds (`max_ref_len=30`, `gpt_cond_len=30`, chunk length 4). The saved
119.204-second file therefore does not establish that the model conditions on
119 seconds. This comparison changes the reference input, not those settings.

Timing and waveform equality can establish specific execution properties. They
cannot establish correct pronunciation, meaning, single-speaker identity or
naturalness. Fixed seeds are diagnostic controls here; they are not yet a
production reproducibility feature or a cross-platform determinism guarantee.

## Results

The machine-readable receipt is
`validation/2026-10-04-reference-comparison.json`; execution log is
`validation/2026-10-04-reference-comparison.log`. Results are recorded after the
three cases finish. No human quality acceptance is implied by successful execution.

Completed successfully in **200.937 seconds**; owned temporary workspace removed.
Outputs: `validation/2026-10-04-reference-comparison-6b96f62e/`.
Full reference is 119.204 seconds; prepared short reference is 6.640 seconds.

| Case | Raw length | Length at approved pace | Speech generation | Fits 2.600 s slot? |
| --- | --- | --- | --- | --- |
| Full reference | 9.242 s | 6.868 s | 72.563 s | No |
| Short reference | 5.655 s | 4.202 s | 34.531 s | No |
| Short reference repeated | 5.655 s | 4.202 s | 42.735 s | No |

Model loading took **39.031 seconds**, once for all cases. Per-case totals with
mastering/export were 75.766, 38.187 and 46.438 seconds. Imports/reference preparation
and publication/cleanup also contribute to the full elapsed time. A reused model
still needs 35–43 seconds to synthesize this short-reference line on this machine.
These measurements do not establish a production-wide speedup or a safe cache
memory budget.

Both short-reference runs have identical raw file hashes and processed PCM hashes.
This establishes repeatability for this text/reference/settings/runtime pair in
one process. It does not establish all-case, fresh-process or GPU determinism.
The full-versus-short duration difference is approximately 39% with the same seed
and pace. It is evidence that reference selection affects this output; it is not
proof of improved naturalness, verified speaker identity or general improvement.

## Next decision and preserved behavior

**Subsequent user listening result: both takes rejected.** Exact feedback:
“both are gibberish after first 2-3 words”. The shorter duration and identical
repeat hashes do not constitute intelligible speech or an improvement. Do not
promote either reference preparation route on this evidence. The receipt now
records this rejection; all original measurements and audio are preserved.
Follow-up controls use the reference from earlier approved Hindi samples,
alternate seeds, an English line and raw audio before mastering/pace adjustment.

Listen to `full.wav` and `short.wav`, especially “रिपोर्ट है”, pauses, speaker
identity and pronunciation. If the short reference sounds better, evaluate a
longer varied passage before changing automatic reference preparation. The source
cue's recognized English “Me has this report.” is suspect: even a good voice take
cannot establish that this Hindi translation preserves the actual meaning.

Both takes remain unaccepted and unsuitable for the existing 2.600-second slot.
Do not cut words or accelerate further to force a fit. Correct recognition and
translation, review the timing window, or choose another delivery as appropriate
after listening. Accepted renders, default seed behavior, Hindi pace and source
assets are unchanged. No model cache was added in this experiment.

Verification: all produced WAVs decode and contain signal; references match the
saved asset hashes; short repeat matches exactly; clean temporary cleanup; diff
whitespace check passes. No production code changed, so the prior 483 backend
checks and portable UI receipt are retained rather than rerun. This experiment
does not test visible audio controls, subtitles, video or translation semantics.
