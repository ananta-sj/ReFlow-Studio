# FFmpeg and output integrity repair — 2026-10-03

## Approval and scope

The user approved step 1 of the pipeline failure proposal: checked FFmpeg
execution, useful failure diagnostics, bounded duration probing, propagated
subtitle-write errors, and validated output replacement that preserves an old
output when its replacement fails. Focused tests and this report are included.

No tools, frameworks, packages, model weights, or downloads were added. Existing
Python standard-library facilities, pydub, and bundled FFmpeg/FFprobe are used.
The one-active-render queue behavior from the previous step remains unchanged.
Existing user changes were retained; no commit, push, release, or deployment
was performed.

## Problems addressed

Previously, the pipeline's FFmpeg wrapper did not request checked exit codes.
Callers often discarded stderr, so failed extraction, tempo processing, muxing,
or subtitle attachment could continue without an actionable error.

`get_duration()` had no timeout and returned zero on probe failure. That allowed
later processing to use a meaningless duration or remain blocked indefinitely.

`generate_srt()` caught write errors and printed them. A pipeline could continue
with missing, partial, or old subtitles. Audio and subtitle final exports wrote
directly to their destinations, as did the second pass of video rendering.
An unsuccessful rerender could therefore damage a previous successful output.

Video merging also returned quietly for a missing video input, and speed
adjustment returned the original audio if the new file was absent. File
existence alone was insufficient to establish that a current media operation
had succeeded.

## Changes in `core/pipeline.py`

### Checked local media commands

Added `_run_media_command()` and routed `_run_ffmpeg()` and pipeline FFprobe
calls through it.

- Uses `subprocess.run(check=True)` so nonzero exits become errors.
- Keeps the existing 1,800-second FFmpeg timeout and Windows below-normal
  process priority.
- Adds a 60-second FFprobe timeout for duration and output validation.
- Closes stdin by default so the command cannot wait for interactive input.
- Captures stderr in a temporary file even when an older caller requests that
  it be discarded. stdout remains suppressed for FFmpeg and captured for probe
  results.
- Reports a tool name and exit code, timeout, or executable-start failure.
- Includes only the last 6,000 bytes of stderr, decoded as UTF-8 with replacement
  for invalid bytes. The complete diagnostic stream is temporarily held on disk
  rather than accumulated in memory. This bounds the diagnostic excerpt, not
  the size of the temporary log while the command runs.
- Preserves the original exception as the cause of the raised `RuntimeError`.

These changes apply to commands routed through the pipeline helper. Standalone
FFmpeg calls in RVC and engine subprocesses in Wav2Lip/MuseTalk were not changed.

### Bounded and valid duration probing

`get_duration()` now requires a checked probe response containing a finite,
positive duration. Zero, negative, NaN, infinity, empty, and unparseable values
raise an error instead of silently becoming zero.

### Staged publication

Added `_staged_output()` as a standard-library context manager:

1. Creates a unique temporary sibling of the destination, retaining its file
   extension so media tools select the intended container.
2. Allows the caller to write and validate that temporary output.
3. Requires a nonempty file before publication.
4. Uses `os.replace()` after successful completion. A sibling keeps replacement
   on the same filesystem.
5. Removes the pending file on failure. If cleanup itself cannot remove it,
   logs a warning while preserving the original error.

The old destination is never proactively deleted. A locked destination, failed
write, failed validation, or failed subprocess prevents replacement. Successful
rerenders retain the existing behavior of replacing the destination filename;
this does not introduce output version history or backups.

### Output media validation

Added `_validate_media()` using checked FFprobe JSON output. Before publication:

- Final video requires video and audio streams and a positive finite duration.
- Embedded-subtitle output additionally requires a subtitle stream.
- Final WAV export and tempo-adjusted audio require an audio stream and a
  positive finite duration.
- Malformed probe JSON, missing fields, invalid duration, or missing required
  stream types raise an error.

This verifies container metadata and stream presence. It does not decode every
frame, prove semantic correctness, detect all corruption, or verify that the
speech is translated, complete, or in the selected voice.

### Video merging

`merge_av()` now rejects missing/empty video and audio inputs. It creates unique
clean-mux and subtitle working files in a temporary directory beside the final
output, and writes the final candidate to a staged file.

Clean muxing, subtitle embedding, and burn-in all use checked FFmpeg execution.
The candidate is validated before the destination is replaced. Requested
burn-in with no usable subtitle file now fails clearly.

The existing custom subtitle styles, encoding preset, video/audio encoding
settings, and default style values were retained. The subtitle filter path is
quoted and its Windows drive colon escaped; the real burn-in test passed in
the workspace path containing a space. Unusual path characters such as an
apostrophe were not separately validated.

An ordinary merge without subtitles remains supported. Existing embedded
subtitle language metadata (`eng`) was retained; language tagging is outside
this change.

