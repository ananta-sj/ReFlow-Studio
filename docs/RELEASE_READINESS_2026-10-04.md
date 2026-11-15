# ReFlow Studio release readiness — current decision

**Decision: not ready for a public, fully featured release.**
The current work supports internal Windows testing and selected accepted media
examples. A release must validate the automatic application workflow on clean
systems, not just retained/manual review clips. The 500 MB target was withdrawn
and is not a release gate. No commit, push, deployment or release has been made.

## Evidence we have

- Current backend after accepted Hindi decoding/processing integration:493 PASS
  in93.946s. Four production segment outputs reproduce accepted processed PCM;
  one fresh actual XTTS adapter inference also matches approved raw/final data.
  Portable QA168 files/no mismatches. See `HINDI_QUALITY_PRODUCTION_2026-10-04.md`.
- Current backend after XTTS playback-rate repair:490 passing checks in124.375s.
  Corrected22050-Hz WAV labeling of24000-Hz decoder samples; seeded real-engine
  controls repeat exactly but still overflow the2.600s cue. Native-rate listening
  comparison direction positively received; cleaned-reference Sujata take accepted.
  Six varied-text takes pass mechanical checks but the user rejects both review
  voices for distortion/stutters. Raw-stage isolation is pending. Diagnostic
  settings still differ from app defaults; reliable Hindi quality remains blocked.
  See `XTTS_PLAYBACK_RATE_REPAIR_2026-10-04.md` and `HINDI_VOICE_COVERAGE_2026-10-04.md`.
- Backend suite after accepted speech tempo repair: 487 passing checks in95.016s;
  exact approved PCM and current portable verification are documented in
  `SPEECH_TEMPO_FIX_2026-10-04.md`. Earlier review storage fixes remain documented
  in `CUE_REVIEW_AUDIT_2026-10-04.md`.
- Retained frontend evidence: 83 passing checks and a successful build; frontend
  was unchanged during the recent audio work.
- Copied Windows portable application: six-page/ten-node desktop checks and
  subsequent 167-file application refresh with no size mismatches. This is not
  a clean second-PC or model-free first-use acceptance.
- Actual selected engine executions, cancellation/output preservation, offline
  recovery and download failure checks are recorded in the architecture ledger.
- User-approved Hindi short/long voice examples; the approved overall pace is
  applied to production Hindi dubbing, with audible-word truncation refused.
- The selected 4.839-second sentence reading is now voice-only on its original
  timeline. A residual separator stem had been incorrectly described as verified
  music/ambience; that selected mix is superseded. Original files are preserved.

Tests establish specific contracts. They do not certify semantic translation,
natural voice quality on all text, visual quality or every engine/platform.

Latest real44-second moving-video baseline failed at cue2: Hindi needs3.011s
within2.600s; guard prevented word cutting. Cue1 fits5.381s/6.640s. Source/translation
review also found suspect recognition, fragmented Hindi and an incomplete final
sentence at the extraction boundary. No final video was published. Evidence and
repair sequence: `REAL_VIDEO_DUB_ITERATION_2026-10-04.md`.

## Remaining work, in priority order

| Area | Current gap | Release acceptance required |
| --- | --- | --- |
| Automatic transcript/translation/timing | Bounded single-voice continuation grouping is now implemented; it cannot repair recognition or guarantee semantic quality. The accepted earlier sample used contextual recognition and a manually reviewed translation. The unchanged eight-second rerun fails source-duration validation before translation. | Complete thought units within bounded timing/speaker windows; preserve meaning, names, numbers and negation; successful automatic real-media runs with no cut words. |
| Consistent voice quality and correction | Single-voice audio correction/audition/regeneration and accepted-take reuse are now implemented. Some generation attempts have choppy endings; a fresh reading improved one earlier case. | Repeated quality review across varied passages/references; video and multi-speaker review; validate the new workflow with actual user listening and complete corrected outputs. |
| Current complete media workflows | The latest strict news-dub fixture failed. Earlier video acceptance predates the latest speech guards/mastering. Short static clips do not establish long-video behavior. | Rerun current audio/subtitle/video chains, longer media, real moving faces, optional stages, cue boundaries, cancellation and output recovery. Review pronunciation, sync, word loss and separation leakage. |
| Nodes and speakers | Ten nodes expose a fixed stage order; extra voices alternate cues. Arbitrary graph execution and speaker identification are not implemented. | Implement the claimed capabilities or clearly restrict the release scope/UI/documentation to what executes. Test every enabled node and combination in that scope. |
| Parallelism and resource guidance | Segment preparation/mastering can overlap; shared heavy inference remains serialized. Estimates are uncalibrated and do not establish model-inclusive memory admission. CPU F5 latency is substantial. | Measure realistic CPU/GPU workloads and worker-inclusive RAM/VRAM; give honest estimates and avoid promising independent engine concurrency or safe memory limits without evidence. |
| Optional integrations | No actual authorized RVC checkpoint acceptance; live configured cloud services unverified; AirLLM optional installation lacks approval. Human quality acceptance is incomplete for several optional engines. | Validate every advertised integration with its actual prerequisites, or disable/exclude it and explain availability accurately. New tools/engines still require approval. |
| Distribution and platforms | Current portable evidence is Windows-local. Linux/macOS and GPU feature acceptance are missing. Model-free first-use and clean relocated/fresh-machine acceptance are missing. | Assemble the chosen portable release, test extraction/relocation, first-use model setup, offline restart, optional environments and clean machines. Test each OS/GPU route actually promised. |
| Release automation and documentation | `.github/workflows/build.yml` still builds native PyInstaller artifacts on three runners without regression or real portable acceptance gates; it is not the verified portable release workflow. | Align CI with the chosen distribution; run required checks before packaging; verify artifacts, manifests, launch instructions and prerequisites; review/version the final source changes. |
| Distribution permissions | Model/dependency redistribution notices and business-use permissions require a final inventory/review. | Record actual shipped/downloaded versions and their terms; complete notices/permissions review before business distribution. No legal conclusion is asserted here. |

## Suggested release scope

First target a validated **Windows portable beta** with explicitly supported
engines and truthful limitations. Do not announce a stable Windows/Linux/macOS,
all-engines release from current evidence. Optional integrations can be excluded
from that beta if visibly unavailable rather than falsely advertised as ready.
Even a beta needs a clean-machine/first-use check and a successful current
automatic dubbing workflow; those gates have not yet been met.

Bounded single-voice sentence-continuation grouping and audio cue review are now
implemented; the current backend suite passes 487 checks. The unchanged eight-second rerun failed in recognition
before translation because a cue exceeded the source duration; it remains an
unpassed acceptance case. See `SENTENCE_GROUPING_ITERATION_2026-10-04.md` for the
separately labelled longer-context run and the rule's limitations. Its first
sentence passes speech timing, but cue two fails (3.143 s needed in 2.720 s),
so the full automatic dub remains unpassed. Automatic
translation acceptance and extension/validation of the new single-voice audio
review workflow remain technical priorities. They can
be developed within the existing stack; this document does not authorize a new
tool, framework, account action or model installation.

Detailed evidence: `ARCHITECTURE_ITERATION_2026-10-03.md`,
`TRANSLATION_TIMING_REVIEW_2026-10-04.md`, `PRODUCT_READINESS_2026-10-04.md`, and
the retained `validation/` receipts. Older audit/ledger statuses are historical;
later measured results and this current decision supersede them.

### Controlled reference follow-up — 4 October 2026

Existing offline CPU XTTS comparison completed in200.937s using the same Hindi text, seed1234, temperature.75 and approved1.342 pace. Saved full reference produced6.868s; a cleaned6.640s first-cue reference produced4.202s; repeating the short reference yielded identical raw/processed hashes. Neither fits the2.600s slot. Model loading39.031s once; synthesis72.563s/full and34.531–42.735s/short. Installed XTTS caps conditioning at30s despite the119.204s saved reference. Naturalness, reference cleanliness/speaker identity and translation meaning still need listening review. No production settings/cache/new tool/model download changed. New diagnostic script dev/compare_review_reference.py and detailed report VOICE_REFERENCE_COMPARISON_2026-10-04.md; receipt validation/2026-10-04-reference-comparison.json. Prior backend483/UI evidence retained, no new production edits. Release decision remains not ready.

