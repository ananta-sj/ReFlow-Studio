# Recognition source-language repair — 2026-10-15

## Result and scope

An explicit source-language choice now reaches speech recognition before
translation, through both the CPU subprocess and the GPU session worker.
The existing confirmed Hindi reference produces Hindi/Devanagari output on
both routes when Hindi is selected. Forced language labels carry no automatic
detection confidence. Recognition recovery distinguishes automatic recognition
from each explicit source-language selection.

This is a pipeline repair, not a new voice-quality tuning experiment. It adds
no package, model, framework, external service call, or default runtime change.
The CPU candidate still requires the existing process-local interpreter
override during evaluation. Production per-feature runtime selection remains
unfinished. The application is not release ready on the strength of this repair.

## Why this repair was necessary

The pipeline accepted a source-language selection but applied it after
recognition returned, when resolving translation and speech languages. Neither
the public local STT provider nor its worker received that choice. Selecting
Hindi therefore could not stop Whisper from detecting Urdu and producing Urdu
script. Both the converted CPU candidate and the original GPU checkpoint had
shown this behavior on the same confirmed Hindi reference.

Recognition checkpoint inputs also omitted the selection. Once recognition is
conditioned on a selected language, omitting it would allow an automatic result
to be incorrectly reused for a subsequent explicitly Hindi run.

## Implementation changes

| Area | Change and purpose |
| --- | --- |
| `core/providers/base.py` | STT contract accepts optional `source_language='auto'`; documents explicit-hint and confidence behavior. |
| `core/recognition_language.py` | Normalizes product source selections and maps Chinese script variants to `zh`, Gurmukhi Punjabi to `pa`, and Javanese `jv` to Whisper's `jw`. Automatic selection returns no hint. |
| `core/pipeline.py` | Both shared audio and video recognition paths pass the selection into `_transcribe_source`; only explicit choices add the provider keyword, preserving automatic-call compatibility. Source-language feedback suppresses automatic-detection labels for hint-origin transcripts. |
| `core/providers/stt/whisper_local.py` | Explicit selections are appended as a separate worker argument, without shell interpolation. Automatic invocation retains the previous argument shape. |
| `core/run_stt.py` | Reads the optional selection argument and passes it into the handler; older invocations default to automatic recognition. |
| `core/stt/stt_handler.py` | Validates explicit hints against the loaded model's supported languages and passes `language` to faster-whisper. Unsupported model/language combinations raise an error instead of substituting another language. |
| `core/providers/stt/whisper_turbo_local.py` | Includes the selection in the session call, including when the provider creates its own job context. Existing worker cleanup remains in `finally`. |
| `core/whisper_turbo_worker.py` | Validates the selected language token against the actual model generation configuration and uses it for generation. Independent masked language-token scores remain in block evidence. |
| `core/transcription.py` | Adds optional `language_origin='hint'`, preserved through normalization, resegmentation and JSON. Hint-origin transcripts always have `language_probability=None`, even if a worker supplies a forced value of 1. Older automatic payload shapes remain unchanged. |
| `core/stage_checkpoints.py` | Recognition inputs include the canonical source selection, including `auto`. Translation checkpoint validation also protects language origin from being dropped or changed. |
| `core/providers/stt/cloud_rest.py` | OpenAI-compatible requests transmit explicit language in the form. Custom endpoints require an explicit `extra.language_field` naming their supported multipart form field. A missing configuration causes a clear error before sending the HTTP request. Saved extras are copied, not mutated. |

Chinese/Punjabi mappings guide the spoken language only. They do not guarantee
a particular written script. Product-menu presence is not a guarantee of model
support; workers check their own vocabulary. No related-language substitution
was added for Hinglish, Nigerian Pidgin, or Western Punjabi.

Existing recognition cache entries lack the new source-selection field and
will not match newly calculated keys, including automatic runs. This is an
intentional one-time recomputation; no cache directory was deleted.

## Verification and evidence

### Real offline worker checks

`dev/evaluate_recognition_language.py` runs each public provider from the clean
desktop parent using the existing runtime/model files. It uses disposable owned
job folders, offline model flags, and blocks network name resolution in the
parent. The existing worker implementations also use local/offline model loads.
No cloud recognizer was contacted.

