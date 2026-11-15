# Speech and dialogue integrity repair — 2026-10-03

## Approval and scope

The user approved the speech-integrity proposal after a read-only inspection.
The agreed behavior was to fail visibly on speech-generation, selected-voice,
or mastering failures; validate generated audio; preserve valid short lines;
reject transcripts without dialogue; remove the emergency silent reference;
warn on successful GPU-to-CPU recovery; and reject the unsupported literal
`source` language for XTTS. Focused tests and thorough documentation were
included.

No tools, frameworks, packages, model weights, or downloads were added. Tests
use simulated engine boundaries, existing pydub, Python standard-library mocks,
short tone fixtures, and the bundled FFmpeg. One active video/audio render is
still the queue policy. Existing within-render segment-worker execution was
retained and tested with simulated engines.

Existing user changes and previous cleanup, queue, and output-integrity changes
were preserved. No commit, push, deployment, or release was performed.

## Confirmed behavior before this step

- XTTS could fail to initialize or generate audio, print an error, and return
  normally. Its provider then returned the requested filename regardless.
- RVC could fail to initialize or infer and return normally. The pipeline
  accepted unconverted TTS audio when the selected-voice output was absent.
- F5 exceptions were caught in the segment loop, allowing a nonblank line to
  disappear.
- Missing audio or mastering failure could return `None`; assembly interpreted
  that as a skipped line instead of a failed job.
- A valid line whose timing window was 500 milliseconds or less was discarded.
- Empty transcripts produced an all-silent voice track in the audio template.
- XTTS could create a three-second silent WAV as an emergency voice reference.
- Reused segment filenames could be accepted without establishing that the
  current generation attempt produced them.
- RVC retried every inference `TypeError` as an API-signature fallback, including
  errors originating inside inference itself.
- XTTS was passed `language="source"` despite that not being a supported speech
  language. The transcription worker currently discards detected-language
  metadata, so automatic source-language support needs separate work.

## Changes by file

### `core/audio_utils.py`

Added `load_playable_audio(path)`, reused by the pipeline and local handlers:

1. Require an existing, nonempty regular file.
2. Open it with an explicitly managed file handle.
3. Decode it using existing pydub support.
4. Require a clip with positive duration in milliseconds.
5. Raise an actionable error for missing, empty, undecodable, or zero-sample
   audio, preserving decoder exceptions as causes.

Validation does not infer whether speech is meaningful, in the correct voice,
or accurately pronounced. A decodable silent clip is still structurally
playable; this step removes the artificial silent-reference fallback but does
not introduce a heuristic loudness/speech detector.

Closed pydub export handles in reference preparation and mastering before the
next operation consumes those files. Their audio effects were retained.

### `core/tts/tts_handler.py`

- Initialize the engine attribute explicitly rather than leave an incomplete
  object on failure.
- Raise for missing model/config files, engine import failures, unsuccessful
  CPU loading, and unsuccessful GPU plus CPU loading. Default feature-scoped
  model recovery remains available in production; tests do not invoke it.
- Preserve successful CPU recovery after GPU loading fails. Update the actual
  handler device to CPU and log a warning including the original failure.
- Accept an optional warning callback for UI delivery. Callback delivery errors
  are logged and do not discard an otherwise successfully recovered engine.
- Require a playable explicit reference when one is supplied; do not silently
  substitute another clip for an invalid explicit selection.
- Retain the existing non-emergency reference search when no reference is
  supplied: project reference asset, source audio in temp, then model sample.
- Remove the emergency-reference method and its silent-WAV generation imports.
- Require a reference instead of skipping nonblank speech when none is found.
- Reject the literal `source` language with an explanation that an explicit
  speech language is required.
- Remove an old generation output before invoking the engine, propagate
  inference errors, decode/validate the generated result, and return the actual
  output path only on success. Blank text may still return `None` as a gap.

The existing PyTorch safe-global registration and model recovery integration
were retained. No engine versions, model architecture, synthesis parameters,
or dependency manifests were changed.

### `core/providers/tts/xtts_local.py`