### Speech intelligibility rejection and diagnostic controls — 4 October 2026

User rejected both reference comparison takes: "both are gibberish after first 2-3 words". Recorded rejection in the original comparison receipt/report; duration reduction and repeat hashes are not quality success. Follow-up with unchanged offline XTTS and exact reference from earlier approved Hindi cases completed131.719s, model load37.360s: Hindi seed1234 raw4.238s/paced3.143s, seed7 raw4.436s/paced3.293s, English control2.172s. Tokenizer round-trips retain full input with zero unknown tokens. All WAVs decode, workspace removed. Listening to raw Hindi versus processed and English is pending; no root cause or quality fix claimed. Both Hindi controls still overflow2.600s. Added dev/diagnose_review_speech.py, detailed SPEECH_INTELLIGIBILITY_DIAGNOSIS_2026-10-04.md and separate speech-diagnosis receipt/log/audio. No production settings/new tool/engine/download/accepted audio changed; prior backend483/UI evidence retained. Release remains not ready.


### Automatic Hindi workflow checkpoint — 9 October 2026

Release remains **not ready**. See `AUTOMATIC_WORKFLOW_VALIDATION_2026-10-09.md` for the complete scope, failures and receipts. The saved app selections now connect installed Whisper turbo, IndicTrans2 and the confirmed Abhishek IndicF5 GPU voice. Automatic audio/video dubbing and cue-review preparation resolve its verified reference without another upload, and reject unrelated explicit references. A fresh 4-second source excerpt completed automatic recognition, translation, synthesis and Hindi-subtitled export using the actual saved registry, without edited text, reused speech or manual timing. The source and registry were unchanged, all workers released and the job workspace removed. This is backend validation of one short excerpt, not an independent-source or complete-video acceptance.

Timing edits are now available in cue review with atomic bounds, overlap, revision and accepted-recording protections. Punctuation-only recognition cannot become a spoken cue. Legacy cleanup preserves managed jobs; lost worker requests fail promptly. The QA portable application copy was refreshed (186 files, no size mismatches). No new dependency/model download was added. Full raw video translations still have **11 of 14 cues exceeding native speech windows**. The revised accepted-shot full-video candidate/ending has not yet received user acceptance; background/multi-speaker/clean-machine/cross-platform validation remains outstanding. Historical pass counts below/above do not supersede these limits.


The final 9 October backend run passed **576 checks in 83.190 seconds**, and the frontend production build passed. A post-run check found and corrected a registry test's fixture isolation; only its known newly-created dummy entry was removed, restoring the exact configured registry hash. Detailed logs and scope are in the 9 October automatic-workflow report. These checks do not change the release decision or full-video quality limitations above.


### Budgeted full-video Hindi review — 9 October 2026

The known full video now has an explicit edited review candidate with **14/14 measured available-window fits**, compared with **3/14 raw translation fits**. Thirteen recordings were freshly generated; the reviewed question/shot composition was preserved. The first ten new recordings are sample-exact matches to the approved baseline. Two changed passage wordings await listening approval. One uses approximately 0.513 seconds after its nominal recognized cue end, inside the silence before the next cue; exact shot alignment remains unaccepted. The full video decodes and retains Hindi subtitles and source duration. This is editorial adaptation using saved live ASR/MT evidence, not automatic budget-aware machine translation.

The app now offers a read-only **Check speech timing** action for the selected confirmed IndicF5 voice, with revision/configuration/reference guards and explicit unavailable estimates for other engines. **581 backend checks passed**, frontend build passed, the real registry was unchanged by the suite, and the QA application copy was refreshed. Detailed report: `BUDGETED_HINDI_FULL_VIDEO_REVIEW_2026-10-09.md`. Human pronunciation/delivery/synchronization review, automatic semantic shortening, independent-source validation and the other release limitations above remain outstanding. Release remains **not ready**.


### Short rewritten passage accepted — 9 October 2026

The user replied “good” to the 68–90-second rewritten-passage preview. Exact media/receipt hashes and limited acceptance scope are recorded in `validation/2026-10-09-budgeted-hindi-passage-user-feedback.json`. The short comparison is accepted; the full-video candidate and release remain pending. No automatic translation-shortening or general naturalness claim follows from this feedback.


### Complete budgeted Hindi video accepted — 9 October 2026

The user replied “good” after the complete reviewed video was linked for full delivery/synchronization/ending review. Acceptance is bound to this output in `validation/2026-10-09-budgeted-hindi-full-video-user-feedback.json`, superseding the pending human acceptance of this particular candidate. It establishes an accepted editorially budgeted Hindi baseline, not automatic shortening or general feature acceptance. The raw translator still needs timing-aware semantic adaptation; independent sources and the other documented release checks remain outstanding. Release readiness remains pending.

### Pipeline foundation implemented — 9 October 2026

After architecture-plan approval, normal automatic runs gained a versioned fixed-template plan, frozen model/settings selections, source-scoped cue identities/lineage, preserved source/raw translated text and durable execution records. [The iteration report](<C:/Projects/Reflow Studio/docs/PIPELINE_FOUNDATION_ITERATION_2026-10-09.md>) documents the code changes, schemas and limits. The final backend suite passed 607 tests in 151.820 seconds and preserved the real model registry.

A fresh four-second automatic excerpt decoded successfully and matched its previous output hash. The full known sample retained all 14 translations but failed native timing preflight (first cue: 7.381 seconds predicted, 6.400 available), with no dub published. A separate eight-second sample failed recognition and retained raw worker evidence, with no translation/speech calls. Saved state/source hashes and the accepted full-video baseline remained unchanged.

This establishes execution evidence rather than automatic quality or resumable stage checkpoints. Shared review-cue migration, checkpoint invalidation/resume, dialogue adaptation, quality supervision, the optional manager and the previously recorded platform/provider release gates remain outstanding. Release readiness remains pending.


### Verified stage recovery and review provenance — 9 October 2026

Normal runs can now reuse verified recognition and translation checkpoints for selected local Whisper Turbo/IndicTrans2 engines. Cache keys include source/audio, selected model/runtime content, relevant code and stage-specific inputs. Unsupported/API/moderated translation routes execute normally. Reuse retains original producer/run evidence without fabricating new inference operations. Saved reviews now preserve stable cue identities, original source/timing, corrections and combination lineage, with read-only legacy migration.

The final backend suite passed **627 tests in 79.355 seconds**, with unchanged saved registry/settings. Real full-video recovery skipped recognition and all 14 translation calls on its second pass while retaining the same 7.381/6.400-second timing failure. Real subtitle exports after the final repairs were byte-identical, with one translation call on the first pass and zero on the second. Frontend build and application-source lint passed; existing warnings remain.

The iteration also repaired subtitle-list compatibility, a disappearing review-lock-path race and transient Windows atomic-save denials, with permanent-failure preservation checks. [The detailed report](<C:/Projects/Reflow Studio/docs/STAGE_CHECKPOINTS_ITERATION_2026-10-09.md>) distinguishes earlier failed attempts and their source versions from final passing evidence.

Strict artifact fingerprinting still adds substantial disk work, especially on recognition recovery. Automatic duration-aware dialogue adaptation, general quality supervision, independent-source validation, wider provider/platform verification and the manager remain outstanding. The accepted editorial full video remains unchanged. Release readiness remains **pending**.


### Dialogue assessment and bounded wording review — 9 October 2026

