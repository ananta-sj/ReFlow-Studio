# Speech language backend safeguards — 2026-10-03

## Authorization and scope

The user approved step 1 of the speech compatibility plan: backend XTTS checks,
resolved source speech, checks for the routes actually used, regression tests,
and detailed documentation. This step uses existing dependencies. It does not
install tools, restore frontend dependencies, download real model weights, call
cloud services, rebuild the interface, commit, or publish changes.

The workspace already contained substantial uncommitted work. The changes below
are incremental; a diff against Git HEAD includes earlier work and must not be
treated as this step's complete change list.

## Problems and resulting behavior

| Trigger | Previous behavior | New behavior |
| --- | --- | --- |
| Bengali selected with default XTTS | Unsupported language reached engine loading/inference | Explicit compatibility error before downloads/loading; homogeneous XTTS casts fail before media preparation |
| Mandarin selected as `zh` | Product code passed directly to XTTS | XTTS receives `zh-cn` |
| Keep source language | Literal `source` passed to XTTS and rejected | Concrete manual or confidently detected source code passed to synthesis; transcription text stays unchanged |
| Missing/low-confidence source metadata in source mode | Failure deferred until XTTS synthesis | Clear request to select a source manually or obtain reliable detection, after STT and before generation |
| Custom local checkpoint | No architecture/language check | Its `config.json` must declare `model: xtts` and a nonempty list of language codes; unsupported languages, unreadable JSON, and missing configs fail clearly |
| F5-only assigned dialogue | Base XTTS compatibility could incorrectly constrain a separate generator | No XTTS language check for those assignments |
| Mixed cast, blank or unassigned XTTS voice | A cast-wide check would reject an unused route | Early check deferred; actual nonblank segment assignments checked after STT |
| Cloud voice conversion carrying an F5 marker | Segment branch could differ from resolver's cloud-first ordering | Cloud conversion uses base TTS, matching resolver precedence |

RVC and cloud audio-to-audio voice conversion still rely on base TTS language
coverage. Cloud TTS and F5 language capabilities are **unverified**, not certified
by skipping XTTS checks. Their settings/capability work remains a separate step.

## Language evidence and policy

The retained `models/xtts/default/config.json` declares architecture `xtts` and
17 engine codes: `en es fr de it pt pl tr ru nl cs ar zh-cn hu ko ja hi`.
Of the current 24 product targets, 13 match after the Chinese alias:
English, Mandarin Chinese, Hindi, Spanish, Standard Arabic, French, Japanese,
Portuguese, Russian, German, Korean, Turkish, and Italian.

The other 11 targets are rejected by this checkpoint: Hinglish, Bengali,
Indonesian, Nigerian Pidgin, Tamil, Kannada, Western Punjabi, Vietnamese,
Marathi, Telugu, and Javanese. Related-language substitutions are not used.

For source speech, generic Chinese, Simplified Chinese, and Traditional Chinese
all map to XTTS's language code `zh-cn`; the original transcription text/script
is preserved. This is speech routing, not a script conversion or a claim about
pronunciation quality.

Manual source selection takes precedence. Automatic source resolution reuses
the existing recognized-label and confidence policy (at least 0.80). Missing,
unknown, or lower-confidence labels cannot establish the speech language.
The source catalog remains unchanged; languages outside that catalog cannot
currently resolve in source mode even if an XTTS checkpoint supports them.
The whole clip's language metadata does not identify per-segment language
changes; mixed-language speech accuracy is not established by these checks.

When the default config is absent, a lightweight declared XTTS-v2 language list
allows pre-download checks. An existing config is authoritative. After default
assets are obtained, the actual config is checked before engine construction.
Custom checkpoints never use the default list to replace missing/broken config.
These checks validate declared architecture and coverage, not weight authenticity
or whether a checkpoint produces correct speech.

## Implementation and timing

1. Dubbing generators run a lightweight early check before janitor cleanup,
   extraction, separation, or STT when a concrete speech language is known and
   all possible voices use base TTS. Auto/source and casts containing F5 defer.
2. After STT, video and audio paths resolve source mode and check actors assigned
   to nonblank segments using the existing round-robin cast assignment. This
   happens before translation and speech model downloads/loading. Media/STT work
   may already have occurred for deferred cases.
