# Translation failure handling — 2026-10-03

## Approval and scope

The user approved the first translation proposal step: request timeouts and HTTP
checks, strict text responses, propagated loading/inference errors, safe prefix
cleanup, explicit language/model selection, contextual errors, visible existing
fallback, regression tests, and documentation.

Source-language handling, approximate target mappings, and instruction support
are the separately proposed language-capabilities step. They were not changed.
No tools, frameworks, dependencies, models, or downloads were added. No live
translation endpoints or model inference were invoked for validation. Existing
user edits and earlier repairs were preserved. No commit, push, deployment, or
release was performed.

## Problems addressed

- Ollama generation had no timeout and did not raise for non-success HTTP status.
- Ollama/M2M100 initialization or translation failures could return source text.
- Ollama discovery could select the first installed model instead of the
  requested one, including a potentially unrelated model.
- Unknown language codes/names silently defaulted to English.
- Empty or non-string provider output could reach subtitle/speech processing.
- Custom API JSON arrays/numbers could become literal string representations.
- Broad colon splitting destroyed valid translation content. The inspection
  reproduced `Here is the translation: Meet at 10:30` becoming `30`.
- Existing fallback to M2M100 was console-only and did not reliably communicate
  failure when that fallback could not load or translate.

## Changes by file

### `core/providers/base.py`

Added `require_translation_text(value)` to the existing provider module. It
requires a string containing non-whitespace content and returns its trimmed
text. Lists, dictionaries, numbers, null values, and blank strings are rejected.
It does not reject text merely because it equals the input; names and some
phrases legitimately remain unchanged.

### `core/llm_translator.py`

**Discovery and model selection**

- Ollama discovery uses `(3, 3)` connection/read timeouts and HTTP status checks.
- Validate the model inventory as a dictionary containing a list of entries
  with string names.
- Match the requested model exactly, allowing the untagged request to resolve
  to its explicit `:latest` name. Do not use substring matching or substitute
  the first available model/tag.
- Missing requested models, malformed inventories, invalid JSON, and discovery
  HTTP errors now fail clearly. They do not trigger arbitrary model selection.
- Retain up to three discovery attempts for connection errors and timeouts,
  with one-second pauses between attempts. Exhaustion invokes the existing
  M2M100 fallback with a warning.

**Generation and response handling**

- Ollama generation uses `(5, 120)` connection/read timeouts and checked status.
- Retain existing fallback on request failures, including HTTP errors, but emit
  an explicit warning. A generation-time missing/deleted model can therefore
  fall back; a model absent during initial discovery fails directly.
- Validate response JSON, reject reported error payloads, and require a
  nonempty response string. Malformed successful responses fail rather than
  masquerade as translations or invoke a hidden fallback.
- Remove only the exact leading English prefix `Here is the translation:`
  (case-insensitive), then validate the remaining text. Colons elsewhere and
  valid timestamps remain intact. This is deliberately not a general LLM
  commentary parser.
- Reject unknown target display names instead of choosing English. Blank
  source text returns unchanged without a generation request.

**M2M100 and fallback**

- Load transformers' M2M100 classes lazily inside the initializer. Ollama-only
  operation no longer needs those classes imported by this module at startup.
- Mark M2M100 ready only after tokenizer/model loading and model setup succeed.
- Raise initialization failures and preserve their causes instead of leaving a
  broken engine that returns source text.
- Reject a broken/uninitialized engine explicitly.
- Raise generation/decoding failures and require valid decoded text.
- Combine the triggering Ollama failure and failed fallback initialization in
  the error when both fail.
- Log and optionally deliver a UI fallback warning. It explains that missing
  M2M100 weights can download on first use, preserving the earlier approved
  on-demand model-recovery behavior. No such download occurs in these tests.

The existing model identifier, cache location, device selection, English-source
assumption, target mappings, and generation behavior otherwise remain. Local
model loading/generation is not protected by a new hard execution deadline.

### `core/providers/translation/ollama_m2m100_local.py`

Skip blank text before constructing a translator. Pass a callback that sends
fallback warnings through the existing `bridge.push` log event. Preserve lazy
construction/caching and propagate the translator's errors.

### `core/providers/translation/cloud_rest.py`

- Apply explicit `(5, 120)` timeouts through the existing checked HTTP helper.
- Validate chat JSON and its `choices[0].message.content` structure before
  accepting text. Invalid JSON/shape gets an actionable response error.
- For custom endpoints, accept either a JSON string or the configured string
  field of a JSON dictionary. Reject missing fields, arrays, numeric values,
  nulls, and blank/non-string field content; never stringify arbitrary JSON.
- Preserve the configured response field, request templates, authentication,
  presets, and API/model defaults.
- Skip blank input and validate the final adapter result.

No new vendor SDK or API integration was introduced; the existing generic
chat/custom adapters were repaired in place.

### `core/providers/translation/nllb_local.py`

