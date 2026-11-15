# IndicF5 moving-video iteration — October 6, 2026

**Latest outcome:** the user reviewed this exact diagnostic video and replied
"it's actually quite good...". Acceptance is recorded in
`docs/validation/2026-10-06-indicf5-video-user-acceptance.json`. The subsequent
normal backend render passed all eight cues and reproduced the complete reviewed
voice track sample for sample. See `docs/INDICF5_APP_INTEGRATION_2026-10-06.md`
for production changes, test evidence and remaining UI/translation/background
gates. The chronological diagnostic details below describe the earlier state.

## Acceptance entering this iteration

The user approved the exact sentence-wise Abhishek paragraph as clear and
natural. Its receipt and acceptance are retained separately from failed
continuous speech. The source phrase "Me has this report" was confirmed against
its original excerpt. Context grouping/extended recognition produced eight
complete English groups through 52 seconds. Raw NLLB translations still failed
meaning checks; assistant editorial Hindi proposals were explicitly presented,
including their adaptation/nuance tradeoffs.

The user replied "yes" to reviewing that corrected Hindi draft before video
speech generation. Text approval is recorded in
`docs/validation/2026-10-06-video-hindi-editorial-acceptance.json`, with the
approved draft's SHA256 pinned. This authorizes the presented draft, not all
raw NLLB translations, new models/frameworks or final video acceptance.

## Speech generation plan and implementation

`dev/verify_indicf5_user_voices.py` gained a diagnostic `--video-followup` mode,
requiring the established selected/alternate/long modes. It verifies draft
approval and uses the exact editorial text. All eight cue texts reconstruct
exactly from fourteen shorter sentences; generation is serial and trained
model/vocoder weights load once. Confirmed alternate Abhishek reference,
seed 1234, guidance 2.0 and 32 steps are retained from the preferred B follow-up.
Every sentence requests a native generation duration calibrated by UTF-8 text
length to that B passage. This is a heuristic, not measured syllable alignment.
There is no cue-based acceleration, truncation or old Hindi 1.342 post-tempo.

Existing strict checkpoint/vocoder loading, vocabulary inclusion, reference
hash checks, native mono 24 kHz, finite/nonzero waveform checks, exact fixed
target frame count, gain-only listening copies and full decoding apply.
Receipts include cue/sentence indices, source windows, exact sentence text,
generation parameters, reference audio/text/hash, raw/listening hashes and
draft identity. Listener acceptance flags remain false for these new utterances.

The initial preflight stopped before synthesis because its parser recognized
only Hindi danda endings, while approved cue 5 ends with a question mark.
The diagnostic parser now recognizes danda, question mark and exclamation mark.
It still requires exact reconstruction; approved wording is unchanged. Failure
log: `docs/validation/2026-10-06-indicf5-video-speech.log`.
Retry: `docs/validation/2026-10-06-indicf5-video-speech-retry.log`.
This planning failure occurred before a render job/receipt was created.

## Moving-video assembly and validation contract

`dev/assemble_indicf5_video_review.py` is an explicit diagnostic bridge, not
a new selectable production engine. It accepts only completed workspace speech
receipts, the unchanged hash-pinned approved text and original source hash.
It checks every sentence once, in order, with matching cue bounds and text.
Speech samples are concatenated with 0.20-second internal sentence gaps and
placed at the cue's start in a 52-second mono 24 kHz PCM timeline. Source
samples must survive assembly exactly. Every cue must fit its existing window;
overflow fails rather than cutting audible words or accelerating speech.
The rest of each cue/timeline is digital silence. Subtitles carry the approved
full cue text and matching source windows.

Existing FFmpeg encodes real moving frames from the source plus the generated
Hindi track and soft Hindi subtitles. The mapping deliberately selects only
the new audio. This first diagnostic checks voice, cue fit, subtitles and moving
video; background preservation is not tested and is explicitly false in the
receipt. It is not represented as a complete production-pipeline acceptance.
Source file, model connections and application defaults are not altered.

Checks require video/audio/subtitle stream types, duration within 0.10 seconds
of 52 seconds, full video/audio and voice-track decoding, unchanged source hash,
and exact PCM assembly. Output, voice and subtitle hashes are recorded.
RenderContext owns transient files and publication, and cancellation follows
the existing job/process controls. The speech hook checks between transformer
passes. No new package/framework, model download or global runtime installation
is involved. Script syntax has been checked; broad production test-suite results
are not claimed for these diagnostic-only helpers.

## Remaining release gates

The resulting video needs human review of every cue, particularly short
questions, the long satirical description and the final cue. A technically
valid WAV/MP4 does not establish correct words, naturalness or timing quality.
Production integration still needs a separate engine identity/verified reference
pair, job-scoped runtime reuse, engine-aware delivery policy, actual readiness/
failure/cancellation validation and calibrated resource estimates. Automatic
translation quality and background-preserving full workflow remain separate
gates. Hindi/Abhishek acceptance cannot be generalized to Sujata, other languages
or other source material.

## Completed speech and first render inspection failure

Speech generation completed successfully with receipt
`docs/validation/2026-10-06-indicf5-gpu-user-voices-2eb79a50.json`.
Fourteen cases completed in 115.313 seconds after imports. Strict trained
loading, confirmed reference integrity, supported text, native 24 kHz output,
finite/nonzero samples, fixed target frame counts, gain-only listening copies
and raw/listening decode checks passed. Job workspace cleanup completed.
Every cue fit its window, including the internal sentence gaps, without
post-generation tempo changes or word cuts:

