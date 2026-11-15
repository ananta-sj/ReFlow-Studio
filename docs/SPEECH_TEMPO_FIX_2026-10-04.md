# Accepted speech tempo repair — 4 October 2026

## Problem and evidence

Supplied Hindi references improved the generated speech. User accepted both
exact raw takes (“both are beautiful”) and their loudness-only versions (“yes”),
but atempo-paced derivatives had distortion at Sujata's opening and Abhishek's
ending. Removing extra EQ/compression did not resolve it. Alternate bundled
Rubber Band pacing at the same1.342 tempo was accepted (“beautiful”). This
isolates and repairs a pace-processing problem for these cases; it does not
establish universal voice quality or failure of atempo on every input.

Detailed controls and receipts remain in HINDI_NOISE_REVIEW_2026-10-04.md and
HINDI_TEMPO_COMPARISON_2026-10-04.md. User acceptance is recorded in
`validation/2026-10-04-hindi-tempo.json`, scoped to both presented takes.

## Production changes

`core/pipeline.py`, `ReflowPipeline.speed_change`:

- Uses bundled FFmpeg `rubberband=tempo=<speed>:pitch=1` instead of atempo for
  tempo adjustments. Original-pace speed1 still returns original audio directly.
- Rejects nonnumeric, Boolean, nonfinite and out-of-filter-range speeds before
  invoking a process. Supported filter range0.01–100; existing production
  speech policies continue to use their much narrower approved range.
- Preserves channel count and sample rate explicitly, with the existing16-bit
  PCM output format. Checks decoded duration against input/speed (100ms tolerance)
  and refuses removal of a nonzero signal.
- Measures post-tempo true peak. If above existing−1.2dBTP tolerance, reduces
  gain only toward−1.55dBTP. No extra limiter, compression or normalization pass;
  the correction does not alter pitch, word timing or duration.
- Missing Rubber Band filter gets an actionable error: use the bundled FFmpeg
  or retain original pace. No silent fallback to the rejected atempo route.
  Actual FFmpeg errors and cancellation still propagate through the existing
  cancellable media runner and owned temporary cleanup.

This shared speech helper affects every language/engine using tempo adjustment;
the listening acceptance is Hindi-specific, while pitch/timing regressions cover
acceleration and slowing mechanically. Hindi1.342 pace, other language pace
policy, strict no-word-cut timing guards, model/voice selections, reference
preparation, mastering, generation temperature and seed defaults are unchanged.
In particular, the diagnostic temperature0.90 preference is not a new universal
generation default. Additional EQ/compression remains outside this tempo repair.
Previously accepted saved audio renders from its existing bytes without redoing
tempo; new generation uses the new helper. No old take or user MP3 overwritten.

Rubber Band already exists in this Windows FFmpeg build; no new tool/library,
framework, optional environment, engine or model download. Other FFmpeg builds
must provide that filter when tempo is requested. This is a distribution
capability requirement, not new Linux/macOS acceptance.

## Verification

- `dev/verify_production_tempo.py` feeds the exact accepted loudness-only inputs
  through the production helper. Both results match the approved alternatives
  **sample for sample**, including format: Sujata6.999s, Abhishek5.460s.
  Receipt `validation/2026-10-04-production-tempo.json`; no new model inference.
- Four new regressions in `dev/test_output_integrity.py`: real220Hz tone retains
  dominant pitch within2Hz at speed0.85 and1.342, timing within30ms and true-peak
  tolerance; unsupported filter fails clearly without fallback; invalid speeds
  do not run FFmpeg; pre-cancelled job does not run/leak tempo work.
- Initial focused run:116 tests,115 passed, one cancellation **fixture** error
  calling nonexistent `RenderContext.cancel`. Corrected to existing
  `request_stop`; failed receipt preserved in
  `validation/2026-10-04-tempo-production-focused-before-fixture-fix.log` (original
  focused log also retained). No production failure was established by that error.
- Complete updated backend suite: **487 passed in95.016 seconds**;
  `validation/2026-10-04-tempo-production-backend.log`, including corrected fixture.
- Isolated portable app refreshed:168 files, no size mismatches; existing
  `validation/2026-10-04-portable-app-refresh.json`.
- Hidden desktop cue-review **PASS in30.860 seconds**: native1.500s WAV decoding,
  stop, acceptance persistence, isolated edits, overflow/incomplete blocking and
  no JavaScript errors. `validation/2026-10-04-tempo-production-desktop.json`.
  It suppresses sound/bypasses hidden context-resume permission; no new visible
  layout/audible desktop acceptance claimed. Listening evidence is the user's
  actual presented alternative files, not this desktop fixture.
- Frontend unchanged: retained83 checks/build from earlier iteration, not rerun.
  Whitespace diff check passes. Owned workspaces cleaned; diagnostic evidence kept.

## Limits and next gates

No full automatic dub or fresh AI generation/translation chain was accepted in
this repair. Production helper equivalence certifies the tempo stage on saved
inputs, not every combined mastering/generation path. Remaining work includes
transcript/translation accuracy, consistent varied-text/reference delivery,
timing fit, memory/latency estimates, accepted-track video integration and
clean-machine/platform release acceptance. The public release verdict remains
not ready. No commit, push, deployment or release performed.
