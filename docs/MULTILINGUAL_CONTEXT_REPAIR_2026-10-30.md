# Multilingual speech context and connected-speech integrity

Follow-up to the first 30 October audit. No software, model, dependency or
external tool was installed. Existing settings, selected engines and source
media were not deliberately changed. This is not release acceptance.

## Problem and change

XTTS previously split every cue into separate sentences. The retained short
German and Polish cues contain substantial extra material when generated as
isolated fragments. A stronger, already-installed Whisper turbo recognizer
confirms these are not merely errors from the first tiny recognizer. Conversely,
some Italian errors reported by the tiny recognizer disappear with the stronger
one, so its diagnostic output is not treated as ground truth.

The new `core/xtts_text.py` policy preserves short cue context for **German,
French, Hungarian, Korean, Polish, Portuguese and Turkish**, using the loaded
checkpoint's tokenizer and language-specific character limits. It checks the
same stripped/lowercase text used by XTTS inference and keeps fewer than 128
tokens together, subject to the checkpoint's own stricter token limit. Longer
text, missing tokenizer metadata and all other languages retain the established
splitting route. Hindi's existing sampling and tempo recipes remain intact. The speech
text sent to the engine is not rewritten or translated by this policy.

The handler uses this policy in both its legacy execution and the isolated
worker, which imports the same handler. Malformed tokens or a tokenizer failure
cannot replace a preceding good output. The change is subject to the following
tests and actual-provider checks; language quality is not inferred from file
existence alone.

The connected TTS and voice-conversion adapters also had an output-integrity
gap: generic media validation accepted a silent audio stream and published it
before the downstream pipeline could reject it. `write_media` now accepts a
stage-specific validation callback, and both speech adapters require decodable,
non-silent signal before replacing the destination. Generic background-media
downloads retain their previous ability to contain silence. Responses are closed
and pending files removed on success and failure. These checks assess signal,
not whether audio contains the right words.

## Paired speech results and withheld changes

The stronger recognizer evaluated 35 retained takes: 17 baseline samples, 16
continuous-context candidates, and two greedy-decoding controls. These are
short, fixed-reference tests, not 35 languages or a broad pronunciation trial.
All seven adopted routes reduced normalized character error in their paired
case. German, French, Hungarian, Korean, Portuguese and Turkish candidates had
zero normalized character differences from their intended texts. Polish reduced
character error from about 296.6% to 3.4%, with one word/form discrepancy still
reported. Insertion errors can make this diagnostic exceed 100%.

The Czech candidate produced an extra recognized word and was **not adopted**.
Arabic and Chinese comparisons include writing-form/spelling differences that do
not establish a spoken improvement, so those changes were also withheld. English,
Spanish, Italian, Russian, Dutch and Japanese already had exact baseline
recognition in these controls; their splitting settings remain unchanged.

[Complete paired results and adopted-route flags](validation/2026-10-30-context-paired-comparison.json).

## Verification records

- The initial candidate's 29 focused short-cue/XTTS tests passed. Final narrowed
  coverage additionally verifies that held/unaffected languages retain their
  established route, plus token limits, Hindi preservation, malformed tokenizer
  output and atomic failure behavior. Final full-regression results are recorded
  below. [Initial focused log](validation/2026-10-30-xtts-context-focused.log).
- Connected speech fixtures exercise silent, corrupt and valid WAV responses for
  both adapters without a live service or credentials.
  [Focused log](validation/2026-10-30-cloud-speech-focused.log).
- Continuous-context samples now cover all 16 non-Hindi XTTS languages across
  the initial two-case, additional four-case and remaining ten-case runs. These
  experiments preserve the retained baseline files.
  [Remaining-language measurements](validation/2026-10-30-multilingual-speech-continuous-remaining/report.json).