Native automatic audio/video runs now save an all-cue timing report before synthesis and explicitly flag review requirements. Saved reviews can request up to three unapproved wording alternatives using the existing IndicTrans2 worker; selecting wording remains an edit followed by saving and auditioning. The worker's multi-candidate processor deadlock and request-counter corruption were repaired. Proposal requests are bounded to 180 seconds with worker diagnostics.

The complete backend suite passed **641 tests across 36 modules in 193.547 seconds**, preserving saved settings/registry and tested source hashes. Frontend build/application-source lint passed with existing warnings. A real worker completed three consecutive requests in one session. All 14 preserved raw-translated full-sample cues were assessed: 11 overflow; no tested alternative for the first three conflicts fits. No new speech/video was generated or human quality accepted in this check. The accepted editorial video remains unchanged.

[The detailed dialogue iteration](<C:/Projects/Reflow Studio/docs/DIALOGUE_ADAPTATION_ITERATION_2026-10-09.md>) records successful and failed evidence separately. Meaning-preserving automatic compression, naturalness supervision, independent-source/provider/platform gates and the manager remain outstanding. This is a partial quality milestone; release readiness remains **pending**.


### Optional hybrid dialogue configuration — 9 October 2026

The approved hybrid design now has Settings modes, separate writer/reviewer connections, scoped text-sharing consent, read-only configuration readiness and a chat-compatible adapter built on existing HTTP/OS credentials. Defaults remain off. A disposable loopback server verified actual writer/reviewer HTTP orchestration; fixture opinions remained unapproved. No real model service, paid API request or model installation was used.

The complete suite passed **673 tests across 38 modules in 168.922 seconds**, preserving tested sources and saved registry/settings. Frontend production build and application-source lint passed with existing warnings. The accepted editorial video hash remains unchanged. [The iteration report](<C:/Projects/Reflow Studio/docs/HYBRID_DIALOGUE_CONNECTIONS_ITERATION_2026-10-09.md>) distinguishes configuration readiness from service availability/quality and records socket cancellation limitations.

Normal pipeline/review invocation, chosen-model evaluation, actual generated-speech fit and semantic/naturalness acceptance remain outstanding. A hybrid configuration is not proof that arbitrary videos now finish automatically. Release readiness remains **pending**.

### User-invoked assistance and setup inspection — 9 October 2026

Saved cue reviews now support an explicitly disclosed hybrid wording/meaning-review action, bounded to one writer and one critic request, with revision/configuration/consent guards and durable unapproved reports. Manual saving/auditioning remains required; ordinary runs do not invoke it. **684 backend tests across 38 modules passed** with saved-state/source integrity, plus frontend build/lint. [Detailed assisted-review evidence](<C:/Projects/Reflow Studio/docs/ASSISTED_CUE_REVIEW_ITERATION_2026-10-09.md>) distinguishes actual localhost transport fixtures from model quality. Live model calls/installations are deferred at the user's request.

The Dashboard also offers read-only selected-setup inspection. Current English-to-Hindi Whisper Turbo/IndicTrans2/Abhishek file contracts and interpreter selections passed the limited installed check. This does not establish engine loading, hardware or arbitrary-video success. [Detailed setup scope](<C:/Projects/Reflow Studio/docs/ENGINE_SETUP_INSPECTION_ITERATION_2026-10-09.md>) records remaining A07 work. Wider runtime/provider/platform gates, independent input validation and quality/manager work remain pending. Release readiness remains **pending**.

Final validation passed **694 tests across 39 modules in 107.359 seconds**, plus frontend build/lint, with source/state/video integrity verified. One initial Windows review-directory rename failure could not be reproduced in ten isolated repeats or the passing full rerun; it is recorded as an unresolved intermittent issue, not a demonstrated repair.

### Explicit selected-runtime checks — 9 October 2026

The Dashboard can now import dependencies and run a tiny selected-device calculation through existing isolated interpreters. Pinned Whisper Turbo, IndicTrans2 and IndicF5 each passed an actual GPU smoke check in retained individual runs. No model weight loading, inference, download or provider request was performed. The bounded checker handles IndicTrans2's deliberate shared CUDA dependencies and gives F5's measured import chain a 90-second budget, keeping 45 seconds for recognition/translation. Timeouts remain unverified. Job/deletion reservations prevent competing application work during checks.

[The runtime report](<C:/Projects/Reflow Studio/docs/RUNTIME_DEPENDENCY_CHECK_ITERATION_2026-10-09.md>) records failed/incomplete attempts, import diagnostics, corrected assumptions, validation and remaining coverage. These observations do not prove a new full video, translation/speech quality or other engines/platforms. Live assistance evaluation remains deferred by the user. The earlier intermittent publication issue remains unresolved; release readiness remains **pending**.

Final runtime increment validation passed **707 tests across 40 modules in 97.391 seconds**, plus frontend build/lint. Tested-source, saved-state and accepted-video integrity passed. Hindi's actual dependency/device probe passed in 49.093 seconds; all three currently selected engines have individual passing smoke-check evidence. The Windows publication error did not recur in final regressions, without a demonstrated repair.

### Windows transient publication recovery — 9 October 2026

Job publication now has bounded, cancellable retries for Windows access/sharing denials. A real locked child review file reproduced WinError 5 during directory rename; publication succeeded after handle release. Integration through real review preparation passed, and persistent-denial tests preserved old/pending data. **717 tests across 41 modules passed in 111.047 seconds**, with saved-state/source/accepted-video integrity preserved. [The detailed report](<C:/Projects/Reflow Studio/docs/WINDOWS_PUBLICATION_ITERATION_2026-10-09.md>) separates the demonstrated transient-lock recovery from the still-unidentified original handle owner. No model/API calls or installations occurred. Wider pipeline/platform/quality gates remain open; release readiness remains **pending**.

### Optional engine dependency coverage — 9 October 2026

Selected-setup runtime checks now cover generic F5, MuseTalk, NudeNet, RVC, GFPGAN, Wav2Lip and image/text classifiers using fixed, bounded dependency/device checks. Built-in stage fallbacks are included. In-process engines use the actual app interpreter; a worker override cannot establish their readiness, and frozen in-process environments remain explicitly unverified. Identical checks are reused only within one inspection, with independent result copies per voice. No API request, model loading, download or installation was performed.

Actual existing CPU checks passed for NudeNet, RVC, GFPGAN and Wav2Lip. Generic F5 and MuseTalk timed out at 90 seconds and remain unverified; a timeout does not establish a broken engine. Optional CUDA environments, checkpoint loading/rendering, background separation, wider platform coverage and independent full-video acceptance remain open. Live assistance evaluation remains deferred at the user's request.

Final validation passed **726 tests across 41 modules in 111.922 seconds**, plus frontend build/lint. Tested-source, saved-state and accepted-video integrity passed. [The detailed optional-engine report](<C:/Projects/Reflow Studio/docs/OPTIONAL_ENGINE_READINESS_ITERATION_2026-10-09.md>) records exact routes, interpreter choices, actual observations and remaining limits. A07 remains partial and release readiness remains **pending**.

### Bundled optional workflow checks and retained import diagnostics — 9 October 2026

Runtime inspection now verifies the generic F5 synthesis interfaces and imports MuseTalk's actual bundled workflow with origin/entry-point checks, without constructing models or invoking inference. MuseTalk's expanded installed CPU check passed in 39.797 seconds. Generic F5 remained incomplete at 90 seconds; snapshots show progressing imports, not an established deadlock or corrupt installation. Its readiness remains unverified. The prior incomplete observations remain preserved separately.

The first full regression run exposed five Windows stdout encoding errors in the standalone verification runner. The normal application already initializes UTF-8. The runner now mirrors that configuration, and its failed receipt is preserved. The corrected final run passed **729 tests across 41 modules in 107.656 seconds**; focused checks passed 35 tests. Saved-state, tested-source and accepted-video integrity passed. No frontend/dependency changes, downloads, model loading or live provider calls occurred.