| Cue | Window seconds | Speech plus internal gaps | Spare seconds |
| --- | --- | --- | --- |
| 1 | 6.400 | 5.290667 | 1.109333 |
| 2 | 2.000 | 1.717333 | 0.282667 |
| 3 | 5.000 | 4.309333 | 0.690667 |
| 4 | 14.720 | 14.338667 | 0.381333 |
| 5 | 1.280 | 1.216000 | 0.064000 |
| 6 | 7.000 | 6.450667 | 0.549333 |
| 7 | 6.000 | 5.576000 | 0.424000 |
| 8 | 9.000 | 8.178667 | 0.821333 |

Cue 5 has only 64 milliseconds spare time. Exact frame fit does not ensure
comfortable pronunciation or accurate source alignment; listener review is
essential. Individual constant listening gains can still yield audible level
changes across sentence boundaries.

Initial assembly receipt:
`docs/validation/2026-10-06-indicf5-video-review-7d17d15b.json`.
Speech fit and encoding completed, but inspection failed because the bound
`core.render_context.run_process` forwarded `capture_output=True` directly to
`subprocess.Popen`, which does not accept that convenience argument. No final
video was published as passed; owned workspace was cleaned. Log:
`docs/validation/2026-10-06-indicf5-video-assembly.log`.

The shared runner now translates bound-job `capture_output=True` into separate
stdout/stderr pipes, retaining text/binary behavior and cancellation tracking.
It rejects explicit stdout/stderr conflicts before process launch, matching the
standard `subprocess.run` contract. Explicit capture false preserves configured
streams. Unbound behavior still delegates to `subprocess.run`. This fixes an
actual shared helper bug also affecting older validation scripts; it does not
enable IndicF5 as a production engine.

`dev/test_process_capture.py` adds real-process regression checks for separate
text capture, binary diagnostics/nonzero exit, conflicting streams and explicit
capture false. Related cancellation and cached-session checks are run too.
The first test command could not locate `dev` because the portable interpreter's
isolated search path excludes the current directory; the corrected test harness
explicitly adds the workspace root. An initial combined run passed the capture
and cancellation tests but encountered four sandbox temporary-folder access
errors in existing session tests. A rerun uses workspace TEMP/TMP, preserving
the initial log instead of representing it as a clean pass. Final results and
render retry are recorded below once complete.

The assembler also extracts embedded Hindi subtitles back to SRT and compares
their text to every approved cue. This adds content-preservation verification
beyond stream presence. Original subtitle source and round-trip SRT are retained.

## Completed review video and validation result

The focused rerun passed all 29 tests in 2.963 seconds with workspace TEMP/TMP.
Log: `docs/validation/2026-10-06-process-capture-tests-workspace.log`.
The four new capture checks and related cancellation/session checks passed.
Earlier failed harness/environment logs remain retained; they are not claimed
as product successes. No broad backend/frontend-suite pass is asserted here.

Corrected assembly completed successfully with receipt
`docs/validation/2026-10-06-indicf5-video-review-2c8507f0.json` and log
`docs/validation/2026-10-06-indicf5-video-assembly-retry.log`.
The sibling directory contains:

- `abhishek-hindi-review.mp4`: 52.000 seconds, 7,009,703 bytes; H.264 real moving
  video at 854×480 with 1,300 reported frames, AAC Hindi audio and soft Hindi
  subtitles (`mov_text`).
- `hindi-voice.wav`: native 24 kHz mono PCM sentence-wise timeline, exact source
  speech samples preserved with explicit silent gaps.
- `hindi-subtitles.srt` and `verified-subtitles.srt`: source captions and captions
  extracted back from the MP4; all eight approved Hindi texts match exactly.
- `review-report.json`: render evidence; outer receipt includes final workspace
  cleanup status.
- `frame-12s.png`: retained decoded frame for visual inspection. It shows the
  expected original location footage. Subtitles are soft, not burned into pixels.

All eight measured cue windows passed without cuts/tempo changes, duration and
expected stream types passed, full video/audio and voice decoding passed, source
hash was unchanged, subtitle text round-trip passed and owned workspace cleanup
completed. A frame was decoded and visually inspected. No inference/render
session remains running. Metadata distinguishes the shared process-helper fix
from the unchanged production speech route: `shared_process_helper_fixed=true`,
`production_voice_route_changed=false`. It does not inaccurately claim that no
production code was repaired.

Hashes:

- Video: `5c7233e631ba6eca09168df878bc5b712706d7296aedd19c2c748f5727eaa411`.
- Voice: `74077375d79f38365ec30f6798008dcc21bf7428e837b8731cb50384caf3f981`.
- Source subtitle file: `3bfc2d64a74281941a8731bf1fd49d53c0131bad636023e1089bf046a600afab`.

At diagnostic completion, human review was pending for this exact video, including natural delivery, words,
sentence transitions, the very short question around 29 seconds and the final
cue from 43 seconds. Accepted earlier audio is not acceptance of these new
sentences or timing. The review render uses approved editorial text and an
explicit diagnostic bridge; it is not a selectable app route or validation of
automatic translation/background-preserving production. Those gates remain.