Reject `source` before constructing/loading a handler. Pass a callback that
delivers CPU-recovery warnings through the existing `bridge.push` log event.
Return the handler's result, rather than invent success from a requested path.

### `core/rvc/rvc_handler.py`

- Raise when engine import, asset recovery, or initialization fails.
- Raise when inference is requested from an unready engine or the selected
  checkpoint is missing.
- Decode the input before preprocessing. Delete stale preprocessing audio,
  invoke the existing checked pipeline FFmpeg helper, and validate the new
  16 kHz mono clip. Do not fall back to the unprocessed input on failure.
- Preserve the existing checkpoint/config preparation behavior; checkpoint
  architecture and config compatibility were not redesigned.
- Require a supported model-loading method.
- Select the inference call shape using standard-library `inspect.signature`.
  Pass `f0_up_key` if supported, otherwise use the installed engine's
  `set_params(f0up_key=...)` when available. If a nonzero pitch change cannot be
  applied, raise instead of silently ignoring it.
- Do not retry an internal inference `TypeError` as if it were an unsupported
  keyword. The original failure now reaches the user.
- Decode and validate the output before reporting success or returning its
  filename.
- Clean preprocessing and failed output files in `finally`; cleanup failures
  log warnings rather than mask the original inference error.

The selected-voice filenames/config lookup remain as before. Marketplace paths,
display-name-to-checkpoint mapping, and forced V2 config behavior still need a
separately scoped compatibility review.

### `core/providers/voice/rvc_local.py`

Return the handler's successful result and propagate its failures rather than
always returning the requested output path.

### `core/providers/voice/f5tts_local.py`

Validate the reference clip, delete any stale output before inference, and
validate the generated clip before returning success. Existing F5 input
requirements, inference arguments, and lazy loading remain unchanged.

### `core/pipeline.py`

Reworked `_dub_segment()` around an explicit stage name and a unique temporary
directory for each invocation. Nonblank dialogue must produce usable audio.

- Retain blank-text gaps as `None` without invoking synthesis.
- Validate finite, nonnegative, increasing timings. Dialogue windows below
  one millisecond fail clearly because the assembly operates in milliseconds.
- Use exact `CLONED_USER` matching; other selected actor names follow their
  selected provider path.
- Use the supplied clean reference when present, rather than silently replace
  a missing clean reference with another clip.
- Preserve the F5 direct text-to-speech path that bypasses XTTS.
- Propagate F5, selected-voice resolution, synthesis, normalization, conversion,
  and mastering failures. Never substitute the unconverted TTS clip after
  selected-voice conversion fails.
- Decode audio after generation, after conversion, and after mastering.
- Preserve valid short lines by removing the blanket 500 ms cutoff.
- Retain the existing tempo tolerance and 0.85–1.3 speed range and trimming to
  the available timing window. Trimming can still cut a long utterance; this
  repair does not redesign alignment or eliminate all speech truncation.
- Clean invocation-specific files on normal return or exception.
- Wrap failures with a one-based segment number, actor, and stage while
  preserving the cause. Example: `Segment 7, voice 'Actor', selected voice
  conversion failed: checkpoint could not load`.

Added `_require_dialogue()` before transcript merging/translation and before
assembly. Empty or entirely blank transcripts now raise `No dialogue detected`
with source/transcription guidance. The subtitle-translation template remains
independent of speech assembly.

Both sequential assembly and existing segment-worker assembly reject `None`
for nonblank text. The worker path propagates exceptions and attempts to cancel
pending futures. Already-running model calls cannot be forcibly cancelled and
may finish before the executor exits. Mixing remains in transcript order.

No parallel video jobs, new concurrency framework, persistent queue, automatic
source-language detection, or new progress-event protocol was introduced.

## Test implementation and results

Added `dev/test_speech_integrity.py` and included it in the existing
nondestructive `dev/run_cleanup_checks.py` runner.

The new module contains **43 tests**, grouped as follows:

