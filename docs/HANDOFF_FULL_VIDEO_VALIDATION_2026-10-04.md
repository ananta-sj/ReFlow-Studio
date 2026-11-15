# ReFlow Studio: detailed engineering handoff

Snapshot: 4 October 2026, Asia/Calcutta. Workspace: `C:\Projects\Reflow Studio`.

**Latest 6 October outcome (supersedes the next historical notes):** the user
accepted the 52-second IndicF5/Abhishek Hindi diagnostic video as "it's actually
quite good...". A distinct IndicF5 backend provider is now implemented and the
normal video pipeline completed all eight cues using the existing isolated GPU
runtime. Its complete 24 kHz speech timeline matches the reviewed diagnostic
sample for sample. One worker was reused and released, full decoding passed,
and source preservation/workspace cleanup passed. No user default or model
connection was changed. The combined regression run passed 129 tests; the latest
targeted checks passed 20 tests, including cp1252 RVC initialization.

Read `docs/INDICF5_APP_INTEGRATION_2026-10-06.md` first for implementation and
receipts. Recognition and translation in this backend video test used reviewed
fixtures; live automatic translation, background preservation, user-facing
reference confirmation/selection, runtime packaging, additional material and
release platforms remain unvalidated. This is a successful reviewed-script
backend workflow, not full product release approval. Earlier XTTS failures and
rejected long IndicF5 takes remain valid historical evidence.

**Subsequent controls iteration:** Marketplace → TTS now exposes prepared Hindi
references with playback, transcript confirmation and a separate Hindi speech
processor choice. Bridge connection, reference/runtime activation checks,
XTTS-free IndicF5 startup and exact cue-review reference preservation are
implemented. Existing user defaults are unchanged. Build and backend regression
checks passed. Read `docs/INDICF5_CONTROLS_ITERATION_2026-10-06.md` for the flow,
test counts, limitations and background-run result before continuing.
The new background-enabled 52-second render completed all eight cues, exported
stems and passed full decoding, source preservation and cleanup in 463.484
seconds. Receipt: `docs/validation/2026-10-06-indicf5-app-video-2918783c.json`.
Background/source-dialogue separation quality still needs listening review;
the retained Hindi subtitle stream has an incorrect English language tag.
Subsequent listening feedback, "no english leaks", accepts original-English
suppression for this exact video. See
`docs/validation/2026-10-06-indicf5-background-listening-review.json`.
Music/ambience preservation and separation-noise quality remain separate gates.

**8 October translation follow-up:** NLLB context/decoding comparison found no
reliable semantic repair; defaults remain unchanged. Local NLLB/M2M100 now
reject oversized/unfinished translation output. The single-voice audio review
workspace can combine adjacent phrases before retranslating. Regression checks
and frontend build passed; both real models exercised completion guards. Read
`docs/HINDI_TRANSLATION_ITERATION_2026-10-08.md` for exact receipts, failed test
history and runtime limitations. IndicTrans2 evaluation is proposed but not
approved or installed; the toolkit's native Windows compatibility must first
be addressed. Automatic translation fidelity remains a release blocker.

**6 October follow-up:** current cue generation and the unprocessed-reference
control were rejected by the user for non-Hindi intelligibility. A same-model
comparison reproduces the accepted Abhishek question exactly and the rejected
line exactly, with correct Hindi input tokens. Thus greedy decoding does not
establish general Hindi reliability. See
`docs/CURRENT_VIDEO_CUE_RETEST_2026-10-06.md` and the new dated receipts before
resuming. The original snapshot below remains historical; full-video work is
deferred while this speech-quality blocker is investigated.

Further 6 October diagnostics tested punctuation and lower repetition penalties
without changing production. No reliable repair was established; the cached
Whisper tiny recognizer also cannot certify Hindi quality. The proposed next
step is an isolated IndicF5 evaluation, requiring user approval and potentially
model-access acceptance. See `docs/HINDI_GENERATION_INVESTIGATION_2026-10-06.md`.

## 1. Current outcome and assignment

The latest Hindi decoding and cloned-voice processing repair is implemented and verified. The user accepted the retained Sujata and Abhishek question/meeting samples before and after processing. The complete backend suite passed **493 checks**. One fresh production Sujata synthesis reproduced its approved raw output and processed PCM exactly.

**The full video workflow is not yet validated, and this is not a release-ready declaration.** The retained 44-second moving-video run failed on a cue that could not fit without cutting words. That run predates the latest native sample-rate and greedy-decoding repairs. No fresh complete video run has established their effect on that failure.

The user's standing assignment is to continue iterating until the full video workflow is validated. Their most recent request is this detailed handoff. This handoff does not start a new render, install a dependency, create another chat, or publish anything.

The next useful action is a narrowly scoped test of the retained failing cue under current production behavior, followed by reference-preparation checks and a fresh complete workflow. Preserve historical evidence and distinguish an automatic pipeline result from any reviewed-script result.

## 2. User intent, decisions and authorization