Require a nonempty decoded string. Retain model/tokenizer loading, language
token validation, local-files-only behavior, and language mappings. Errors
already raised by loading/generation continue to propagate.

### `core/providers/translation/airllm_local.py`

Skip blank input before loading and require a nonempty decoded string. Retain
the existing model, offloading/compression configuration, prompt token slicing,
and generation settings.

### `core/pipeline.py`

- Add `_translation_target()` to resolve known codes without silently choosing
  English.
- Validate the requested target in `run()` before executing any template, except
  the existing intentional `source` bypass. Direct template translation paths
  also use strict lookup.
- Validate translation results at the pipeline boundary so every provider,
  including a future/custom implementation, must return usable text.
- Preserve legitimate blank text without calling a translation provider.
- Wrap translation errors with target and one-based `Segment N` or
  `Subtitle cue N` context at all three translation call sites.
- Preserve the separate optional profanity-filter call after translation.
  Filtering failure/fallback/output policy is outside this step; the translation
  validator does not claim to validate that stage's result.

## Validation

Added `dev/test_translation_integrity.py` and registered it in the existing
nondestructive backend runner. Its **31 tests** cover:

- Exact/default-tag matching, missing requested models, malformed inventory,
  discovery status failures, timeout settings, and discovery retries.
- Fallback warning delivery, successful simulated recovery, failed recovery,
  broken engine states, and model-loader/generation failure propagation.
- Blank input, non-string/empty outputs, malformed JSON, error payloads,
  unchanged text, anchored prefix removal, and embedded colons.
- Checked cloud adapter response shapes, custom fields/JSON strings, rejection
  of JSON lists/numbers/nulls, and explicit timeout arguments.
- Pipeline target rejection before template execution and segment/cue context.
- Empty simulated NLLB and AirLLM output rejection.

All HTTP calls are mocked. Model initialization/generation boundaries are
mocked, including an execution of the real M2M100 initializer with a failing
mocked loader. Early test runs exposed incorrect tokenizer mock shapes and a
patch-lifecycle mistake in that initializer test; the fixtures were corrected.
These failures did not trigger real downloads or model inference.

Reproduce from the workspace root in PowerShell:

```powershell
$env:TEMP = Join-Path (Get-Location).Path 'temp'
$env:TMP = $env:TEMP
$env:PYTHONIOENCODING = 'utf-8'
.\build\windows-portable\python.exe -B dev/run_cleanup_checks.py
```

Final aggregate result: **134 tests passed**, exit code 0, approximately 15.3
seconds of reported test execution. This includes the previous 103 backend
checks and 31 new translation checks. The bundled Windows CPython 3.10.11
interpreter ran with bytecode writing disabled.

Eight syntax parses passed, covering seven changed production modules and the
new test file. `git diff --check` passed for the changed production files;
Git emitted its configured LF-to-CRLF notices. No complete AI render, live
Ollama/cloud request, actual M2M100/NLLB/AirLLM inference, GUI run, GPU run,
fresh installation, or other-platform validation was performed.

## Files changed

| File | Purpose |
| --- | --- |
| `core/providers/base.py` | Shared strict text-result validation |
| `core/llm_translator.py` | Ollama discovery/requests, explicit failures, visible M2M100 fallback |
| `core/providers/translation/ollama_m2m100_local.py` | UI warning delivery and blank-input handling |
| `core/providers/translation/cloud_rest.py` | Request timeouts and response schema validation |
| `core/providers/translation/nllb_local.py` | Decoded text validation |
| `core/providers/translation/airllm_local.py` | Blank input and decoded text validation |
| `core/pipeline.py` | Strict targets, text validation, contextual errors |
| `dev/test_translation_integrity.py` | 31 isolated regression checks |
| `dev/run_cleanup_checks.py` | Include translation tests |
| `docs/TRANSLATION_INTEGRITY_REPORT_2026-10-03.md` | This detailed record |

Diffs against HEAD include earlier user and approved changes, especially in the
pipeline. This report records the current step's scope.

## Limits and separately approved next step

Requests timeouts are connection/read limits, not a hard total duration budget;
a server repeatedly delivering data or retries/fallback may extend the total
operation. Local model loading/inference also retains its existing execution
and cancellation limits.

Nonempty output is not proof of accurate translation, correct language, or
instruction compliance. Identical text is accepted intentionally. This step
does not automatically detect semantic refusals or all explanatory chatter.

M2M100 still assumes English source text. Its existing approximate mappings,
including Telugu-to-Kannada and Nigerian-Pidgin-to-English, remain untouched.
NLLB's existing Hinglish-to-Hindi approximation also remains. Local seq2seq
engines still cannot honor custom instructions in their current implementations.
LLM prompting does not establish that every model supports every listed language.

Those known capability issues need a separately approved policy for source
language, unsupported targets, approximations, and instruction support. Optional
filtering and stem-export repairs also remain independently scoped work.