3. Dubbing receives the concrete speech code while output naming still reflects
   the requested target (`SOURCE` for keep-source jobs).
4. Each base-TTS segment repeats preflight before synthesis, preserving segment
   and voice error context from the earlier speech integrity work.
5. XTTS provider checks and normalizes the code before constructing its lazy
   handler. The handler checks before asset acquisition and against the actual
   config before engine construction when given a language. Generation checks
   again, including direct handler calls.

Direct handler construction without a language preserves the existing interface;
it cannot preflight an unspecified future target. Its generation call still
checks coverage. Direct provider calls must supply an explicit engine/product
language; literal `source` continues to be rejected there because the provider
has no transcription context.

Subtitle-only translation does not enter any of these speech checks. The shared
transcription/translation helper retains its previous behavior when the optional
speech cast argument is absent.

## Files changed in this step

| File | Change |
| --- | --- |
| `core/speech_language.py` | New lightweight source speech resolution, XTTS config validation/alias mapping, actor routing, and preflight helpers |
| `core/pipeline.py` | Early and transcript-aware checks, concrete language forwarding, per-segment guard, consistent cloud/F5 precedence |
| `core/providers/tts/xtts_local.py` | Validate before lazy handler construction and pass normalized language into initialization |
| `core/tts/tts_handler.py` | Optional initialization language; pre/post asset checks and generation guard |
| `dev/test_speech_language.py` | 15 regression tests with model and external boundaries mocked |
| `dev/run_cleanup_checks.py` | Include new test module in existing aggregate suite |
| `dev/test_speech_integrity.py` | Replace empty fake XTTS config with valid declared architecture/languages; provide concrete mock registry responses |
| `dev/test_source_language.py` | Supply concrete empty registry selections for existing pipeline fixtures |
| `dev/test_output_integrity.py` | Supply concrete registry responses and metadata-bearing mock transcription for source-mode output preservation test |
| This report and `docs/validation/2026-10-03-speech-language.log` | Detailed change record and final aggregate validation output |

## Verification

Final aggregate: **242 tests passed in 28.143 seconds**, exit code 0 (227 existing
checks plus 15 new checks). All nine edited/new Python files parsed successfully.
Scoped Git whitespace checks passed, with the existing Windows line-ending
conversion notice for the XTTS provider.

New checks cover Chinese aliases, authoritative custom coverage, broken/missing
configs, default pre-download contract, manual/confident/unknown source cases,
provider rejection before handler construction, handler rejection before asset
download, F5-only/cloud-base bypass, cloud voice marker precedence, actual
nonblank assignments, compatibility before translation, rejection before janitor
cleanup, source language forwarding through both actual dubbing generators, and
mixed-cast deferred checks. Existing tests retain real synthetic-audio decoding
and FFmpeg output preservation coverage; AI inference boundaries are simulated.

Initial runs exposed invalid old fixtures (empty checkpoint configuration and
unconfigured registry mocks), and a wrong class name in the new test. Those were
corrected; production requirements were not relaxed to accept invalid fixtures.
The final validation log is retained. Temporary test directories were removed
by fixture cleanup; no dependency cache or model weights were introduced.

Reproduce from the workspace in PowerShell:

```powershell
$env:TEMP = Join-Path (Get-Location).Path 'temp'
$env:TMP = $env:TEMP
$env:PYTHONIOENCODING = 'utf-8'
.\build\windows-portable\python.exe -B dev/run_cleanup_checks.py
```

## Limits and recovery

No real XTTS/F5/RVC inference, model download, GPU recovery, cloud request, live
GUI interaction, fresh installation, or Linux/macOS run was performed. The
frontend still shows its existing language catalog; actionable errors are
delivered through the current backend render error path. Runtime weight checks,
pronunciation quality, and model concurrency safety remain outside this step.

Recovery must preserve previous approved and user changes: selectively remove
this step's imports/checks/forwarding and restore the prior target forwarding,
provider/handler signatures, and test fixtures if needed. Do not reset these
files to Git HEAD, which would erase earlier work. Removing the new helper alone
would break imports. Removing guards restores the late failures described above.

Next proposed scope: inspect and repair cloud/F5 settings and explicit capability
declarations, with separate approval before changes or dependency installation.