- Original goal: clean unnecessary heavy files, caches and replaceable model weights, initially aiming at approximately 500 MB. **The user explicitly withdrew the size target.** Product quality now leads; do not dismantle the working runtime to pursue that abandoned target.
- Priority: **better translation and voice quality first**, then a reliable complete product with nodes, parallel processing, resource estimates, model download and all advertised features.
- Replaceable downloadable models may be removed when appropriate. Preserve source videos, rendered outputs and custom or unverifiably replaceable voice assets. This handoff requires no deletion.
- Broad project audit and ongoing repairs are authorized. The user previously requested approval before changes and later authorized continued auditing/fixing without repeatedly stopping. Continue routine repairs within that established scope, while explaining meaningful changes.
- **Ask before adding a new tool, framework or engine.** Explain what it does and why it is needed. Separate optional environments and required packages for F5, NudeNet and MuseTalk were specifically approved. That is not approval for unrelated engines such as IndicF5 or AirLLM.
- No release, deployment, commit or push is authorized by the current request. Do not treat “yes,” “ok,” or listening acceptance as blanket approval for these actions.
- Do not automatically accept new generated takes on the user's behalf. Prior approval applies to the identified recordings and contexts.

The user asked whether manual intervention would be needed before continuing. Technical execution, diagnostics and authorized repairs can proceed autonomously. Human help remains necessary for ambiguous English wording, Hindi meaning/naturalness and final video listening/viewing. Consolidate these into meaningful checkpoints; do not repeatedly request approval for routine tests.

## 3. Checkout and runtime

| Item | Observed state |
| --- | --- |
| Local branch / HEAD | `master` / `d3408a5` at handoff creation |
| Remote configuration | `git remote -v` returned no entries; do not assume a push target |
| User-provided upstream reference | https://github.com/ananta-sj/ReFlow-Studio |
| Runtime | `build/windows-portable/python.exe`, Python **3.10.11**, not the recalled 3.11.12 |
| Inference hardware evidenced | Local Windows CPU; current Torch runtime is CPU-only |
| Media tools | Bundled `ffmpeg/bin/ffmpeg.exe`; RubberBand filter available |
| Cached test engines | Whisper tiny, NLLB translation, XTTS through isolated fixture registry |
| Owned QA application | `dist/portable-architecture-check` |
| Running work | No known pending validation job at this handoff snapshot |

The checkout contains extensive tracked modifications and untracked implementation, diagnostics, reports and media from the iteration. HEAD does not represent the current working implementation. **Do not reset, stash, clean or overwrite the checkout to obtain a clean baseline.** Inspect relevant diffs and preserve existing work. No commit was created for this handoff.

The original voice sources remain at:

- `C:\Users\19shr\Downloads\Hindi_F_Sujata.mp3`
- `C:\Users\19shr\Downloads\HIN_M_AbhishekS.mp3`

Retained validation copies support continuing even if Downloads changes. Verify receipt hashes before reuse; never modify the originals. Keep custom voice media local and do not publish it as a repository artifact without separate authorization.

## 4. Current production speech behavior

### Hindi decoding

`core/tts/tts_handler.py::generate_audio` resolves Hindi to `hi` and passes `do_sample=False, num_beams=1` to local XTTS. Other languages retain their previous sampling defaults. The existing temperature argument remains 0.75 but is inactive for greedy Hindi decoding. Inherited penalties are unchanged. No fixed production random seed was introduced.

Explicit reference routing, staged output publication and cooperative cancellation remain enforced. Do not revert Hindi to the earlier stochastic 0.90 experiments merely because one short sample sounded good: the later varied-text batch was rejected.

### Native output sample rate

After normal or GPU-recovery initialization, `TTSHandler` derives the synthesizer output sample rate from the loaded HiFi decoder, validating an integer rate between 8,000 and 192,000 Hz. The installed Coqui checkpoint-loading branch previously labelled decoder audio at the conditioning rate, 22,050 Hz, rather than its actual 24,000 Hz output. This caused longer playback and lower pitch. Custom decoder rates and CPU recovery are covered. Vendor files and model configuration were not edited.

### Cloned Hindi processing

`core/pipeline.py::_dub_segment_bound` uses existing `normalize_voice_loudness` for Hindi with actor `CLONED_USER`, bypassing the extra `AudioEngineer.master_voice_segment` compressor/treble overlay. Existing normalization still includes its own dynamics and peak control. Other actor/language routes retain their previous mastering behavior.

This language/actor condition can apply to other selected TTS providers; the greedy-decoding change specifically concerns local XTTS.

### Tempo and fitting

Hindi pace remains the user-approved **1.342**. `ReflowPipeline.speed_change` uses bundled `rubberband=tempo=<speed>:pitch=1`, replacing the earlier `atempo` route after localized distortion complaints. It preserves sample rate and channels, uses cancellable owned temporary work, validates decode and timing, and applies measured peak safety.

Invalid/nonfinite/bool/out-of-range speeds are rejected; the allowed range is 0.01–100. Speed 1 returns the original audio without invoking FFmpeg. A missing RubberBand filter produces an actionable error, without a silent fallback. Timing error is limited to 100 ms in this operation.