### Subtitle writing

`generate_srt()` now writes to a staged UTF-8 file and propagates errors. It
rejects nonfinite, negative-start, or reversed/zero-length cue timings and
rejects a result containing no nonempty cues. Cue numbers remain consecutive
when blank text is skipped. A successful subtitle file replaces its destination
only after writing completes.

This shared method protects both intermediate subtitles and the final
subtitle-translation template. Consequently, a video transcript producing no
nonempty subtitle cues now fails earlier instead of proceeding with empty
subtitles. Full empty-transcription policy for the audio template remains part
of the separate dialogue-integrity proposal.

### Audio export and tempo processing

The audio-dubbing template now stages and validates its final WAV before
replacing any existing audio output.

Tempo processing uses a unique temporary directory for each invocation,
replacing the shared `stretch_in.wav` / `stretch_out.wav` filenames. Failed
tempo processing raises instead of silently returning unadjusted audio. This
also prevents those tempo filenames from colliding when the existing
within-render segment-worker option is used; it does not add parallel video
jobs or establish overall inference concurrency safety.

Explicitly close the pydub export handles and the tempo-output input handle
before validation, replacement, or directory cleanup. Initial test execution
revealed unclosed-file resource warnings on these paths; the final run had
none of those warnings.

## Tests and validation

Added `dev/test_output_integrity.py` and included it in the existing
nondestructive `dev/run_cleanup_checks.py` runner.

The new module contains **24 checks**: 18 simulated failure/publication tests
and 6 bundled-media integration checks. It invokes the actual pipeline helpers;
model inference is not involved. Tests cover:

- Nonzero exit diagnostics, bounded error excerpts, timeouts, and missing tools.
- Probe timeout/check settings and invalid duration values.
- Failed writes, empty outputs, locked replacement, and preservation of an
  existing destination.
- Missing streams, invalid probe data, malformed JSON, and invalid durations.
- Subtitle write failures, invalid/blank cues, and successful replacement.
- Failed clean mux, failed embedded/burned subtitle passes, missing inputs,
  and requested burn-in without subtitles.
- Real muxing with no subtitles, embedded subtitles, and burned subtitles.
- Real corrupt-input FFmpeg failure preserving an old output.
- Real tempo processing producing usable, shorter audio with unique files.
- The actual audio-template publication path preserving an old output when
  its candidate validation fails; STT/TTS and Janitor are mocked in that case.

The six bundled-media tests use synthetic 64×64 video, short silent WAV files,
and a tiny generated subtitle file. Files live in automatically cleaned
temporary directories within the workspace. Production sample videos and
existing rendered outputs were not used or modified. Windows bundled-media
tests skip if the bundled `ffmpeg.exe` is absent.

Reproduction from the project root in PowerShell:

```powershell
$env:TEMP = Join-Path (Get-Location).Path 'temp'
$env:TMP = $env:TEMP
.\build\windows-portable\python.exe -B dev/run_cleanup_checks.py
```

Final aggregate result: **60 tests passed**, exit code 0, approximately 5.1
seconds of reported test execution. This includes the previous 36 backend,
model-recovery, and queue checks. Bytecode writing was disabled.

`git diff --check -- core/pipeline.py` passed. The unrelated, previously
documented trailing whitespace in `core/hardware_monitor.py` remains outside
this step. No full AI render, GUI session, GPU test, fresh installation,
Linux/macOS run, or release build was performed.

## Files changed in this step

| File | Purpose |
| --- | --- |
| `core/pipeline.py` | Checked media execution, probing, staged outputs, subtitle propagation, tempo files |
| `dev/test_output_integrity.py` | 24 focused checks, including bundled FFmpeg integration |
| `dev/run_cleanup_checks.py` | Include the new test module |
| `docs/OUTPUT_INTEGRITY_REPORT_2026-10-03.md` | This detailed approval/change/validation record |

The preexisting subtitle-style and stem-export changes in `core/pipeline.py`
were preserved. Git's diff against HEAD includes those earlier changes as
well, so this report is the scope record for the current step.

## Remaining limits and next approval

Staging temporarily requires enough disk space for an additional output and,
for video subtitle passes, a clean intermediate. Normal completion cleans
these working files; an abrupt process termination can leave `.reflow-*`
files/directories beside outputs. No new startup cleanup policy was added.

This repair makes individual exports transactional, not the whole job. A later
stage such as stem export can still fail after a valid video was published.
The known undefined stem variables remain unchanged pending their own approval.

Speech-generation and voice-conversion failures, translation fallback behavior,
background-separation fallback, optional feature skipping, and the NudeNet
compatibility problem remain separately scoped work. A valid media container
can still contain missing or incorrect dialogue.

Recommended next step: prepare and approve the dialogue-integrity implementation
so failed speech generation cannot silently produce gaps in a completed dub.