[The detailed workflow-import iteration](<C:/Projects/Reflow Studio/docs/OPTIONAL_WORKFLOW_IMPORT_ITERATION_2026-10-09.md>) records both diagnostic runs, limits and the harness correction. Model-backed rendering, wider device/platform coverage, independent full-video acceptance and live assisted-review quality remain open. A07 stays partial; release readiness remains **pending**.

### Translation-stage failure/close recovery — 9 October 2026

Translation's existing IndicTrans2 worker release is now guaranteed at the owning stage boundary for success, failure, cancellation and subtitle-generator close across audio/video/subtitle runs and review preparation. Cleanup failures during unwinding retain the original failure and log only their type; cleanup failure after success remains explicit before later work proceeds. Video release now occurs before subtitle writing. Other providers' lifecycle protocols and universal media-stage resume are not added by this change.

A synthetic PCM/provider-fixture restart test verified that a failed second translation cue leaves completed recognition reusable, does not publish partial translation, and retranslates the full batch on a new run. Recognition was called once across the two runs, translation four times and release twice. This is control-flow/cache evidence, not live model quality. Subtitle close records cancellation/restores selection; failed review preparation preserves the earlier review.

Focused validation passed **103 tests in 23.456 seconds**; full validation passed **733 tests across 41 modules in 104.297 seconds**. Tested-source, saved-state and accepted-video integrity passed. An initial focused invocation failed on denied renames in the sandbox's default temporary directory; its log is preserved, and final runs use project-owned disposable fixtures. No frontend/dependency change, model inference, download, installation or external provider call occurred. [The detailed stage-recovery report](<C:/Projects/Reflow Studio/docs/STAGE_RECOVERY_ITERATION_2026-10-09.md>) records the stage map, scope, repair, evidence and remaining gates. Wider resource/provider/platform and independent video/quality validation remain open; release readiness remains **pending**.

### Mixed processor budgets and shared parallel bounds — 9 October 2026

Resource planning now splits base speech and requested voice-conversion components by the processors used in execution, including separately selected IndicF5 devices for non-cloned actors and optional CPU F5 mixed with GPU speech. CPU components no longer receive another component's GPU timing discount or count against its GPU budget. Duplicate voice IDs count once; all-F5 casts omit unrelated active base speech. GPU model budgets are grouped by device, with missing estimates marked unknown rather than zero. The legacy aggregate remains for response compatibility; Dashboard/Nodes use the selected processor's own budget.

Scheduling and buffer estimates share the existing 1–8 worker policy and bounded segment window (one sequential, twice workers for parallel). Worker count does not imply measured model speedup or multiply model VRAM. Text-only internal estimates count no audio buffers. Nine-second clip assumptions, additional model memory and uncalibrated cumulative GPU budgets are explicit. The shared frontend calculation refuses missing/invalid memory or telemetry; stale asynchronous results cannot overwrite newer selections. Interactive UI and physical multiple-GPU acceptance are still open.

Final validation passed **742 tests across 42 modules in 102.688 seconds**, plus 81 focused tests, eight source-bound frontend helper checks, production frontend build and lint. Tested-source, saved-state and accepted-video integrity passed. No model inference, installations, downloads or external provider requests occurred. [The detailed resource-routing report](<C:/Projects/Reflow Studio/docs/RESOURCE_ROUTING_ITERATION_2026-10-09.md>) records assumptions, source changes, API compatibility and remaining limits. Actual throughput/activation/CPU-model/service-resource calibration and independent video/quality validation remain pending; release readiness remains **pending**.

### Portable UI walkthrough — 10 October 2026

Partial actual native acceptance covered Dashboard, Advanced navigation, Nodes, empty Assets queue, Marketplace and local Open/cancel. Fixed blank default voice selection (verified after rebuild/restart) and misleading static recognition label (backend regression verified). All 743 backend tests across 42 modules in 108.610 seconds and frontend build/lint passed. No live inference/installations/downloads/paid requests. Existing settings, registry, hardware profile and accepted video unchanged; normal startup created previously absent graph.json.

Release remains pending: private WebView preference persistence, graph/config mirrors, selected-source estimates, active queue/cancellation/recovery, actual optional model execution, independent fresh-video acceptance, resource calibration and clean-machine/platform checks. See [detailed walkthrough](<C:/Projects/Reflow Studio/docs/UI_WALKTHROUGH_ITERATION_2026-10-10.md>) for evidence and automation limitations.

### Preference persistence and graph configuration — 10 October 2026

App-owned UI state now uses a validated transactional ui_preferences.json while the WebView remains private. Preferences hydrate before React mounts; writes are ordered and the normal close button waits for them. Actual portable close/relaunch preserved Advanced mode, and Basic was restored after testing. Graph language/source labels and singleton voice display follow shared render settings; singleton edits update the render choice, duplication saves the current base voice, and removal to one actor restores its choice. Multiple actor choices remain independent; complete native actor-edit acceptance is still open.

All 747 backend tests across 43 modules in 97.031 seconds, eight frontend runtime checks, production build and lint passed. Existing settings/registry/hardware/graph and accepted video unchanged; the new preference file is an intentional state addition. No live model calls, packages or downloads. See [detailed iteration](<C:/Projects/Reflow Studio/docs/PREFERENCE_GRAPH_ITERATION_2026-10-10.md>) for exact evidence, failed-lint-invocation retention, native automation limits and remaining gates. Release readiness remains pending.

### Graph cast estimate controls — 10 October 2026

Public single/all-device estimates now resolve the graph's multi-actor choices using the render acceptance rule. Nodes refreshes estimates after cast changes; queue inspection confirmed only draft/queued jobs participate in pending batch selection. A Windows retry fixture now accounts exactly for injected plus real eligible sharing denials, preserving production's four-attempt limit. The initial failed run remains recorded.

Final backend validation passed 748 tests across 43 modules in 105.360 seconds; frontend build/lint and tested-source/state/video integrity passed. No live models, installs, downloads or new native acceptance. Release remains pending on native controls/recovery, measured resource calibration, full model/video quality and clean-machine/platform checks. [Detailed iteration](<C:/Projects/Reflow Studio/docs/CONTROL_PATHS_ITERATION_2026-10-10.md>).

### Native source selection and recovery dismissal — 10 October 2026

Interrupted-render recovery now distinguishes dismissal from explicit Discard, preserving the record on Escape/close/outside dismissal. Real native controls with disposable state and blocked worker execution verified file selection, pending batch confirmation, rollback on start rejection, recovery dismissal and rejected Resume preservation. These checks do not establish active inference, genuine crash/relaunch, or full model/video quality.

748 backend tests across 43 modules passed in 95.000 seconds; eight frontend runtime checks, production build/lint and source/state/video integrity passed. No dependencies, models, downloads or paid calls. Release remains pending on graph/estimate controls, actual active workflow recovery/cancellation, measured resources, complete model/video acceptance and clean-machine/platform validation. [Detailed iteration](<C:/Projects/Reflow Studio/docs/NATIVE_RECOVERY_ITERATION_2026-10-10.md>).

### Graph controls and populated estimates — 10 October 2026

Late graph loads now display optional switches from shared render configuration; rejected graph-mirror saves warn without discarding future-job choices. Native disposable-state acceptance verified populated CPU estimates, restored target/source labels, voice duplication, actor B selection, four workers and matching estimate/render cast IDs. A rebuilt viewport allows further zoom-out at minimum window width, though the estimate overlay still requires layout work.

748 backend tests across 43 modules passed in 93.562 seconds, alongside eight frontend checks, build/lint and source/state/video integrity. No live models, packages, downloads or paid calls. Native language-menu changes/removal/optional toggles, active-work concurrency/recovery, measured resources, full model/video quality and clean-machine/platform release checks remain open. [Detailed iteration](<C:/Projects/Reflow Studio/docs/GRAPH_CONTROLS_ITERATION_2026-10-10.md>).

