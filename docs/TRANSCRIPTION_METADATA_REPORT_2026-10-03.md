# Transcription metadata preservation — 2026-10-03

## Approved scope

The user approved the first source-language repair: preserve detected language and confidence from transcription, retain compatibility with older segment-only results, test the worker/provider/pipeline boundaries, and document the changes. Source-language selection, manual overrides, confidence thresholds, translation tokenizer configuration, and interface controls require later approval. This change adds no dependencies, frameworks, external tools, or models. No commit, push, or deployment was performed, and unrelated preexisting changes were preserved.

## Problem and result

Local faster-whisper supplies segments and an information object containing language and language_probability. STTHandler previously discarded that object. The worker consequently wrote only a JSON segment list. Cloud STT adapters also extracted segments and dropped top-level language metadata. Even a later source-language fix could not use information that had already been discarded.

The local handler now preserves available metadata. The worker writes an envelope containing segments, language, and language_probability. Providers accept that envelope as well as legacy lists. Both audio and video pipeline paths preserve metadata while merging short segments. Translated text can replace segment text without replacing the original recording's source-language metadata.

Example worker output:

```json
{
  "segments": [
    {"start": 0.0, "end": 1.0, "text": "Example dialogue"}
  ],
  "language": "hi",
  "language_probability": 0.91
}
```

A segment-only result is normalized to the same representation with both metadata fields null. English is never invented by this normalization.

## Representation and compatibility

Added core/transcription.py using only the standard library. TranscriptionResult subclasses list so existing iteration, indexing, length checks, list equality, and segment consumers continue to work. Its language and language_probability attributes carry source metadata. This avoids changing every downstream segment consumer to a new dictionary API.

normalize_transcription() accepts a TranscriptionResult, a plain segment list, or a dictionary containing segments. It copies segment dictionaries and retains additional fields such as speaker identifiers. Each segment must be a dictionary with start, end, and text fields; malformed response shapes raise ValueError. This helper does not newly validate timestamp ranges, alter text, or rewrite language codes.

with_segments() creates a new result with changed segments while retaining source metadata. The pipeline uses it after the existing short-segment merge. Results carry their own metadata; there is no shared last-language field that could leak the previous job's detection into a metadata-free result.

### JSON compatibility boundary

A generic JSON encoder treats a list subclass as a list, discarding its attributes. Call to_payload() when metadata must cross a JSON boundary. It returns the explicit envelope shown above. The worker uses that method.

The updated local provider accepts both new envelopes and old worker lists. Custom cloud endpoints can continue returning their old lists. Metadata-free segments envelopes also remain valid. External scripts that consume the worker's raw JSON and require a top-level list must be updated to read the segments key; compatibility is provided at the application provider/normalization boundary, not by emitting both incompatible JSON shapes at once.

### Metadata validation policy

- A nonblank string language label is retained, with surrounding whitespace removed. Codes and display names are not guessed, lowercased, or mapped in this step. For example, hi, Hindi, English, and pa remain the provider's original labels.
- Missing language is None. An empty, whitespace-only, or non-string language is ignored with a warning and becomes None.
- A supplied probability must be a finite int or float within [0, 1]. Both endpoints, including zero, are preserved. Booleans, strings, collections, NaN, infinity, and out-of-range numbers are ignored with a warning and become None. Numeric strings are not coerced.
- Missing probability remains None. No default confidence is generated.
- A probability without an available language becomes None because it cannot identify a source language.
- Invalid optional metadata does not discard otherwise valid segments. Malformed segment containers/required fields fail explicitly.

These checks validate shape and range, not the truth of a provider's language claim. A supplied language label can still be unknown to a later translator. No confidence acceptance threshold is introduced.

## Changes by file

### core/transcription.py — new

Defines TranscriptionResult, to_payload(), with_segments(), and normalize_transcription(). Centralizes the compatible representation and metadata validation without loading AI libraries or models.

### core/stt/stt_handler.py

Returns the new list-compatible result using language and language_probability from Whisper's info object. Uses getattr(..., None) to accept absent metadata. Existing segment extraction, beam size, CPU behavior, and model cleanup remain unchanged.