- `validation/2026-10-15-recognition-language-cpu.json`: all nine checks passed.
- `validation/2026-10-15-recognition-language-gpu.json`: all nine checks passed.

Both receipts verify the reference audio hash, explicit Hindi label,
hint-origin/null-confidence metadata, Devanagari text, absence of Urdu script,
nonempty timed speech, worker release, a Torch-free desktop parent, and removal
of the owned job workspace. The CPU segment ends at 7.46 seconds and the GPU
segment at 7.44 seconds. These checks establish integration and script behavior;
they do not establish perfect transcription or natural synthesized delivery.

The GPU retains independent automatic detection of `ur` with probability
0.8949387073516846 for this clip. This evidence is deliberately distinct from
the chosen Hindi recognition language. Automatic detection is still a quality
limitation; the patch does not relabel that detection as Hindi or claim to fix it.

### Regression tests

- `validation/2026-10-15-recognition-language-full-backend.log`: **815 tests
  passed**, 106.807 seconds, in the existing shared runtime. This suite was
  loaded before four additional tests were added.
- `validation/2026-10-15-recognition-language-desktop-scoped.log`: **79 tests
  passed**, 3.292 seconds, including the four subsequent tests. Covers source
  hints, metadata serialization, checkpoints, local-worker arguments, mocked
  cloud requests, GPU-provider lifetime and handler import boundaries.
- Tests specifically prove identical Hindi aliases reuse recognition while an
  automatic request recomputes it, hint origin survives cached round trips,
  translation checkpoints reject dropped origin, unsupported model languages
  fail clearly, and the handler forwards `language='hi'` without importing Torch.

Counts overlap and must not be added together as distinct test coverage.
Cloud tests use mocked HTTP responses; no cloud capability or quality has been
validated against a live service.

### Failed attempts retained

`validation/2026-10-15-recognition-language-focused.log` records the initial
122-test run with 16 permission errors involving the sandbox's temporary
directory. The corrected full suite uses the workspace temporary directory and
passed. This was an execution-environment issue, not a reason to weaken tests.

`validation/2026-10-15-recognition-language-desktop-regressions.log` records a
broader desktop attempt: 127 tests, two failures and one error. Those three
tests require faster-whisper or Torch in the desktop parent. The small desktop
candidate intentionally lacks those engines, and production per-feature
routing is still incomplete. The later scoped pass excludes that provider
test module explicitly; it does not convert the broader failure into a pass.

## Preservation and candidate metadata

Historical conversion and acceptance receipts remain unchanged. The recognition
candidate profile's handler/worker bindings must track the repaired source;
its new hint-evaluation receipt is recorded separately from the earlier
candidate acceptance. Automatic Hindi detection remains unverified/failed and
release eligibility remains false. Installed-package/state verification is
recorded in `validation/2026-10-15-recognition-candidate-file-integrity-after-language-hints.json`.
That historical verifier reports `passed=false` solely because the deliberately
changed `core/pipeline.py` differs from its October 13 source hash. All five
other preservation checks pass, including all 2,316 installed payload files.
`validation/2026-10-15-recognition-language-acceptance.json` records this exact
expected source change, verifies the remaining historical source hashes and
original/converted Whisper hashes, and binds the new tests to current source.
The earlier failed comparison is retained; its baseline is not rewritten.
The first finalization attempt also retained a failure log after resolving a
conversion-manifest path relative to `model/` instead of the conversion root.
No profile or acceptance receipt was written in that failed attempt. The
corrected root passed full original/converted asset hash verification; its log
is `validation/2026-10-15-recognition-language-finalization-corrected.log`.

No model weights or installed packages were changed. The working app settings,
model registry, user outputs, original voice references and previous runtime
defaults were preserved. No Ollama reinstall or paid model call was performed.

## What remains

1. Integrate per-feature runtime selection and preflight so a clean desktop
   launches recognition in its own verified runtime without a global override.
2. Evaluate automatic language ambiguity and recognition accuracy on more than
   one Hindi reference, including long, noisy and multilingual sources. An
   explicit source choice guides decoding; it is not an accuracy guarantee.
3. Complete the other engine runtime migrations and full video workflow gates.
4. Resolve owner licensing, remaining third-party notices and redistribution
   requirements before producing a public release.

No default migration, release approval or public distribution is implied by
the passing checks in this iteration.