**Speech is not cut to fit.** Cue bounds and overflow rejection remain active. Do not increase pace beyond the accepted profile simply to force a failing cue through.

## 5. Listening evidence and its limits

| Evidence | User or technical result | Scope |
| --- | --- | --- |
| Earlier stochastic Hindi varied-text batch | User rejected distortion/stutters | Do not promote that profile |
| Earlier raw Abhishek negation | User heard another language before Hindi | Failure arose before final output processing |
| First greedy Abhishek negation | User accepted Hindi-only speech with all words/no stutter | One sentence/reference |
| Greedy Sujata and Abhishek question/meeting takes | User accepted natural Hindi without distortion/stutters | Four raw takes |
| Those same four takes, normalized and paced | User accepted natural, clear processed takes | Four processed takes, not a complete video |
| Production processing replay | All four approved PCM outputs reproduced exactly | Controlled provider; no fresh synthesis |
| Fresh production Sujata question | Raw SHA and final PCM matched approved control | One CPU/reference case; no full reference preparation |

Approved processing durations:

| Voice | Question | Meeting/time-and-pause |
| --- | ---: | ---: |
| Sujata | 4.460 s | 5.533 s |
| Abhishek | 3.076 s | 4.253 s |

Texts in the coverage include `क्या आप मेरी आवाज़ साफ़ सुन पा रहे हैं?` and `कल सुबह दस बजे बैठक शुरू होगी, इसलिए कृपया समय पर पहुँचें।`. These are diagnostic sentences, not corrections approved for the source video.

Key retained directories under `docs/validation/`:

- `2026-10-04-hindi-greedy-e59ab24c/`: first accepted greedy Abhishek negation.
- `2026-10-04-greedy-coverage-f0745810/`: accepted raw question/meeting takes and references.
- `2026-10-04-greedy-processed-d2a35976/`: accepted processed takes.
- `2026-10-04-production-hindi-922db889/`: actual segment processing replay.
- `2026-10-04-live-hindi-7eee0ce3/`: fresh actual XTTS raw/final Sujata output.
- `2026-10-04-hindi-coverage-509b2ff0/`: rejected stochastic coverage, retained for comparison.
- `2026-10-04-hindi-raw-controls-8cc1a42c/`: raw controls locating Abhishek language drift.

**Reference preparation remains a material gap:** accepted Sujata diagnostics use a cleaned full 17.528-second mono 24 kHz reference; accepted Abhishek diagnostics use an unprocessed full 19.775-second mono 24 kHz reference. The automatic pipeline cleans user references using an 80 Hz high-pass, edge trimming and peak normalization. Actual full-pipeline Abhishek quality must therefore be tested. Do not introduce filename-specific voice heuristics or silently assume the reference paths are equivalent.

A single full-scale sample from the Coqui WAV saver is not proof of sustained clipping. Earlier Sujata opening distortion was audible before final processing. Do not mask speech defects through arbitrary fades, gates, cuts or speed changes.

## 6. Verification snapshot

| Check | Recorded outcome | What it establishes |
| --- | --- | --- |
| Focused generation/speech regressions | 64 PASS, 21.494 s | Current targeted behavior |
| Complete backend suite | **493 PASS, 93.946 s** | Latest backend regression baseline |
| Production processing replay | Four exact PCM matches | Accepted processing route integrated |
| Fresh production XTTS question | PASS, 59.640 s | Real adapter/handler/segment inference for one Sujata case |
| Owned portable app refresh | 168 files, no size mismatches | QA application source copies refreshed |
| Frontend checks/build | Earlier 83 checks/build retained | Frontend unchanged in latest repair; not rerun here |
| Whitespace checks | PASS | Patch formatting |

Primary receipts/logs: `2026-10-04-hindi-quality-focused.log`, `2026-10-04-hindi-quality-backend.log`, `2026-10-04-production-hindi.json`, `2026-10-04-live-hindi.json`, `2026-10-04-portable-app-refresh.json` in `docs/validation/`.

Earlier 487- and 490-check results in reports are historical checkpoints, not the latest suite result. Receipt fields named `acceptance` may indicate a mechanical diagnostic gate; read the surrounding report to determine whether human listening was also accepted. The portable refresh is not fresh-PC, model-free first-use, relocation, audible desktop playback or release-package acceptance.

## 7. Full video baseline: retained failure

`dev/verify_real_video_dub.py` exercised a real moving-frame 44-second excerpt of `Sample/2.mp4`, H.264/AAC. The source is approximately 122.532 seconds, 854×480 at 25 fps. Other available samples: `Sample/1.mp4` approximately 102.621 seconds, 1280×720 at 23.976 fps; `Sample/3.mp4` approximately 15.935 seconds, 320×240 at 30 fps.

Baseline configuration: CPU; English source; Hindi target; single `CLONED_USER` Abhishek reference; keep background; soft subtitles; export stems; one worker. Lip sync, enhancement and content filtering disabled. `FixtureRegistry` isolated connections and reused cached models without modifying user registry or downloading models.