## Graph layout validation — 10 October 2026

The Nodes estimate card and render controls occupy separate layout space. Nine frontend contracts, build and lint pass; the isolated native walkthrough validates subtitles at the guarded render boundary and singleton voice changes across graph, Dashboard and estimates. Production backend code did not change and the full backend suite was not rerun. No model calls or dependencies added. Minimum-width overview still needs zoom for detailed editing; other window sizes and active-render layout remain open. Release readiness remains pending. Details: [graph layout iteration](GRAPH_LAYOUT_ITERATION_2026-10-10.md).

## Language and optional-stage acceptance — 10 October 2026

Fourteen frontend contracts and 39 focused backend tests pass, along with build and lint. The isolated native walkthrough verifies source/target changes and optional flags reach estimates and guarded render parameters. Direct graph rejections are visible; bridge exceptions and obsolete reads are handled. Full backend suite was not rerun. No actual engines executed; release still requires active-job/recovery, fresh full-video and clean-machine validation. [Detailed report](REMAINING_CONTROLS_ITERATION_2026-10-10.md).

## Active work and process recovery — 10 October 2026

Native synthetic-worker validation now covers pending cancellation, disabled resume while stopping, cancelled-first/completed-second batch state and recovery-marker cleanup. The active filename, accessible progress and Assets stopping display were repaired. Independent process exit/restart retains and clears the current-render recovery record. Seventeen frontend contracts, 54 focused backend tests, build/lint and integrity checks pass; no full backend rerun or live models. Release remains pending on actual engine cancellation/checkpoint reuse, remaining batch persistence, complete model/video acceptance and clean-machine/platform checks. [Detailed scope and evidence](ACTIVE_WORKER_ITERATION_2026-10-10.md).

## Durable batch restart — 10 October 2026

The queue is now saved atomically and restored paused. Token-based recovery updates the original accepted item; headless synthetic crash/restart verifies retained IDs/settings, current-only resume and subsequent batch failure advancement. Disk-write failure halts the batch rather than skipping the unsaved job. Cue-review publication and reading share a stable transaction lock with bounded Windows replacement retries. Final test/evidence results are recorded in the [durable queue iteration](DURABLE_QUEUE_ITERATION_2026-10-10.md). No new models/dependencies or live inference. Native restored controls, actual provider cancellation/checkpoints, fresh full-video quality, multiple application instances and clean-platform packaging remain release gates.

## Native batch recovery controls — 10 October 2026

Native restored-control acceptance passed using four synthetic jobs inside the real bridge worker lifecycle: current-only recovery, paused remaining jobs, explicit batch resume, pause after current and failure advancement. The final interface returned to Ready with three completed jobs and one deliberately failed job. All 26 evidence checks passed; saved user state/video and previously tested source hashes remain unchanged. This iteration added verification tooling/documentation and did not rerun the full backend suite or execute models. Actual provider cancellation/checkpoints, model/download and resource calibration, fresh full-video quality, multiple-instance behavior and clean-machine/platform packaging remain release gates. Dashboard selection-versus-active-input clarity is also recorded for follow-up. [Detailed scope and evidence](NATIVE_BATCH_RECOVERY_ITERATION_2026-10-10.md).

## Dashboard input identity clarification — 12 October 2026

The active/stopping input is now labelled separately from the next pending selection. Estimate and expert-configuration text explains selected versus accepted settings. Four Dashboard component contracts and build/lint passed; saved state/video remain unchanged. No backend/native rerun, live engines or new dependencies. Native layout acceptance and the previously recorded real-engine, download, resource, multi-instance and clean-platform gates remain pending. [Detailed iteration](DASHBOARD_INPUT_CLARITY_ITERATION_2026-10-12.md).

## Live short-video recovery acceptance — 12 October 2026

Installed offline engines produced a real 6.9-second Hindi output with subtitles and background/dubbed/master/vocal stems. Fixed-seed Demucs separation permits exact-audio checkpoint reuse after real IndicF5 cancellation; restart skipped recognition/translation inference and generated new speech. Fifteen independent output/recovery checks, six native Dashboard checks, 763 backend tests and 13 final integrity checks passed. The user accepted this exact output as natural, correctly timed and without audible English. No new models/dependencies or paid calls; saved state/earlier media remain unchanged. Verification metadata failures and corrections are retained and explained in the [iteration report](LIVE_WORKFLOW_ITERATION_2026-10-12.md).

Release is still pending: a dense eight-second excerpt requires 10.027 seconds of native Hindi delivery and stops for review. General duration-aware localization, long/music-rich/multispeaker workflows, other languages/optional stages, actual native model-running process-crash recovery, calibrated resource estimates, download/retry behavior, multiple instances and clean-platform packaging remain gates. Acceptance of one short proper-name-heavy phrase does not establish those features.

## Video dialogue review and adaptation evaluation — 12 October 2026

Existing video cue review is now reachable from Dashboard's standard dubbing template. Six component checks, 89 focused backend tests, build/lint and integrity passed. The installed IndicTrans2 alternatives did not solve the eight-second overflow; no candidate wording or audio was accepted/applied. No new writer model or service was added. Automatic shortening, native acceptance of the new review route and the previously listed release gates remain pending. [Detailed timing iteration and optional evaluation proposal](TIMING_TRANSLATION_ITERATION_2026-10-12.md).

## Windows portable release audit — 12 October 2026

The user selected Windows portable as the first release target; Linux/macOS remain experimental. Added a per-folder desktop ownership lock and corrected the portable instructions. Full backend regression passed 766 tests across 45 modules, 47 frontend contracts passed, frontend build/lint passed, and 15 current-source/state/media/evidence checks passed. Two existing frontend build dependencies were patched; full npm audit now reports zero advisories. A 2.825 GB model-free candidate passed nine inventory/relocation/core checks and native onboarding, review-panel visibility, duplicate-launch rejection, close/relaunch and preference persistence observations. It remains a used QA copy, not a pristine release ZIP.

All six existing dependency probes pass after an F5 recheck; its initial timeout is retained. Current core XTTS passed real offline token-boundary cancellation in 0.094 seconds with output preservation and workspace cleanup. These results do not establish all-engine or all-language quality.

The approved temporary Ollama/Qwen dialogue trial was unsuccessful as a quality gate: one service timeout, one fitting rewrite flagged as changed meaning and no fitting dense-passage alternatives. Nothing was applied. Its runtime/archive/models/temporary keys and caches were removed (5.965 GB); independent cleanup audit passed seven checks.

**Release readiness remains pending.** The shared runtime's dependency check fails and multiple package-version metadata overlaps exist. A separate runtime repair requires the pending user approval. Fresh users also lack a complete in-app setup path for the validated gated Hindi engines and confirmed voice references. Representative full workflows, native model-running crash recovery, calibrated resource/download/optional-route acceptance and clean-machine Windows verification remain open. The application license is undecided; FFmpeg distribution material and exact model/runtime terms require preparation. Current CI produces experimental executables rather than the verified portable recipe. See the [consolidated release iteration](WINDOWS_RELEASE_ITERATION_2026-10-12.md), [licensing discussion brief](LICENSE_DECISION_BRIEF_2026-10-12.md) and [final evidence integrity](validation/2026-10-12-windows-release-integrity.json).

## Runtime repair planning — 13 October 2026

The user requested discussion before package installation, then approved preparation of the dependency map and pinned repair plan and, separately, only the Docopt helper build and dependency-lock preparation. The verified 25,901-byte Docopt source archive was downloaded; a 13,857-byte wheel was built with existing tools and tested without installation. The metadata-only resolver completed, and independent Windows/Python 3.13 checks produced an 85-package XTTS candidate lock with 128 satisfied active dependency links. Required artifact sizes total 279,567,278 bytes (about 266.6 MiB), excluding the proposed Python interpreter and extracted runtime. No runtime was installed, published wheel archives downloaded or models loaded/downloaded. Fifteen root checks still pass. Actual candidate execution, installed footprint and licensing/notices acceptance remain pending; package installation is not authorized by this approval. [Detailed helper, lock and package inventory](XTTS_DEPENDENCY_LOCK_PREPARATION_2026-10-13.md).