- Stronger ASR compares the retained baseline and candidate recordings using the
  existing converted CPU Whisper turbo model and verified recognition runtime.
  Networking is blocked and model files are loaded locally.
  [Primary diagnostics](validation/2026-10-30-strong-multilingual-content.json),
  [remaining-language diagnostics](validation/2026-10-30-strong-multilingual-remaining-content.json).
- **976 backend tests passed in 316.751 seconds** against the final narrowed
  policy. This includes the new language-gating, token-limit, output-preservation
  and connected-speech tests. Counts overlap the earlier 962/975-test runs and
  must not be added together. [Final regression log](validation/2026-10-30-context-final-backend.log).
- Fresh actual production-provider runs passed in **both legacy and isolated
  execution**, generating German and Korean speech with the final source hashes
  unchanged during each run. The legacy model selected unsplit short-cue delivery;
  the isolated worker reused one process/model for both requests. Both runs
  validated waveform format/timing and normalization, removed their workspaces,
  and confirmed that owned processes exited. These execution checks are distinct
  from recognition accuracy and human listening acceptance.
  [Legacy final receipt](validation/2026-10-30-context-provider-legacy-final/report.json),
  [isolated final receipt](validation/2026-10-30-context-provider-isolated-final/report.json).
- Syntax and whitespace checks passed. Frontend code did not change in this
  follow-up; the first pass's production build and 83 frontend checks remain the
  relevant frontend verification.
- The final [source-bound summary](validation/2026-10-30-context-final-summary.json)
  records the current policy, regression count and successful provider modes.
  Regenerable diagnostic caches were removed after verification; review audio,
  models and prior receipts were retained. [Cleanup receipt](validation/2026-10-30-context-cleanup.json).

## Listening comparisons

These retained fixed-seed benchmark recordings support review; they are not
automatically accepted takes for a user's project.

| Language | Original | Short-context candidate |
| --- | --- | --- |
| German | [Original](validation/2026-10-30-multilingual-speech/de.wav) | [Candidate](validation/2026-10-30-multilingual-speech-continuous/de.wav) |
| French | [Original](validation/2026-10-30-multilingual-speech/fr.wav) | [Candidate](validation/2026-10-30-multilingual-speech-continuous-remaining/fr.wav) |
| Hungarian | [Original](validation/2026-10-30-multilingual-speech/hu.wav) | [Candidate](validation/2026-10-30-multilingual-speech-continuous-remaining/hu.wav) |
| Korean | [Original](validation/2026-10-30-multilingual-speech/ko.wav) | [Candidate](validation/2026-10-30-multilingual-speech-continuous-additional/ko.wav) |
| Polish | [Original](validation/2026-10-30-multilingual-speech/pl.wav) | [Candidate](validation/2026-10-30-multilingual-speech-continuous/pl.wav) |
| Portuguese | [Original](validation/2026-10-30-multilingual-speech/pt.wav) | [Candidate](validation/2026-10-30-multilingual-speech-continuous-additional/pt.wav) |
| Turkish | [Original](validation/2026-10-30-multilingual-speech/tr.wav) | [Candidate](validation/2026-10-30-multilingual-speech-continuous-remaining/tr.wav) |

## Subsequent user listening feedback

The user subsequently reported: “all the dubs loook and sound goood”. This accepts
the dubs they reviewed in this conversation. The exact reviewed file list was
not enumerated, so this feedback is not expanded into approval of every engine,
future generation, unreviewed experimental candidate or release artifact.
Earlier receipts correctly retain their pre-feedback human-acceptance flags.
See [the feedback and remaining release checklist](RELEASE_NEXT_STEPS_2026-10-30.md).

Audio models remain probabilistic. Recognition has its own errors and spelling
conventions, and a small scripted corpus does not establish native pronunciation,
voice similarity or long-form quality. Human listening acceptance now covers the
user-reviewed dubs; broader and release acceptance remain open.
Processing times observed during overlapping diagnostics are not performance
benchmarks. RVC's missing installed voice models and the first audit's remaining
release gates are not represented as solved by this change.