The run took **572.734 seconds**. Nine grouped cues were recognized/translated; English detection and source bounds were valid. Cue 1 produced 5.381 seconds within a 6.640-second slot. Cue 2 failed: **3.011 seconds required after timing adjustment, 2.600 seconds available**. The guard stopped the render rather than cutting words.

**No final video was produced.** Background mixing, residual-English leakage, final subtitles, muxing and final frame/audio acceptance were not reached. Demucs progress showed roughly 3m38s of inference, which is not an independent whole-stage wall-time measurement.

Evidence:

- `docs/validation/2026-10-04-real-video-dub.json` and `.log`.
- `docs/validation/2026-10-04-real-video-5b4d14f8/`: source video, supplied/cleaned references, separated vocals/background, separation log, SRT, cue report, cue 1 output and original cue 2 audio.
- Failed cue raw synthesis was not retained during that baseline; a later capture containing zero files is not audio evidence.

A subsequent isolated retry retained two full candidates, 6.134 and 5.832 seconds, both exceeding the same 2.600-second window. It took 93.953 seconds; raw/processed files decode. These randomized retries also predate current greedy/native-rate changes. Neither retry establishes current behavior. Their evidence is in `2026-10-04-cue-retry.json` and `2026-10-04-cue-retry-27beb73d/`.

## 8. Source meaning and translation blockers

| Cue / time | Finding | Required treatment |
| --- | --- | --- |
| 1 / 0–6.64 | Literal Hindi for an established news-report visual style | Review a natural meaning-preserving translation |
| 2 / 6.64–9.24 | Recognition: “Me has this report.” Translation: `मेरे पास यह रिपोर्ट है।` | Source wording uncertain; listen before changing meaning |
| 3 / 9.24–14.48 | “Lackluster establishing shot” became an unclear/ambiguous shot | Correct semantic distinction after source review |
| 4 / 14.48–19.68 | Suspect “Next day,” “altar,” and incomplete sentence | Review full sentence with cue 5 |
| 5 / 19.68–28.64 | Gestures/profanity/matrix phrase mistranslated in tone and meaning | Preserve meaning and intended register; human semantic check |
| 6 / 28.64–31.32 | “What comes next?” | `आगे क्या होता है?` is a proposal, not an accepted rendered correction |
| 7–8 / 31.32–43.44 | Suspect “fellow shot,” fragments and untranslated English terms | Confirm source, translate complete thought, allocate cues deliberately |
| 9 / 43.44–44.04 | Excerpt cuts into “This is followed.” | Choose a complete-sentence endpoint for a future clip; preserve old baseline |

The first-15-second word-timestamp pass also heard “Me, has this report.” (6.66–8.28 seconds, first-word probability 0.769). Agreement from the same small recognizer is not independent human truth. The user's “ok” did not confirm these words. Do not invent a reporter name or assert “filler shot” as confirmed.

Current merging thresholds are approximately 2.5-second minimum, 0.6-second gap and 9-second maximum. Some complete thoughts span approximately 12–14 seconds, exceeding that merger. Context-aware translation is needed; simply creating huge cue windows risks synchronization. Current cue rendering can use following gaps, not automatically borrow earlier time. An earlier-shift proposal using cue 1's spare duration is **not implemented or validated** and requires explicit cue/subtitle/A-V reasoning and review.

## 9. Architecture and product limits

The cue-review workspace supports durable **single-voice audio** preparation, correction, retranslation, generation, audition, acceptance of fitting takes and rendering the exact accepted WAVs. It uses hashed provenance, strict timing/JSON validation and revision/process locking. Overflow acceptance is rejected; edits invalidate candidates and acceptance. Accepted render can reuse retained accepted audio without fresh inference even after settings/model digest changes; new generation/retranslation applies conservative digest checks.

**Video rendering cannot yet reuse those corrected/accepted audio-review takes.** It regenerates recognition, translation and speech. Video/multispeaker review, timing editing and pruning remain gaps; the current cue view displays up to 50 cues.

The exposed ten nodes represent a fixed stage order, not arbitrary executable graphs. Speaker identification is not implemented; multivoice assignment alternates cues. Segment preparation/mastering can overlap, but shared heavy inference is serialized. Do not promise simultaneous GPU model execution. Resource estimates have contract coverage but remain uncalibrated against real model-inclusive RAM/VRAM and admission limits.

Optional environments/integrations are not equivalent to accepted features. F5's default v1 Base supports English/Chinese rather than Hindi; NudeNet/MuseTalk quality acceptance is incomplete. No authorized RVC checkpoint has been accepted, and configured cloud services remain unverified. Do not substitute engines to conceal the local workflow's remaining problems.

## 10. Resume plan and acceptance gates