The original RVC dependency family cannot share the proposed modern XTTS NumPy version; its malformed OmegaConf requirement and missing Fairseq Windows wheel require a separate reviewed repair path. Existing Python 3.10 profiles remain protected baselines, but that branch reached end of support on 1 October 2026 and all release profiles need supported-runtime acceptance. Main-process imports, integrity checks, worker routing, cache identity and absolute profile dependency paths also need coordinated code repairs before a minimal desktop candidate can replace the shared runtime. No production code changed in this planning pass. [Detailed map, pins, reasons, phases and unresolved gates](RUNTIME_REPAIR_PLAN_2026-10-13.md).

## Isolated XTTS runtime acceptance — 13 October 2026

The user subsequently approved the reviewed candidate creation/testing. The separate Windows Python 3.13.16 CPU candidate installed all 85 pinned packages with zero duplicate metadata and passed 14 real runtime checks. Existing XTTS weights generated 5.42 seconds of non-silent 24 kHz speech; real token-boundary cancellation took 0.168 seconds and preserved the completed output. The loaded model was reused and owned generation workspaces were removed. The unchanged existing Whisper worker recognized the sentence with zero normalized word errors. This is technical English-checkpoint acceptance, not human naturalness or full-video/all-language acceptance.

The candidate measured 960,336,065 bytes after installation. Owned installer/wheel staging was removed (291,023,750 bytes). All five protected state hashes, eight original XTTS asset hashes and previously tested production-source hashes remain unchanged. The earlier Ollama trial remains absent. Failed preparation/offline-check attempts remain documented; corrected actual runtime and speech checks were rerun successfully.

**Release remains blocked.** Exact-version advisory lookup returned matches for Torch and Transformers; this candidate remains offline-evaluation-only and was not selected by the app. Package notices were collected for 83/85 packages; tokenizers and tensorboard-data-server need exact-source notice follow-up. Compatible security remediation, isolated app-worker integration, other runtime families and the prior release gates remain required. No application license was chosen. [Detailed candidate iteration, measurements, advisories and evidence](XTTS_RUNTIME_CANDIDATE_ITERATION_2026-10-13.md).

## XTTS replacement lock and persistent session bridge — 13 October 2026

A development-only XTTS worker passed nine real checks through the unchanged `FeatureSession` interface: two speech requests reused one process/model; invalid language produced no output; token-boundary stop exited in 1.437 seconds, preserved completed speech and removed the parent workspace. This is session-interface acceptance using the existing offline candidate, not production provider/default integration or validation of a newer runtime.

A separately reviewed CPU replacement lock contains 99 packages and 143 satisfied target dependency links. It proposes Torch 2.14.1+cpu, TorchAudio 2.11.0+cpu, TorchCodec 0.17.0+cpu and Transformers 5.19.0, keeping Coqui TTS 0.27.5 and the existing Python/checkpoint. Six versions change and fourteen transitive support packages are introduced. Exact wheel sizes total 304,189,555 bytes; public OSV lookup found zero current matches. Eleven consolidated planning/session/state checks passed. No replacement archive was downloaded or runtime modified. Major Transformer/model compatibility, installed footprint and package notice review still require an approved separate installation and real evaluation. All original saved state, XTTS assets and tested production sources remain unchanged. [Reviewable replacement plan and session evidence](XTTS_SECURITY_AND_WORKER_PLAN_2026-10-13.md).

## Approved replacement runtime execution — 13 October 2026

The user subsequently approved the separate replacement runtime and tests. The exact 99-package CPU stack is installed separately, using the verified existing Python bootstrap and models. Fourteen runtime checks, real 5.42-second/24 kHz speech, 0.080-second token-boundary cancellation, nine persistent-session checks and the existing Whisper recognition cross-check passed. The sentence had zero normalized word errors; new human naturalness/full-video acceptance was not claimed.

Coqui's removed Transformer helper and elided dense attention mask required an exact-version evaluation adapter using native Torch and modern generation/cache handling. All failed trials remain retained. The adapter changes no installed third-party source; 13,902 Python source files across all 99 distributions match RECORD hashes. The candidate measured 1,055,079,244 bytes after installation; 304,210,617 bytes of owned staging were removed. Original saved state, model assets, tested production sources and both comparison runtimes remain preserved.

The reviewed package lock has no current OSV matches, but this does not certify all native/model components or upgrade the original/GPU/other optional runtimes. Production provider/readiness/cache wiring, broader generation/reference/language/device cases, remaining warnings, licensing/notices, full workflows and clean-machine/native release gates remain pending. App defaults are unchanged; release eligibility remains false. [Detailed replacement iteration and final evidence](XTTS_SECURITY_RUNTIME_ITERATION_2026-10-13.md).
 
## XTTS production integration — 13 October 2026

The approved CPU replacement now has an opt-in application provider and persistent job-owned worker. Real provider model reuse, output preservation after a forced child crash, new-job recovery and workspace cleanup passed. Runtime recipe identity is recorded in manifests and checked during setup inspection. After explicit environment-corrected reruns, 778 discovered backend cases pass; the initial failed raw report and two excluded standalone scripts are documented. Current settings and default engines remain unchanged. This is not native whole-app or full-video release acceptance. See [the detailed integration record](XTTS_PRODUCTION_INTEGRATION_2026-10-13.md) and [consolidated evidence](validation/2026-10-13-xtts-production-integrity.json). Packaging/default migration, the other runtime families, broader workflows, licensing and clean-machine release gates remain open.
 
## Saved XTTS selection and relocated portable acceptance — 13 October 2026

Settings now exposes the optional isolated CPU XTTS runtime; rendering, setup inspection and cue review use the saved selection. The current runtime remains the default. A fresh portable QA copy includes the validated runtime and its previously omitted dependency lock. Live relocated speech, stage-worker exit with the enclosing job preserved, token-boundary cancellation, output preservation and cleanup pass all 11 checks. A slow-shutdown bug was fixed to terminate only the exact owned session process instead of cancelling later render stages. The final complete backend suite passes 790 tests; 17 frontend graph/control contracts and 12 final integrity checks pass. Protected original state and model assets remain unchanged. The retained QA copy measures 3,879,984,638 bytes with the optional runtime. Native selector interaction, clean-machine acceptance, the other runtime families, broad model/workflow quality and licensing remain release gates. [Detailed iteration, failures and final evidence](XTTS_SELECTION_AND_PORTABLE_ITERATION_2026-10-13.md).

## Desktop boundary corrections — 13 October 2026

Latest source fixes isolated-XTTS preflight routing, allows desktop imports when legacy Torch is absent or its DLL is broken, and separates desktop integrity from optional shared AI diagnostics. The complete backend suite now passes 800 tests. Two real subprocess probes also pass desktop imports, four-template listing and source-subtitle export with AI imports blocked; no native window or clean runtime installation was tested. All protected user-state/model hashes and isolated-runtime identity remain unchanged, with Ollama still absent. The earlier portable QA copy remains its historical tested snapshot and has not received these edits. **Release remains blocked** on the actual clean-runtime migration, remaining engine/workflow acceptance, native clean-machine checks and licensing. [Detailed current iteration](DESKTOP_RUNTIME_BOUNDARY_ITERATION_2026-10-13.md).

## Clean desktop package proposal — 13 October 2026

A revised metadata-only proposal covers 31 packages, 22 satisfied declared dependency links and about 23.54 MiB of published artifacts. Older proposed Pillow/Requests pins were revised after advisory matches; the revised point-in-time package scan reports zero matches. Five offline planning tests and eight integrity/preservation checks pass. No production source, runtime or user state was changed. Required `proxy-tools==0.1.0` has only a source archive, so its reviewed helper build and subsequent real resolver acceptance remain prerequisites to an installable desktop lock. No desktop installation/native acceptance is claimed; release gates remain open. [Reviewable proposal and bounded next approval](DESKTOP_RUNTIME_PROPOSAL_2026-10-13.md).

