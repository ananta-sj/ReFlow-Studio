# Pitch-preserving tempo alternative — 4 October 2026

## Why this comparison

Both supplied-reference raw takes were accepted (“both are beautiful”). User
also accepted both loudness-only/unpaced versions as equally clean (“yes”).
The no-EQ/compression paced derivatives remained distorted at Sujata's opening
and Abhishek's ending. Existing atempo processing is therefore implicated for
these inputs. This does not prove atempo fails universally.

## Existing bundled capability

Installed FFmpeg lists `rubberband`; local filter help confirms tempo/pitch.
Use `rubberband=tempo=1.342:pitch=1` with existing defaults, keeping the approved
tempo and retaining pitch. No tool/package/framework installation or download.
`dev/compare_hindi_tempo.py` reuses exact accepted loudness-only WAVs. No inference,
reference change, EQ, extra compression, fades, pauses or word cuts. Prior atempo
takes are copied alongside outputs. Overshoot needs only measured gain reduction
and remeasurement; no new post-tempo normalization pass.

## Execution and measurements

Completed **2.593 seconds**, workspace removed. WAVs decode and contain signal;
duration within100ms of input/tempo, explicit original sample rate/channel count,
whitespace check passed.

| Reference | Accepted input | Prior atempo | Rubber Band | Final true peak / integrated level | Gain correction |
| --- | --- | --- | --- | --- | --- |
| Sujata | 9.393 s | 6.988 s | 6.999 s | −1.55 dBTP / −16.62 LUFS | −0.54 dB |
| Abhishek | 7.327 s | 5.445 s | 5.460 s | −1.59 dBTP / −16.32 LUFS | None |

Levels differ from earlier atempo outputs (−14.53/−14.40 LUFS): not perfectly
loudness-matched. Do not attribute preference solely to distortion reduction
without considering that difference. Pitch=1 is the requested filter behavior;
this run does not include scientific/perceptual pitch validation. Decoding and
duration do not certify naturalness, complete words or listening acceptance.

Receipt/log: `validation/2026-10-04-hindi-tempo.json` and `.log`.
Outputs: `validation/2026-10-04-hindi-tempo-0266c6e3/`. Source hashes recorded;
previous raw/user files preserved. Production code unchanged; prior backend/UI
results retained, not rerun for diagnostic files.

## Decision pending

Check Sujata's opening and Abhishek's ending, overall pace and voice quality.
If preferred, implement a production route with actual pitch/timing/cancellation
checks and capability handling for builds without the filter, then run relevant
regressions. Clean natural pace should remain an option when fitting harms speech.
No global quality or release acceptance claimed.

Subsequent user feedback: **“beautiful”**. Both presented alternative-tempo clips
are accepted for this passage/reference pair. Production tempo helper updated
and verified against exact approved PCM; see SPEECH_TEMPO_FIX_2026-10-04.md.
This supersedes the pending decision for these takes, not all-text acceptance.