| Group | Count | Coverage |
| --- | ---: | --- |
| Audio validation | 4 | Missing/empty, corrupt, zero-sample, real 300 ms clip |
| XTTS | 13 | Config/loading failure, CPU recovery/warning, missing/stale output, references, source language, provider propagation |
| Segment assembly | 15 | Stage errors, conversion/F5/mastering failure, short dialogue, blank gaps, timing, fresh folders, empty transcription, sequential/worker success and failure |
| RVC | 9 | Initialization/readiness/checkpoint errors, real preprocessing, failed preprocessing, missing output, API/pitch selection, no internal-TypeError retry |
| F5 | 2 | Stale/missing output rejection and valid simulated output |

Tests call the actual application helpers and lifecycle code. Inference engines
are substituted at their import/construction or method boundary. Audio decoding
uses real short tone WAVs; RVC preprocessing uses real bundled FFmpeg. Engine
model weights are not loaded and no model downloads are performed.

The initial test harness imported the full TTS package before replacing its
engine. Two runs were stopped during lengthy imports before test execution.
The harness was corrected to substitute the import boundary and retain the
same imported handler module for the provider. Production engine imports were
not altered by this test-only isolation.

Reproduction from the workspace root in PowerShell:

```powershell
$env:TEMP = Join-Path (Get-Location).Path 'temp'
$env:TMP = $env:TEMP
$env:PYTHONIOENCODING = 'utf-8'
.\build\windows-portable\python.exe -B dev/run_cleanup_checks.py
```

Final result: **103 tests passed**, exit code 0, approximately 13.5 seconds of
reported test execution. This comprises the previous 60 checks and 43 new
speech checks. The Windows portable CPython 3.10.11 interpreter was used with
bytecode generation disabled. Temporary fixtures were removed; `temp` was
empty after the aggregate run.

All seven changed production files passed `git diff --check`; Git emitted only
its configured LF-to-CRLF conversion notices for provider files. The unrelated
previously documented trailing whitespace elsewhere in the workspace was not
changed. AST syntax checks also passed before test execution.

## Files changed in this step

| File | Purpose |
| --- | --- |
| `core/audio_utils.py` | Reusable decoded-audio validation and managed export handles |
| `core/tts/tts_handler.py` | Explicit XTTS loading/generation/reference failures and CPU recovery warning |
| `core/providers/tts/xtts_local.py` | Handler result propagation, early source-language rejection, warning delivery |
| `core/rvc/rvc_handler.py` | Checked preprocessing, initialization/inference propagation, validated output, cleanup |
| `core/providers/voice/rvc_local.py` | Handler result propagation |
| `core/providers/voice/f5tts_local.py` | Reference/output validation and stale-output rejection |
| `core/pipeline.py` | Required dialogue, isolated segment files, contextual failures, short-line preservation |
| `dev/test_speech_integrity.py` | 43 simulated-engine and real-audio checks |
| `dev/run_cleanup_checks.py` | Include the new tests |
| `docs/SPEECH_INTEGRITY_REPORT_2026-10-03.md` | This record |

Git diffs against HEAD include earlier user edits and previously approved
repairs. The file table and this report describe the current step's scope.

## Remaining limitations and next approval

No complete AI render, actual XTTS/RVC/F5 inference, actual GPU loading/recovery,
GUI interaction, fresh installation, Linux/macOS run, or release packaging was
verified. Simulated engine tests establish control-flow and file-validation
behavior, not model compatibility, voice quality, or pronunciation accuracy.

Decodable generated silence and semantically wrong speech cannot be identified
by structural validation alone. CPU model thread safety and lazy-handler
initialization races remain outside this repair; testing simulated segment
workers is not proof that all installed engines support concurrent CPU calls.
Cancellation remains cooperative, with already-running tasks allowed to finish.

Translation still has its previously identified source-text fallback and HTTP
handling problems. Background separation, optional-feature skipping, the
NudeNet compatibility mismatch, and stem-export defects remain separately
scoped work. An interrupted process may leave temporary segment folders for
the existing temporary cleanup to handle on a later run.

Recommended next approval: inspect and prepare the translation-integrity fix
proposal before modifying translation behavior.
