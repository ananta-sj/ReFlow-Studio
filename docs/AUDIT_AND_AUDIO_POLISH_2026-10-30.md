# Project audit and audio polish — 30 October 2026

The subsequent [multilingual context and connected-speech repair](MULTILINGUAL_CONTEXT_REPAIR_2026-10-30.md)
continues this work. The counts and decisions below describe the first pass.

This is a completed code audit/repair pass, not a declaration that every engine,
language, media file or clean-machine installation is release-ready. No package,
model, framework or external tool was installed. No release was published.
The workspace already contained extensive modified and untracked work; it was
preserved rather than reset, committed wholesale or treated as disposable.

## Repairs made in this pass

- Generated cloned speech in every language, including connected cloud speech,
  and F5 speech now use the measured loudness treatment previously limited to
  cloned Hindi. This avoids the extra compressor and treble overlay. Reviewed
  native IndicF5 delivery still bypasses further mastering. RVC retains its
  existing mastering treatment. Hindi's decoding and tempo recipes are unchanged.
- Mastering publishes its result only after the loudness pass succeeds. A failed
  pass preserves the preceding clip. Audio reads in the mastering/reference
  helpers now close their input streams explicitly.
- Voice/background mixing reserves headroom before integer PCM addition, avoiding
  irreversible clipping when both tracks are loud. This is gain-only protection;
  it does not repair distortion already present in an input recording.
- Native credential-store errors now become clear application errors rather than
  leaking platform exceptions. Failed deletion cannot report success while the
  credential remains. There is no plaintext storage fallback. Tests explicitly
  report an unavailable OS store as a skip rather than silently passing it.
- The color picker no longer lets a square press also change the hue ring. Its
  text field follows external changes/reset, and cancelled pointer drags end.
- Nodes resource estimates refresh after processor or render-setting changes.
  Chart animation effects now include their changing inputs; tooltip animation
  updates occur in an effect instead of mutating the animation during rendering.
- Personal `ui_preferences.json` is excluded from version control.

## Verification

- **962 backend tests passed in 264.043 seconds** in the existing portable
  interpreter. The final run had access to the temporary localhost connections
  used by its integration fixtures. Two historical standalone scripts that
  download fixtures or mutate app state remain excluded from unit discovery.
  [Final backend log](validation/2026-10-30-backend-final.log).
- **83 frontend contract checks passed** across architecture/parameter routing,
  cancellation, deletion previews, job state, ordered settings saves and source
  language/preferences. A stale browser-storage fixture was updated to exercise
  the current app-owned preference store.
  [Frontend checks](validation/2026-10-30-frontend-checks.log).
- TypeScript and the production frontend build passed.
  [Build log](validation/2026-10-30-frontend-build.log).
  Lint reports warnings, with no errors. Remaining warnings include development
  hot-refresh exports, the deliberately caller-supplied path-metrics dependency
  list, and graph-request ref cleanup. The build still reports a large bundle and
  an ineffective dynamic import; these are not claimed to be resolved.
  [Lint log](validation/2026-10-30-frontend-lint-final.log).
- The initial unrestricted-cache test invocation failed extensively because its
  temporary paths, cache locations and network access did not match this execution
  environment. Those failures remain in the earlier logs. The repeatable
  `dev/run_backend_checks.py` uses workspace-owned temporary caches and existing
  bundled FFmpeg. Additional failures exposed the credential error handling and
  two tests' dependence on the ambient offline flag; both were corrected before
  the final passing run. Historical failed logs were retained.

## Actual multilingual speech, distinct from simulated engine tests

The existing XTTS checkpoint generated a short sample in each of its 17 supported
languages: English, Spanish, French, German, Italian, Portuguese, Polish, Turkish,
Russian, Dutch, Czech, Arabic, Chinese, Hungarian, Korean, Japanese and Hindi.
The same six-second source reference was used throughout, extracted from the
existing `Sample/2.mp4`. Generation ran offline, on CPU, with the same fixed seed
and the existing per-language sampling settings. No translation stage was used.

All 17 samples decoded, contained signal, retained their timeline/sample format
through loudness processing, and passed the -1.2 dBTP peak acceptance ceiling.
The complete job workspace was removed. These are signal/publication checks,
not pronunciation approval or a timing-fit test against a real dubbed video.

[Audio/report directory](validation/2026-10-30-multilingual-speech/),
[technical measurements](validation/2026-10-30-multilingual-speech/report.json),
[existing tiny-ASR diagnostics](validation/2026-10-30-multilingual-speech/asr-diagnostic.json).

The diagnostics flag likely content problems, especially extra material in the
German, Polish and Korean samples. The small recognizer also makes errors of its
own, including script/transliteration errors; its output cannot certify the words
or native pronunciation. Human listening acceptance remains **false**.

Copying Hindi's greedy decoding to German and Polish was tested separately,
without changing production defaults. It did not consistently remove unwanted
material, and increased their clip lengths in this comparison. It was therefore
not promoted. Generating the two phrases continuously reduced their excessive
durations, but ASR still reported wording/ending discrepancies. Further continuous
comparisons are retained separately. These experiments do not justify a universal
language recipe or automatic replacement of working generation settings.

The additional continuous English, Korean, Italian and Portuguese samples also
passed signal/timeline checks. Korean shortened from 12.993 to 5.153 seconds and
the tiny recognizer reported substantially less extra material. English remained
recognizable; Italian/Portuguese diagnostics still contain wording discrepancies.
This is a promising candidate for a later listening comparison, not a promoted
default. [Additional comparison](validation/2026-10-30-multilingual-speech-continuous-additional/report.json),
[diagnostics](validation/2026-10-30-multilingual-speech-continuous-additional/asr-diagnostic.json).

## Cleanup and current limits

The cleanup removed 23 verified regenerable cache directories/files, totaling
1,790,317 bytes, with resolved workspace-boundary and reparse-point checks.
Models, original media, outputs, installed runtimes, source, saved state and
historical validation records were retained.
[Cleanup receipt](validation/2026-10-30-cache-cleanup.json).
After the final frontend rerun, its regenerated test copies and the owned ASR
cache were removed again. [Final cleanup receipt](validation/2026-10-30-final-cache-cleanup.json).

The current registry has 37 voice entries and zero installed voice entries.
Actual RVC conversion across these voices therefore could not be accepted;
simulated conversion/cancellation tests are not substituted for real voice models.
The multilingual run tests XTTS, not 17 independent speech engines. F5, IndicF5,
cloud APIs, voice conversion and visual engines keep their own capabilities and
limitations. No paid cloud call or new full visual-engine acceptance was performed.

The read-only portable inventory measures the present default core at
2,824,731,999 bytes. Correction: the earlier 500 MB target had already been
withdrawn, as recorded in the release-readiness ledger; it is not a release gate.
Final packaging still needs consistent runtime ownership and an accurate size
inventory. Unused-looking runtime DLLs/packages were not deleted speculatively.
[Portable inventory](validation/2026-10-30-portable-inventory.json).

Release work still needs native-speaker/voice-reference acceptance, longer/noisy
and multispeaker cases, real installed voice-conversion models, broader engine
execution, and fresh relocated/clean-machine/manual UI acceptance. The broken
local `.venv` shortcut was observed; the verified checks use the bundled Python.
It was not silently rebuilt or replaced. A passing suite is not a zero-bug claim.