1. **Preserve and inspect.** Read the latest production report and receipts; inspect current diffs. Allocate a new run label and receipt path. Confirm retained references/models and owned work directory. Do not overwrite accepted/rejected historical receipts.
2. **Test the failing cue under current behavior.** Reuse the retained cleaned Abhishek reference and diagnostic text, actual provider/handler/segment path, no Demucs/STT rerun. Retain raw and full processed audio before owned cleanup. If using diagnostic overflow capture, record actual duration and explicitly keep it unaccepted. Compare against 2.600 seconds; do not truncate or silently relax the render guard.
3. **Test reference preparation.** Compare the accepted unprocessed Abhishek reference with actual automatic preparation on the same text/settings. Preserve both hashes and recordings. Request listening review if the difference changes language, stutters or naturalness. Verify the actual Sujata full-input preparation too.
4. **Resolve source and script.** Present retained source context for ambiguous lines and a consolidated proposed Hindi script. Human confirmation is required where meaning cannot be established. Keep automatic transcript/translation evidence separate from editorial revisions.
5. **Handle cue timing explicitly.** Preserve words and approved pace. Implement any context/timing/review-to-video changes with meaningful regression coverage. New takes need acceptance. Track corrected cue timings in subtitles as well as audio.
6. **Run a complete current automatic workflow** on a complete-sentence excerpt, preserving the old 44-second baseline. Retain configuration, hashes, stage events, transcripts, cue durations, stems, subtitles and final media. If a reviewed-script mode is also tested, give it a separate result and label; it cannot stand in for automatic success.
7. **Verify final media mechanically.** Require real moving frames, expected video/audio/subtitle streams, complete A-V decode, no silent/truncated speech, valid timestamps and expected duration. The existing video diagnostic uses an approximately 0.15-second duration tolerance; state the tested tolerance and container/time-base limitations. Check subtitle synchronization and output/stem publication.
8. **Human final checkpoint.** Supply the actual final video for review: meaning, entirely Hindi delivery, naturalness, stutters/distortion, cue transitions, synchronization and residual original English. Background retention must be judged against source material that actually has music/ambient sound; a source without it cannot prove preservation quality.
9. **Exercise actual app and failure paths.** Confirm the desktop entry path produces the validated output; test cancellation, missing/corrupt assets, failed downloads/offline recovery and failure cleanup/output preservation where changes warrant it. A hidden synthetic audio-control test does not establish audible playback or visible layout quality.
10. **Report bounded readiness.** Document which source, voices, settings, hardware and paths passed. Longer material, multiple speakers, optional features and platform/install matrices remain separate gates. Do not label all features ready from one successful clip.

## 11. Diagnostic entry points and safe operation