### core/run_stt.py

Adds the repository root to its import path so the standalone worker can import core.transcription. Normalizes the handler result and explicitly writes to_payload() with existing UTF-8 JSON settings. This also tolerates a legacy handler returning a plain list. Keeps the separate process boundary and current worker arguments.

### core/providers/stt/whisper_local.py

Normalizes parsed worker JSON rather than returning it unchanged. Preserves metadata from the envelope and accepts older lists. The checked subprocess execution, one-hour timeout, and temporary-directory cleanup remain in place.

### core/providers/stt/cloud_rest.py

Both existing request presets normalize their returned JSON directly. The chat-compatible verbose transcription shape and the custom segments envelope retain top-level language/language_probability fields when supplied. Custom segment lists remain supported. No endpoint, credential, model, multipart request, or network behavior was added.

A response dictionary without segments now raises a descriptive shape error instead of becoming an empty transcript or an indirect iteration error. Additional segment fields are retained rather than stripped.

### core/providers/base.py

Documents the STT contract as a list-compatible TranscriptionResult with optional metadata, and explains legacy normalization and explicit JSON serialization. Python does not enforce this annotation on third-party providers; plain lists remain accepted by the pipeline.

### core/pipeline.py

Introduces _transcribe_source() shared by the audio helper and the video transcription path. It normalizes the provider result, retains the existing no-dialogue check, runs the existing short-segment merge, and wraps the merged segments with the same source metadata. Existing translation calls still receive their original arguments; this step does not pass source language to translation.

Subtitle-only workflows skip STT and remain unchanged. Metadata is scoped to the in-memory transcription result and the worker's temporary JSON, not a new permanent output sidecar or persisted job record.

### dev/test_transcription_metadata.py — new

Adds 29 focused tests for list compatibility, JSON round trips, legacy and metadata-free results, raw language labels, probability validation, shape errors, copied segments, metadata retention after segmentation, local provider parsing/failures/cleanup, cloud adapters, actual handler extraction from a mocked generator, actual worker-script serialization through runpy, pipeline merging/translation/source bypass, separate successive results, and existing empty-dialogue rejection.

Whisper factories and HTTP/model boundaries are mocked; the worker-script tests execute the real script with a fake STT handler. They do not run a real Whisper subprocess or load actual weights. The local provider subprocess tests simulate the worker JSON file while checking invocation behavior.

### dev/run_cleanup_checks.py

Includes the new module in the existing aggregate backend suite.

## Verification

Focused run: 29 tests passed in 0.229 seconds. Aggregate run: 177 tests passed in 13.162 seconds, exit code 0. All 9 changed Python files passed AST syntax validation. Targeted git diff --check passed with only existing LF/CRLF conversion notices. The workspace temp directory was empty after validation. No real STT model, cloud endpoint, or model download was used for these tests.

Commands used the existing bundled Windows interpreter with bytecode disabled and workspace-local temporary directories:

```powershell
$env:TEMP = Join-Path (Get-Location).Path 'temp'
$env:TMP = $env:TEMP
$env:PYTHONIOENCODING = 'utf-8'
.\build\windows-portable\python.exe -B dev/test_transcription_metadata.py
.\build\windows-portable\python.exe -B dev/run_cleanup_checks.py
```

## Remaining limits and next review

M2M100 still assumes English and NLLB is not explicitly configured with a source language by Reflow. Removing those assumptions is the next separately approved repair. The new metadata does not prove that a whole recording is monolingual, establish per-segment languages, or guarantee transcription correctness. No language-name/code alias policy, manual override, confidence threshold, source-language UI, or translation quality detector was added.

No live Whisper model, full AI render, GUI, GPU, fresh installation, Linux, or macOS was exercised. Existing bundled-media output tests run as part of the aggregate suite on synthetic fixtures. Provider metadata is retained for later use but is not yet displayed to the user or written to final subtitles/media.

Rollback must reverse this step's coordinated worker/provider/pipeline changes against the preceding working state. Do not reset the entire working tree: earlier approved repairs and unrelated user changes are present.
