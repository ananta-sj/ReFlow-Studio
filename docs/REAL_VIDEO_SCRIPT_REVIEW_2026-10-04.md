# Real-video script review and isolated cue retry

## Scope and status

This continues the failed 44-second Sample/2.mp4 baseline. It does not certify a
corrected transcript or publish an accepted video. The user's latest “ok” is an
acknowledgement, not confirmation of ambiguous source words. Existing media,
models, generation defaults, cue timings and user settings are preserved.

## Source recheck

The retained first-15-second word-timestamp recognition pass independently
reported “Me, has this report.” at 6.66–8.28s. Its first-word probability was
0.769. The full-run grouped cue reported “Me has this report.” at 6.64–9.24s.
Agreement between runs of the same small recognizer is not independent human
verification. It does not establish whether “Me” is intentional speech, a name,
or a recognition error. No reporter name or new wording has been invented.
The retained original `source-cue-02.wav` remains the listening evidence.

The shorter pass also ends with “Next day, we'll...” as the excerpt cuts off.
That fragment cannot establish the correct wording of full-run cue 4.

## Proposed Hindi edits — not applied or accepted

These are editorial proposals based on the captured English, not fresh automatic
translation output. Exact cue duration and listening quality remain untested.

| Cue | Proposed wording or action | Reason and limitation |
| --- | --- | --- |
| 1 | कुछ ही समय में खबरों की एक तय दृश्य शैली बन गई, जिसे देखते ही कोई भी पहचान लेता। | More natural than the literal machine wording; not a new approved recording. |
| 2 | Keep the existing मेरे पास यह रिपोर्ट है। only as an explicitly uncertain diagnostic input. | Resolve the English first; do not shorten or change its meaning merely to make it fit. |
| 3 | शुरुआत एक अहम जगह के फीके-से शुरुआती शॉट से होती है। | “Lackluster” describes dullness, rather than the machine translation's “unclear.” “Establishing shot” may warrant a retained technical term for the intended audience. |
| 4–5 | Review the entire source sentence before writing a complete Hindi version. | “Next day,” “altar,” and the connection to cue 5 remain suspect. Translating fragments separately caused broken syntax; profanity also needs a meaning-preserving editorial choice. |
| 6 | आगे क्या होता है? | Natural short rendering of “What comes next?”; not yet duration-tested. |
| 7–8 | Resolve “fellow shot” from source audio and translate the complete thought together before allocating it to cues. | Possible recognition error and an incomplete thought; avoid treating an inferred “filler shot” as confirmed speech. |
| 9 | Exclude from a future excerpt only after selecting a complete-sentence boundary. | The 44-second test cuts into the next sentence. Do not force the 0.6-second fragment to fit or alter the retained baseline. |

## Isolated timing experiment

`dev/retry_real_video_cue.py` reuses the baseline's cleaned Abhishek reference and
cue 2 translation. It calls the production speech/mastering/tempo path with
unchanged generation defaults and no fixed seed. At most two fresh takes are
generated, stopping early if one fits the original 2.600-second window.

The diagnostic uses `allow_overflow=True` solely to retain a full candidate for
inspection. Each candidate's actual duration is recorded; no take is truncated,
overlaid into a video, marked accepted or used to relax the normal render guard.
Raw synthesis and processed WAVs are both retained. Separation, recognition and
translation are not repeated. No package or model is installed or downloaded.

The first driver invocation failed before inference because its JSON read used
Windows' default text encoding. The read was changed to explicit UTF-8 and the
original failure log retained separately. This was a diagnostic-driver error,
not a new production regression.

Results are recorded in `validation/2026-10-04-cue-retry.json` and the rerun log.
The completed retry took 93.953 seconds including setup. Trial 1 was 6.134 seconds
and trial 2 was 5.832 seconds, both exceeding the 2.600-second slot. Their raw
synthesis durations were approximately 8.23 and 7.83 seconds, respectively.
Both raw and processed files are retained in
`validation/2026-10-04-cue-retry-27beb73d/`; all four WAVs decode successfully.
The owned temporary workspace was removed. Compared with the earlier 3.011-second
failure, these fresh takes show substantial duration variation for unchanged
text/reference/defaults. Two attempts are not a statistical reliability estimate
and do not identify the cause of that variation. No successful fitting take was
found, and increasing tempo or cutting words was not used to force success.

Passing a timing measurement does not establish intelligibility, source meaning,
voice naturalness, synchronization or release readiness. No backend production
code changed here; the previous 487-check result is retained, not rerun.