## Approved helper and final desktop lock — 13 October 2026

The approved proxy-tools helper build and genuine metadata resolver are complete. Its wheel passed actual Python 3.13 execution without installation; source/wheel/notice hashes and RECORD entries were verified. The final target lock contains 31 packages, 22 satisfied active links and 24,686,927 artifact bytes. Three host-only dependencies are excluded and the final exact-version advisory query has zero current matches. All 12 integrity/preservation checks pass. No desktop runtime was installed, production default changed, or native acceptance claimed. The helper archive's missing notice and MIT/BSD label conflict are documented with a pinned supplemental notice; distribution review remains open alongside all earlier release gates. [Detailed completion and separate installation scope](DESKTOP_HELPER_AND_LOCK_COMPLETION_2026-10-13.md).

## Separate desktop candidate acceptance — 14 October 2026

The approved 31-package Python 3.13 candidate passes installed dependency/origin checks, native WinForms/WebView2 tests, six-screen and saved-selector walkthrough, credential/audio/state operations, real isolated XTTS speech/cancellation and 438 scoped desktop tests. All 1,793 payload files are verified; package notices are collected for all 31 distributions. Original source/state/models are preserved and installer staging removed. The candidate is about 87.14 MiB, excluding the application/media/AI assets; current defaults remain unchanged. **Full release approval still fails:** the broad suite reports one failure and twelve errors because default AI dependencies/routes are not migrated, and full workflows, clean-machine/native acceptance and licensing remain incomplete. [Full results, retained failures and remaining architecture work](DESKTOP_CANDIDATE_ACCEPTANCE_2026-10-14.md).

## AI boundary repair and recognition plan — 15 October 2026

Two unnecessary Torch imports were removed, allowing the existing HTTP translation wrapper and faster-whisper handler boundary to load independently of Torch. Full working-runtime acceptance passes 802 tests; focused desktop local translation also passes. The recognition candidate is planned, not installed: 24 packages, 31 valid target links, about 81.37 MiB of downloads, zero current package advisory matches. Offline reuse/conversion of the existing Whisper turbo checkpoint is proposed without model downloads. Source/state/model preservation checks pass; full release remains blocked on actual worker migrations and all earlier acceptance/licensing gates. [Detailed iteration and reviewable next scope](RECOGNITION_MIGRATION_PLAN_2026-10-15.md).

## Recognition candidate: quality approval failed — 15 October 2026

The approved separate runtime/conversion is technically working: exact English recognition, silent/corrupt/metadata fixtures, desktop worker errors/cancellation, 807 regression tests and 2,316 payload checks pass. Automatic recognition of the confirmed Hindi reference instead returned Urdu script; the explicit Hindi diagnostic still measured about 25.8% word errors. Overall recognition approval remains false, with no default change. Source-hint propagation, language/script ambiguity and broader quality must be resolved before promotion. Installer/cache cleanup and original-state/model preservation pass; package notice follow-up and all prior full-release gates remain open. [Detailed partial acceptance](RECOGNITION_CANDIDATE_ACCEPTANCE_2026-10-15.md).

## Explicit recognition source-language repair — 15 October 2026

Source-language selections now reach both local recognition workers, rather than being applied only after recognition. Real CPU/GPU Hindi-hint checks each pass nine assertions; hinted transcripts retain no automatic detection confidence. Recognition cache keys include the selection, and translation cache validation preserves its origin. The working-runtime suite passes 815 tests; 79 overlapping scoped desktop tests also pass, including four added afterward. No package/model/default changes were made. The historical source verifier flags the deliberately modified pipeline; its other preservation checks pass, and a separate current-source receipt records that expected difference. Automatic Hindi/Urdu ambiguity, actual recognition accuracy, per-feature production routing, licensing and other release gates remain open. [Detailed repair, evidence and retained failed attempts](RECOGNITION_LANGUAGE_REPAIR_2026-10-15.md).

## CPU recognition runtime connected — 16 October 2026

An explicit isolated CPU recognition choice now connects settings, frozen jobs, preflight, worker execution, engine inspection, run evidence and portable inventory. Actual saved-setting-to-pipeline acceptance passes 18 checks without AI packages in the desktop parent, despite an invalid global worker override. Native WebView2 passes 26 checks including the selector; backend acceptance passes 831 tests and final desktop-scoped acceptance passes 104 overlapping tests. Payload/state/model preservation passes; expected source changes are recorded separately. No packages/models were installed and the default stays legacy. Automatic language/accuracy issues, remaining engine migrations, clean-machine/full-workflow acceptance and licensing remain open. [Full iteration](RECOGNITION_RUNTIME_ROUTING_2026-10-16.md).

## NLLB translation worker connected — 16 October 2026

Selected NLLB models now have an explicit isolated CPU trial using the existing approved modern package environment. Frozen settings, real preflight, readiness, stage-owned persistent translation, run evidence and review cleanup are wired. Real worker acceptance passes 13 checks, including repeated cues in one process and decoder cancellation/release in 0.572 seconds; native selector acceptance passes 22 checks. Full backend regressions pass 846 tests and focused desktop regressions 76 overlapping tests. No package/model/default change was made. M2M100 still requires a reviewed SentencePiece-compatible separate environment; semantic quality, other engines and all broader release gates remain open. [Detailed implementation, evidence and retained failed harness run](NLLB_RUNTIME_ROUTING_2026-10-16.md).

## M2M100 repairs and reviewable runtime proposal — 16 October 2026

M2M100 now validates the target token before generation and explicitly releases its owned local weights on stage completion, errors and generator close. Failed initialization drops partial references. Full regressions pass 853 tests and focused checks 17 overlapping tests. A metadata-only proposal contains 41 packages: 40 copied from the existing verified environment plus SentencePiece 0.2.2's 1,247,987-byte Windows/Python 3.13 wheel. All 48 active dependency links validate; the current 41-version OSV query has zero matches, without implying security certification. Saved state, existing runtimes and model hashes are preserved; no archives or new runtime were created. Installation and live M2M100 worker acceptance await explicit package approval. [Exact plan and approval scope](M2M100_RUNTIME_PLAN_2026-10-16.md).

## M2M100 separate CPU trial accepted technically — 16 October 2026

Following explicit approval, the separate 41-package translation candidate is built from 40 existing packages and the pinned SentencePiece 0.2.2 wheel. Settings, frozen execution, preflight, readiness, manifest evidence and portable inventory support explicit isolated selection; defaults remain legacy. Actual offline subtitle pipeline/session/cancellation checks pass 17 assertions, candidate native checks 56, native interface checks 22, backend regressions 867 and focused regressions 73 overlapping tests. Owned staging cleanup removed 1,248,026 bytes; original runtime/state/model hashes are preserved. Installed notices cover 39 packages, with separately recorded official version-tag supplements for the other two; legal clearance remains open. Full video, semantic quality, remaining engine migrations, clean-machine and other release gates remain open. [Detailed acceptance and evidence](TRANSLATION_CANDIDATE_ACCEPTANCE_2026-10-16.md).

## Separation runtime boundary audited — 16 October 2026

Real one-second separation succeeds only with the original portable worker; the modern desktop lacks Torch and the translation runtime lacks Demucs. Cancellation now preserves RenderCancelled, fixed status text works in a legacy Windows console encoding, and a bounded no-model Demucs probe is available. Backend regressions pass 878 tests and desktop-focused checks pass 24 overlapping tests; actual active-child cancellation returns in 0.117 seconds with cleanup. Original state/model/runtime identities remain preserved. No packages or model archives were downloaded or installed. Metadata inspection identifies ten additional Demucs dependencies, including four source-only package versions needing an approved helper-build step before a lock/runtime proposal. Clean separation routing, quality and full-release gates remain open. [Audit, retained failures, exact source artifact hashes and next approval scope](SEPARATION_RUNTIME_AUDIT_2026-10-16.md).