Use the existing runtime and bundled media tools. A local setup example:

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$env:TEMP = Join-Path (Get-Location).Path 'temp'
$env:TMP = $env:TEMP
$env:PATH = (Join-Path (Get-Location).Path 'ffmpeg/bin') + ';' + $env:PATH
& 'build/windows-portable/python.exe' -B dev/run_cleanup_checks.py
```

Check the current runner before execution; do not interpret its name as permission to remove user files. Some checks use local HTTP fixtures and may need the existing execution approval mechanism. No external service or new package is implied.

| Entry point | Purpose / caution |
| --- | --- |
| `dev/verify_production_hindi_quality.py` | Controlled-provider processing replay; no synthesis or video |
| `dev/verify_live_hindi_quality.py` | Fresh Sujata adapter/handler/segment check; prepared reference; not full pipeline |
| `dev/retry_real_video_cue.py` | Historical isolated cue experiment; adapt to a new receipt and current behavior rather than blindly repeat two old randomized trials |
| `dev/verify_real_video_dub.py` | Full moving-video diagnostic; static top-level receipt name must be changed for a new run to preserve baseline |
| `dev/refresh_acceptance_portable.py --app-only` | Refresh owned QA app only; not a release build |

Several scripts create unique media directories but write a fixed dated top-level JSON receipt. Before rerunning, preserve the old receipt and its acceptance metadata, and use a distinct new result name. Avoid duplicating heavy model weights. Read/write JSON explicitly as UTF-8 on Windows; a previous driver failed before inference under default text encoding.

Use `RenderContext` ownership, cancellable process execution and publication semantics. Retain diagnostic evidence before cleanup. Never delete source media or unrelated temporary directories. CPU-heavy inference is serial; reuse loaded models within a batch where safe. Keep user-facing progress updates and avoid long blocking waits without updates.

## 12. Release gates beyond this video iteration

- Fresh Windows machine, first-use model downloads, interrupted/corrupt download recovery, offline behavior and portable relocation.
- Linux/macOS distribution and actual execution; GPU memory/fallback behavior on supported hardware.
- Optional engine end-to-end and perceptual acceptance, including lip sync, filtering, enhancement, RVC and cloud paths when advertised/configured.
- Real resource-estimate calibration, concurrency limits and longer/multispeaker workload evidence.
- Packaging/CI alignment: current `.github/workflows/build.yml` still targets native PyInstaller artifacts on three runners, not a fully verified portable acceptance workflow.
- Distribution dependency/model/license/version inventory review; no legal conclusion is asserted here.
- Final UI, documentation, error messages, install instructions and release artifact acceptance.

## 13. Reading order and evidence ownership

Read these workspace reports in order; reports with old check counts describe their historical stage:

1. `docs/HINDI_QUALITY_PRODUCTION_2026-10-04.md` — latest production behavior and 493-check result.
2. `docs/REAL_VIDEO_DUB_ITERATION_2026-10-04.md` — actual failed full-video baseline.
3. `docs/REAL_VIDEO_SCRIPT_REVIEW_2026-10-04.md` — unresolved meaning, proposed edits and historical isolated retries.
4. `docs/CUE_REVIEW_AUDIT_2026-10-04.md` and `docs/CUE_REVIEW_ITERATION_2026-10-04.md` — durable review implementation and video gap.
5. `docs/HINDI_LANGUAGE_DRIFT_2026-10-04.md`, `docs/HINDI_GREEDY_COVERAGE_2026-10-04.md`, `docs/HINDI_GREEDY_PROCESSING_2026-10-04.md` — listening decisions and greedy evidence.
6. `docs/XTTS_PLAYBACK_RATE_REPAIR_2026-10-04.md` and `docs/SPEECH_TEMPO_FIX_2026-10-04.md` — native-rate and tempo repairs.
7. `docs/RELEASE_READINESS_2026-10-04.md` and `docs/PRODUCT_READINESS_2026-10-04.md` — wider readiness; reconcile chronological sections with latest evidence.
8. `docs/ARCHITECTURE_ITERATION_2026-10-03.md` and `docs/FULL_PROJECT_AUDIT_2026-10-03.md` — broad audit and chronological decisions.

JSON receipts and retained recordings are the concrete evidence; prose explains their scope. This handoff adds no new execution result. Resume from the current working tree, preserve approved assets and rejected controls, and close the full-video gate with a new recorded run and human final review.

## 14. October 6 IndicF5 evaluation update

The isolated IndicF5 candidate completed its first trained inference. See
`docs/INDICF5_EVALUATION_2026-10-06.md` and receipt
`docs/validation/2026-10-06-indicf5-smoke-7db43633.json`. The target is the
previously failing Hindi sentence, supplied directly without translation.
The official documented reference voice generated a 1.877333-second output;
strict weight loading and full audio decoding passed. Human speech quality
acceptance remains pending. CPU execution took 695.515 seconds overall, so
performance remains a material concern. Sujata/Abhishek identity, varied Hindi
text, production integration and complete video acceptance are still pending.
This update supersedes the earlier pending-inference checkpoint only; it does
not promote the historical full-video attempt to a pass.

### Listening and user-reference preparation

The user accepted the exact official-reference smoke recording with "yep".
`docs/validation/2026-10-06-indicf5-smoke-user-acceptance.json` records that scope
without altering the original execution receipt. This is not acceptance of
Sujata, Abhishek, varied passages or a full video.

`dev/prepare_indicf5_voice_references.py` prepares separate reference copies and
draft transcripts using the already present local Whisper-large-v3-turbo
assets. An initial generic-F5 interpreter invocation produced no startup
output and was stopped; the empty startup log is retained. A subsequent
isolated-evaluation invocation loaded Whisper but failed because Transformers'
ASR pipeline unconditionally imported unavailable TorchCodec native libraries
even for decoded arrays. Receipt
`docs/validation/2026-10-06-indicf5-user-references-1b39f646.json` and the
`2026-10-06-indicf5-user-references-codec-failure.log` retain the failure.

The diagnostic now calls Whisper's existing feature extractor and
`model.generate` directly with decoded 16 kHz samples, avoiding that optional
codec pipeline. No package or shared-library installation or production patch
was made. It retains cooperative decoder cancellation, serial inference,
source hash checks, unique evidence publication and owned workspace cleanup.
Draft text is reference preparation only, not an independent language-quality
acceptance test. Inspect the successful receipt and listen to exact excerpts
before using their text to condition user-voice tests.

The repaired transcription run completed: receipt
`docs/validation/2026-10-06-indicf5-user-references-984652c4.json`. Prepared short
excerpts and unverified transcript proposals are recorded in
`docs/validation/2026-10-06-indicf5-reference-excerpts-20f08c78.json`.
Read `docs/INDICF5_USER_REFERENCES_2026-10-06.md` for exact source preservation,
failure evidence, repair scope and excerpt boundaries. Await transcript
confirmation/correction against the presented excerpts before user-voice
conditioning tests. Both preparation sessions have finished and their owned
temporary workspaces were removed.

The user confirmed both exact reference excerpts/transcripts, and the serial
CPU voice baseline completed with receipt
`docs/validation/2026-10-06-indicf5-user-voices-d47f7b63.json`. Both generated
voices need delivery work: Sujata is emotionless compared with her original;
Abhishek is too fast and unnatural. Read
`docs/INDICF5_USER_VOICE_RESULTS_2026-10-06.md` for exact durations, timing,
feedback corrections and acceptance scope. The user subsequently approved the
separate GPU evaluation runtime; its package transfer is underway. Do not
interpret approval to install as acceptance of generated speech or production
integration. GPU execution, speech quality and speedup still need verification.

### Latest GPU and listening checkpoint

The approved isolated GPU environment, official wheel checksums, dependency
compatibility and actual CUDA operations passed. Six trained-speech trials
completed in 50.282 measured seconds after imports, with roughly 5.5–7.3-second
inference per short take. The user preferred C for both voices. This means
guidance 2.0/seed 42, native speed 1.0 for Sujata and 0.65 for Abhishek.

The subsequent three-sentence test completed technically: receipt
`docs/validation/2026-10-06-indicf5-gpu-user-voices-747ae53b.json`, Sujata output
8.096 seconds and Abhishek 7.744 seconds. Human listening is pending for these
longer takes. Read `docs/INDICF5_GPU_ITERATION_2026-10-06.md` for all exact
settings, isolation evidence, transfer recovery, timings, audio checks and
acceptance boundaries. Approximately 4.0 GB of exact owned transfer files were
removed after verification; installed packages, model assets, sources and media
remain. All background jobs for this iteration have finished.

Resume with longer-take listening, then broader wording and a separate
production engine/reference/delivery integration. The existing pipeline's
global Hindi 1.342 tempo and reference-cleaning path must not silently alter
the new preferred settings/pairs. No completed video, release or new full
backend-suite result is claimed.
# Latest Hindi naturalness checkpoint — 2026-10-06

Newest result: the user approved the editorial Hindi draft. Fourteen IndicF5
sentence generations completed with accepted reference/settings; generation
receipt `docs/validation/2026-10-06-indicf5-gpu-user-voices-2eb79a50.json`.
A real moving 52-second review video is now complete:
`docs/validation/2026-10-06-indicf5-video-review-2c8507f0/abhishek-hindi-review.mp4`.
Outer receipt: `docs/validation/2026-10-06-indicf5-video-review-2c8507f0.json`.
Eight cues fit without cutting words or post-tempo, full decoding passed,
approved Hindi subtitles survived round-trip extraction, source hash unchanged
and workspace cleanup completed. Human review of this exact final video is
pending, especially the short question at 29 seconds and final cue at 43 seconds.

An actual shared `run_process` capture-output bug exposed during inspection was
fixed in `core/render_context.py`. Four real-process regression tests plus
related cancellation/session tests passed: 29 tests total, workspace TEMP/TMP.
Detailed implementation, failures, logs, hashes and limits:
`docs/INDICF5_VIDEO_ITERATION_2026-10-06.md`.
All sessions finished. This is an explicit diagnostic render bridge with reviewed
text, not selectable production IndicF5 integration; background preservation,
automatic translation quality and full release validation remain outstanding.

Context run completed: `docs/validation/2026-10-06-indicf5-video-cues-9fce0cd4.json`.
Eight complete source groups now end at 52.0 seconds. The confirmed English
phrase remains. Grouping recovered some omitted context, but NLLB still fails
idioms/film terms. Explicit assistant editorial Hindi proposals, not automatic
NLLB improvements, are prepared in `docs/VIDEO_HINDI_DRAFT_2026-10-06.md` and
`docs/validation/2026-10-06-video-hindi-editorial-draft.json`.
Pending human wording/tone review; not synthesized or accepted. Timing estimates
including sentence gaps now fit all eight windows, but actual audio fit is
untested. Exact nuance tradeoffs and previous overrun estimate are documented in
`docs/INDICF5_VIDEO_TEXT_REVIEW_2026-10-06.md`. All sessions finished; production
and release status unchanged.

The user confirmed the short source phrase as "Me has this report".
Receipt: `docs/validation/2026-10-06-video-source-wording-acceptance.json`.
Keep that source wording; its unusual grammar is not an established ASR error.
Context preparation now runs with the existing Whisper/NLLB, extending source
recognition to 60 seconds and selecting the first complete sentence endpoint
after 44 seconds. Punctuation-based groups are translated together; tail cues
remain recorded. Log: `docs/validation/2026-10-06-indicf5-video-context.log`.
This is still diagnostic preparation; text quality and video integration are
not passed.

Video text preparation is now finished; fresh receipt:
`docs/validation/2026-10-06-indicf5-video-cues-dc446977.json`.
Twelve phrases prepared with stronger existing Whisper and NLLB; technical
checks and cleanup passed, but meaning review failed. Do not synthesize these
drafts as accepted translations. See `docs/INDICF5_VIDEO_TEXT_REVIEW_2026-10-06.md`
for recognition ambiguity, film-term/idiom mistranslation, omitted meaning,
fragment context and the 44-second cut ending mid-sentence. Editorial proposals
are explicitly unapproved, not NLLB outputs. All sessions are finished.

Accepted now: the exact sentence-wise Abhishek assembly is clear and natural
per user feedback, saved in
`docs/validation/2026-10-06-indicf5-segmented-user-acceptance.json`.
The earlier continuous paragraph remains rejected. User approved moving to
video validation. Production integration must preserve confirmed reference
audio/text and native delivery instead of applying the pipeline's Hindi 1.342
tempo to IndicF5.

Old real-video recognition/translation drafts have content errors and are not
appropriate inputs for accepted voice-quality validation. Fresh 44-second
source/translation preparation is underway with existing Whisper-large-v3-turbo
and NLLB in the isolated verified GPU runtime:
`dev/prepare_indicf5_video_cues.py`, log
`docs/validation/2026-10-06-indicf5-video-cues.log`.
No new dependency or production change. Prepared cues require review before
speech/timing validation; a full-video pass has not occurred.

Latest feedback rejects the 25-second continuous take: words before about 2 s
and after about 15 s were gibberish; the middle was good. Review:
`docs/validation/2026-10-06-indicf5-extended-user-review.json`.
Do not count this as a naturalness or intelligibility pass.

The same exact six-sentence paragraph has now been generated sentence by
sentence using the same confirmed alternate reference, seed 1234, guidance
2.0 and 32 steps. Sentence speech durations share the original 25.376-second
budget; the assembled result is 26.376 seconds with five 0.20-second gaps.
Generation: `docs/validation/2026-10-06-indicf5-gpu-user-voices-fbf9cf81.json`.
Assembly: `docs/validation/2026-10-06-indicf5-segmented-listening-5e24a3c2.json`.
All technical checks and cleanup passed. A final console Unicode-print failure
occurred after publication; completed media and receipt were verified, and
console escaping was corrected. Human review of the full result, especially
start/end wording and sentence transitions, is pending. No inference remains
running; no production default or release-status change.

Most recent test: user preferred B on the follow-up passage, then approved a
longer check. Review: `docs/validation/2026-10-06-indicf5-followup-user-review.json`.
Six-sentence Abhishek output completed at 25.376 seconds using the confirmed
alternate reference, seed 1234, guidance 2.0, 32 steps and text-length-scaled
explicit duration. Receipt:
`docs/validation/2026-10-06-indicf5-gpu-user-voices-9af33aa8.json`.
Technical checks and cleanup passed; no inference remains running. Human review
of sustained naturalness, full wording, stutters and ending is pending. This
test does not yet validate production integration, cue timing or full video.

Newest checkpoint: user said "so better" for the alternate-reference Abhishek
take, recorded in `docs/validation/2026-10-06-indicf5-reference-comparison-user-review.json`.
This is an exact-take improvement, not full release acceptance. A different
three-sentence passage was generated with that reference using seeds 42 and
1234, each at guidance 2.0, 32 steps and explicit 7.744-second target duration.
Completed receipt: `docs/validation/2026-10-06-indicf5-gpu-user-voices-0f148951.json`.
All technical/audio-duration checks passed, owned workspace cleaned, sessions
finished. Both new takes await human review for wording, naturalness and
stutters. Production defaults remain unchanged. See the iteration record for
exact hashes, durations, timings and duration-control limitations.

Alternate Abhishek excerpt transcript was confirmed by the user's "ok".
Acceptance: `docs/validation/2026-10-06-indicf5-alternate-abhishek-acceptance.json`.
Duration-controlled comparison completed:
`docs/validation/2026-10-06-indicf5-gpu-user-voices-7f1af934.json`.
Control and alternate are both 7.744 seconds, with seed 42, guidance 2.0 and
32 steps. Control listening hash reproduces the earlier rejected baseline.
Alternate delivery awaits human review; no quality pass or production change.
Initial attempt `7f89b674` failed the duration gate and published no audio;
centered Vocos frame-count correction is documented in the iteration record.

Subsequent A/B/C/D review: user chose D for Sujata and none for Abhishek.
`docs/validation/2026-10-06-indicf5-prosody-user-review.json` preserves the reply
and scope. Sujata guidance 2.5 is a candidate preference only, not a production
quality pass. All four Abhishek longer takes were rejected. Next: confirm the
exact words in the prepared alternate Abhishek original excerpt, then compare
reference conditioning while controlling duration. Production unchanged.

The user preferred C for both short GPU samples, but rejected the subsequent
three-sentence takes as robotic on closer listening. Do not promote the short
preference or technical GPU pass into production naturalness acceptance.
Review: `docs/validation/2026-10-06-indicf5-long-user-review.json`.

Six controlled diagnostic cases are now complete (64 steps, guidance 1.5,
guidance 2.5 for each voice). Same confirmed references, target, seed and native
speeds; no post-generation tempo changes. Receipt:
`docs/validation/2026-10-06-indicf5-gpu-user-voices-87b036a9.json`.
Baseline-plus-variants A/B/C/D listening montages:
`docs/validation/2026-10-06-indicf5-gpu-comparison-4ce65b0d.json`.
Human review is pending. All inference sessions are finished.

Alternate original reference phrases are prepared in
`docs/validation/2026-10-06-indicf5-alternate-references-1f79a3cd.json`.
Draft transcripts are unverified: obtain exact-excerpt confirmation before
using these for synthesis. Production remains unchanged. Detailed changes,
validation evidence and limitations are in `docs/INDICF5_GPU_ITERATION_2026-10-06.md`.