## Approved Demucs helpers and prepared lock — 16 October 2026

The four approved source archives (1,476,709 bytes) produced verified pure-Python wheels with 126 byte-matched source files. Python 3.13 acceptance passes 14 bounded checks, including real resampling and a modern audio-writer roundtrip. Code inspection added the existing TorchCodec package as an operational requirement missed by declared dependencies. The final 32-package lock passes a genuine metadata-only resolver and independent artifact/requirement review; the 32-version OSV query has zero current matches. A missing ANTLR notice is supplemented from the official release tag without altering the wheel. Cleanup removed 4,881,561 bytes of owned staging; original sources/state/model/runtime identities are preserved. No separation runtime is installed. The separate installation proposal uses 22 copied packages, four existing built wheels and six downloads totaling 365,848 bytes; defaults stay unchanged pending approval. [Detailed completion, retained failures and next scope](SEPARATION_HELPERS_AND_RUNTIME_PLAN_2026-10-16.md).

## Approved isolated CPU separation integrated — 16 October 2026

The approved 32-package candidate is built separately (615,796,387 bytes), with 365,848 bytes of pinned wheel downloads and existing Demucs weights. Saved explicit trial selection now reaches frozen audio/video jobs, correct isolated preflight, readiness/probe, manifest evidence and portable inventory; defaults remain legacy. A precise legacy NumPy scalar alias repairs restricted checkpoint loading without unrestricted pickle or package-source changes. Actual repeated stereo PCM16 stems match, cancellation returns in 0.111 seconds, native dependencies pass 48 checks, native interface 22, full backend regressions 891 and focused desktop checks 46 overlapping cases. A real six-second English video with separation/recognition/XTTS passes nine checks and fully decodes, but takes 213.997 seconds on CPU and does not validate Hindi or audible leakage/naturalness. Owned staging cleanup removes 365,886 bytes; original state/models/runtime identities remain preserved. Remaining engines, broader workflows/performance, fresh portable/clean-machine/manual and licensing gates remain open. [Complete implementation, evidence and retained failures](SEPARATION_CANDIDATE_ACCEPTANCE_2026-10-16.md).

## Remaining voice/visual engines audited and repaired — 16 October 2026

RVC and Wav2Lip now preserve RenderCancelled; fixed Wav2Lip status strings work in a cp1252 test. Detector/enhancer wrappers defer heavy imports, allowing actual existing NudeNet filtering from the clean desktop: eight checks pass, including failed-input output preservation. Actual legacy GFPGAN runs three face-model forwards and publishes three decoded frames in 92.329 seconds; legacy Wav2Lip also produces a valid one-second/three-frame result in 11.875 seconds. All 896 backend regressions and 21 overlapping focused checks pass. RVC/GFPGAN/Wav2Lip still lack clean desktop engine runtimes. MuseTalk dependency checks pass without new full rendering. F5 remains unverified after bounded startup timeouts, with a captured stack inside Transformers import-structure construction. Scoped inventory finds 37 registered voice entries, none installed and no usable RVC checkpoint in searched project/registered locations. No packages/models/defaults changed; protected state and all five isolated runtime identities remain preserved. [Detailed observations, tests, source changes and release gaps](REMAINING_ENGINE_AUDIT_2026-10-16.md).

## F5 startup repair follow-up — 16 October 2026

The optional base F5 worker now defers unnecessary ASR/training imports through an exact-version/source-hash adapter without editing installed packages. Bounded API startup passes in 17.86 seconds; the unchanged 90-second probe passes. Actual reference ASR matches the expected English words and releases its model; actual speech after reference-before-model ordering passes in 182.282 seconds on CPU. Final regressions pass 907 backend and 40 overlapping focused tests; all 11 preservation/acceptance checks pass. Protected state, tested upstream/model assets, built frontend and all five prior runtime identities remain preserved. No dependency/model/default changes were made. Hindi quality, a complete automatic-reference/persistent F5 render, GPU performance and broader release gates remain open. A metadata-only visual proposal identifies two source helpers requiring bounded owner approval before download/build; no visual runtime is installed. [Detailed repair, limitations and next approval scope](F5_STARTUP_REPAIR_AND_VISUAL_PLAN_2026-10-16.md).


## Visual helper preparation completed; security gate remains — 16 October 2026

Two approved sources (350,509 bytes) produced verified wheels with 128 byte-matched Python sources plus one generated version file; seven real helper checks pass under Python 3.13. Actual target metadata resolution and independent artifact review confirm 55 packages/96 active dependency edges. Two advisory records alias one BasicSR vulnerability (CVE-2024-27763); the lock remains security_clear=false. A no-install prototype blocks three distributed-training launchers with zero shell calls, but production mitigation and real modern GFPGAN inference remain untested. All 18 final preservation/preparation checks pass and 2,771,202 bytes of owned staging were removed. No runtime/model/default changes occurred. Separate proposed installation uses 41 copied packages, two retained helpers and 12 pinned downloads (64,466,647 bytes); explicit approval and guarded acceptance are required. [Full iteration, failures, exact inventory and next scope](VISUAL_HELPERS_AND_RUNTIME_PLAN_2026-10-16.md).

## Isolated CPU face enhancement technically validated — 16 October 2026

The approved separate 55-package visual candidate is installed with 64,466,647 bytes of pinned wheel downloads and existing local GFPGAN/detector/parser weights. Exact-source application guards disable BasicSR distributed training and adapt its old TorchVision import without changing installed package bytes. A lightweight media helper split removes an accidental audio/pipeline dependency from frame processing. Real restoration/failure/cancellation passes ten checks (three model forwards; cancellation 0.119 s), native dependencies 74, native interface 22, and post-processing pipeline integration nine with an explicitly substituted source-audio fixture. Final backend regressions pass 930 tests and focused checks 48 overlapping tests. A full generated dub separately fails the timing guard (6.605 s needed, 6.000 s available) before enhancement; it is not counted as successful dubbing. All 21,572 recorded payload files verify; runtime size is 1,048,855,925 bytes with no cache directories. Cleanup removed 64,466,681 bytes of owned staging. Existing user state, five established runtime identities and tested assets are preserved; defaults stay legacy. The upstream BasicSR advisory remains recorded, one distribution lacks an installed notice, and speech timing, broader workflows/performance, GPU, fresh portable/clean-machine and licensing gates remain open. [Complete iteration, failures, provenance and measured acceptance](VISUAL_RUNTIME_ACCEPTANCE_2026-10-16.md).

## Speech timing mechanics repaired; dense-line adaptation remains open — 16 October 2026

Non-Hindi fitting no longer slows short speech to fill a window; final cues may use actual remaining media time in sequential and parallel execution. Native preflight uses the same bounded media window, with existing ASR rounding tolerance capped at source end. Audible overflow retains a complete hash-verified take and a needs-review report instead of losing the generated audio. A single seeded English XTTS diagnostic produced 10.209 s for the dense six-second line, with only 0.416667 s of exact trailing silence; actual replay at the existing 1.3x limit still needs 7.853 s. Seven replay checks pass with no further model calls; the original six-second cue remains incomplete. Final backend regressions pass 936 cases, focused acceptance 131 overlapping cases, and all nine preservation/acceptance checks pass. Six established runtime identities, original XTTS assets, protected state and built frontend are preserved; no new packages/models/defaults/external AI calls occurred. Dialogue assistance is off with no configured instruction model. Automatic wording adaptation, full-workflow quality and prior release gates remain open. [Detailed diagnosis, repairs, failed attempts and evidence](SPEECH_TIMING_REPAIR_2026-10-16.md).
