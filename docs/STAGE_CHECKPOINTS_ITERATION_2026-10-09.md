# Verified stage recovery and review cue provenance — 9 October 2026

## Purpose and scope

This increment implements the next part of the approved architecture plan: recover completed recognition and translation work after a later failure, and carry the common cue contract into saved reviews. It extends the fixed-template pipeline foundation. It does not introduce a different dubbing engine, a trained reviewer, a new framework, or another manually polished sample.

The production sequence remains preprocessing → optional background separation → recognition → optional translation/moderation → speech generation → timing/mixing → optional visual processing → export. Cached text stages can replace recognition and translation calls only when their fingerprints and saved payloads pass verification. Preprocessing, media checks, speech generation, timing and export still execute.

The first supported recovery pair is the explicitly selected local Whisper Turbo and IndicTrans2 adapters. These are the real engines used in the current English-to-Hindi workflow. Other recognizers/translators, API connections, Ollama, default unregistered engines and translation combined with a profanity filter are deliberately ineligible in this increment. They continue to call their providers. Supporting another engine requires checking its actual runtime, assets and fallback behavior before enabling its checkpoints.

## What changed

| File | Change and reason |
| --- | --- |
| `core/stage_checkpoints.py` | Adds content fingerprints, bounded checkpoint loading, semantic payload checks, atomic publication and explicit reuse events. Keeps generated speech outside the cache. |
| `core/pipeline.py` | Connects recognition recovery and a shared translation iterator to audio, video and subtitle paths. Each normal run owns its checkpoint manager; the previous manager is restored on exit. |
| `core/run_manifest.py` | Records supported checkpoint stages and a checkpoint ledger separately from provider operations. A hit retains producer/run provenance and a new durable copy of the reused cues. |
| `core/json_store.py` | Adds four bounded attempts for Windows access/sharing denials during atomic replacement; old saved bytes survive permanent failure. |
| `core/render_state.py` | Updates the recovery description: an interrupted job is re-executed, with verified supported text stages reusable. It is still not a continuation of an interrupted speech worker. |
| `core/review_cue_contracts.py` | Adds stable identities, original-source fields, correction fields, lineage and conservative legacy migration to reviews. |
| `core/cue_review.py` | Integrates those contracts with preparation, edits, retranslation, combinations, explicit saves and read-only loads. Existing revision and audio-integrity checks remain active. |
| `frontend/src/lib/api.ts` | Adds optional cue identity to the review response type. |
| `frontend/src/components/shared/CueReviewPanel.tsx` | Uses the cue identity as the selection-row key, retaining an index fallback for old responses. |
| `frontend/package.json` | Restricts the existing lint command to application source. The previous bare command also inspected installed dependency code and declarations. No linter was added. |
| `dev/test_stage_checkpoints.py` | Exercises reuse, content invalidation, corruption, incomplete work, unsupported routes and review provenance using disposable assets. |
| `dev/test_cue_review.py` | Adds persisted legacy-read and original-source edit checks. |
| `dev/test_pipeline_foundation.py` | Updates the prior checkpoint-support expectation for the new capability. |
| `dev/run_cleanup_checks.py` | Includes the new checkpoint tests in the curated backend runner. |
| `dev/verify_stage_checkpoints.py` | Runs the existing full known sample twice through the normal offline pipeline to verify recovery using actual models. |
| `dev/verify_subtitle_checkpoint.py` | Verifies actual subtitle export and translation reuse after repairing the shared iterator compatibility issue. |
| `dev/test_persistence_safety.py` | Adds transient-success and permanent-denial checks for the shared atomic save, including old-file and staging-file preservation/cleanup. |
| `dev/test_feature_session.py` | Bounds retries for transient Windows sharing denials in the disposable fixture worker. It still fails on persistent denial; production worker/model errors are not hidden. |

All paths above are relative to `C:/Projects/Reflow Studio`. The working tree already contained substantial changes from earlier iterations; this table identifies the additional scope of this increment rather than describing the entire diff against Git HEAD.

## Checkpoint identity and invalidation

Every eligible stage fingerprints its selected registry entry, adapter identity, installed model files, isolated runtime files, Python files under `core`, and root `config.py`. Files are hashed by content, with relative names included in the tree digest. A file that changes size or modification time during hashing causes fingerprinting to fail. Links and Windows reparse points in used fingerprint/cache paths are rejected. Generated `__pycache__`, `.cache` and `.git` directories are excluded.

The fingerprint also includes the original input's SHA-256. Recognition includes the actual decoded/separated audio hash, PCM duration and grouping mode. This avoids treating two different separation outputs as the same recognition input. Temporary job paths are excluded, so a new job workspace can reuse the same verified content.

Translation includes the complete canonical incoming transcript and recognition metadata, resolved source language/origin, target language and custom instructions. Consequently, edits to cue text, identity, grouping, timing or recognized-language metadata invalidate the translation stage. Reuse never swaps a new target language onto an old translation.

| Change | Recognition | Translation |
| --- | --- | --- |
| Original source bytes | Invalidated | Invalidated |
| Decoded/separated recognition audio or grouping mode | Invalidated | Invalidated if the resulting transcript changes |
| Recognition model/entry/runtime | Invalidated | Invalidated if its transcript or source resolution changes |
| Translation model/entry/runtime | Reusable | Invalidated |
| Translation target/source selection or instructions | Reusable | Invalidated |
| Selected voice, speech device, export styling | Reusable when grouping is unchanged | Reusable when incoming text/language is unchanged |
| Relevant core/config source code | Conservatively invalidated | Conservatively invalidated |
| Unsupported provider or selected translation moderation | Recognition eligibility unchanged | Provider executes; no translation reuse |

The code fingerprint is intentionally conservative: a change elsewhere in `core` may invalidate both stages even when that particular change would not alter their output. Refining stage-specific dependency fingerprints is future optimization. Fingerprints are memoized only within a single run, not trusted across sessions. Changing a selected entry's descriptive metadata also invalidates its stage because the full entry configuration is hashed.

This is local reproducibility evidence, not a claim that every external dependency is frozen. GPU drivers, hardware, external environment changes and mutable artifacts changed during inference are not made immutable. The excluded cache directories are not independently verified. Users should not modify active runtimes/models during a job. The next run rehashes included artifacts.

## Saved records and failure behavior

Checkpoint files live under the current output folder's `stage_checkpoints/<stage>/<fingerprint>.json`. Each file is one atomic publication containing a version, stage/key, canonical transcript payload, payload SHA-256, originating run identifier and actual producer identity. There is no separate header that can commit an incomplete payload. Concurrent writers may publish equivalent valid stage results under the same key; a reader observes one complete publication rather than a partially written JSON file.

Loading is bounded to 32 MiB. The loader checks the envelope identity and payload hash, then checks canonical cue IDs, uniqueness, original/current text fields, finite ordered cue windows and lineage fields. Recognition is checked against the decoded PCM duration. Translation must preserve incoming cue identity, source text, timestamps, parent lineage and recognition metadata, and its effective text must equal its raw translated text. The latter is why moderated translations are not stored here.

Missing files produce a miss. Invalid, truncated, oversized or unreadable records produce an invalid event and fresh provider execution. They are not accepted because their filenames look plausible. Cache read and write I/O failures are recorded; missing/corrupt reads trigger normal provider execution. Invalid stage payloads and unsafe publication paths are rejected rather than treated as successful checkpoint writes. Model/provider failures and cancellation propagate normally. A complete translation checkpoint is published only after the iterator has translated every cue and completed; stopping after a yielded cue does not publish the stage.

The run manifest's `checkpoints` ledger distinguishes disabled, miss, invalid, stored, hit and not-stored events. A hit contains the original producer/run identity and payload digest. Reused cues are copied into the new run's durable cue-artifact directory. No recognition or translation inference operation is fabricated for a hit. Logs identify reuse with `[CHECKPOINT]`.

The existing interrupted-job action re-enters the normal pipeline with the saved input and parameters. Ordinary rerenders use the same verification mechanism. A later timing failure can therefore leave usable text checkpoints. It does not create an accepted dub. There is no per-cue translation recovery, speech/audio cache, visual checkpoint, automatic eviction policy or checkpoint-management UI in this increment. Checkpoint JSON is disposable; run evidence is kept separately.

## Review cue contract and migration

Review JSON retains its existing version-1 shape and index/revision API. Each cue additionally carries `cue_id` and a nested `cue_contract` using `reflow.cue.v1`. The outer source/target text and timing remain the editable review fields; the nested contract keeps the original source text and original recognized window, raw translation where known, effective/adapted text, corrected source text, current timing and revision.

A text/timing edit retains the cue identity and original-source fields. Source corrections are recorded separately. The existing rules still clear candidate/accepted audio on text changes, recalculate fit on timing changes and reject a timing change that cuts accepted speech. Explicit saves synchronize the nested current fields. Persisted contracts with duplicate identities or disagreement between nested and outer text/timing are rejected on load.

Retranslation records the new raw provider result in the same contract before any selected filtering. Correcting the source line does not rewrite the original recognized source. Combining adjacent cues creates a child ID derived from both parent IDs, retains their source fragments and lineage, and clears only the combined cue's takes. Unrelated cues keep their IDs and saved takes even when their array positions change.

Legacy reviews without contracts are upgraded in memory on load. Their deterministic IDs include the review identity and original current cue index/window/text. They are labelled `legacy-current-review-snapshot`, with `original_source_known=false` and no invented raw translation. That old text may already contain edits, so it cannot be presented as a verified original model result. Reads do not rewrite JSON or increment its revision. A subsequent explicit save persists the added fields.

Newly prepared reviews retain recognition provenance and translation fields directly from the recognized canonical cue. The recognized original window remains available even where the existing 50 ms rounding tolerance clamps the review's editable window to the decoded source duration.

## Validation and observed results

Final validation results and live receipts are recorded below. The initial restricted-temp test attempt encountered Windows sandbox rename denials; focused checks were rerun using the workspace-owned test directory. That environmental failure is not counted as a passing product check.

The first live attempt was stopped before model inference because runtime fingerprinting redundantly walked all ancestors for every file. The implementation now validates the root and each walked child once, while still hashing every included file and checking file stability. The interrupted attempt's folder/log are retained as investigative evidence, not successful recovery validation.

The frontend TypeScript/production build passed. It reported the existing large-bundle warning. Application-source lint reported warnings without errors; the original unscoped lint attempt inspected dependency declarations and failed. The lint script correction prevents that irrelevant dependency scan. Existing hook/component-export warnings are not claimed fixed by this increment.

### Findings from the first full suite

The first full run executed 625 tests in 192.818 seconds and reported one failure and three errors. Its saved-state integrity check passed. The failing checks were investigated rather than counted as validation success:

- Two subtitle checks exposed an actual regression: subtitle parsing uses a plain list, while the new shared translation iterator assumed a `TranscriptionResult`. The helper now normalizes a copy for its checkpoint input envelope and normalizes the completed payload before storing it, while retaining the original caller's list and progress events.
- A competing review-save process exposed an existing `exists()`/`lstat()` race on the disappearing file-lock path. The path guard now uses one guarded `lstat()` and tolerates an absent component while retaining containment/link checks.
- A disposable session-worker test hit a transient Windows permission denial when reading a newly published call file. Its fixture now retries only that permission error for up to one second. Persistent errors still fail. This change is to the test worker; it does not claim production inference errors cannot occur.

The affected source-language, feature-session, review and checkpoint modules then passed 104 tests in 44.070 seconds. The first full-suite log/JSON remain at `validation/2026-10-09-stage-checkpoints-backend.log` and `.json`. The subsequent final suite is recorded separately, so the unsuccessful attempt is not overwritten.

A second complete run cleared those four failures but encountered one transient registry atomic-replace denial: 625 tests in 102.083 seconds, zero assertion failures and one error. Its records remain at `validation/2026-10-09-stage-checkpoints-backend-final.log` and `.json`; despite that historical filename, this attempt is not the final passing validation.

The shared `core/json_store.py` publisher now retries Windows errors 5/32 up to four attempts with delays of 0.05, 0.10 and 0.20 seconds. Other errors propagate immediately, and a persistent denial still propagates after the bound. Writes remain temporary-file-plus-atomic-replace transactions; no delete-and-rewrite fallback was introduced. The prior file remains intact and temporary staging is removed on failure. The run-record publisher retains its existing bounded outer retry. This is a general saved-state reliability repair, not an instruction to ignore permission failures.

The persistence, deletion-safety and foundation modules then passed 94 tests in 14.903 seconds, including the two new Windows-specific publication tests. The final successful full-suite and latest real export receipts are recorded separately below.

The full-video recovery receipt below predates these final compatibility, path-guard and shared-persistence repairs. Its evidence audit pins the implementation hashes actually used for that run. The checkpoint implementation and its recognition behavior did not change during those repairs; the final real subtitle check and final backend suite validate the repaired shared helper. Core-code changes conservatively invalidate checkpoints from the earlier run, as designed.

### Real-model recovery receipt

[The two-pass receipt](<C:/Projects/Reflow Studio/docs/validation/2026-10-09-stage-checkpoints-500390d0.json>) reports a passing normal-entry offline recovery test on the existing 122.5-second full known excerpt. No fixture translation, imported checkpoint or pre-generated speech was substituted.

| Observation | First pass | Second pass |
| --- | --- | --- |
| Elapsed wall time | 346.687 s | 181.453 s |
| Real recognition calls | 1 | 0 |
| Real translation calls | 14 | 0 |
| Speech-generation calls | 0 | 0 |
| Recognition/translation checkpoints | Miss, then stored | Both verified hits |
| Final result | Timing-preflight failure | Same timing-preflight failure |

All 14 speech-input cues, their identities, source fields and translated text matched exactly between passes. Both runs rejected the first cue at 7.381 seconds predicted versus 6.400 seconds available. Neither published a dub or concealed the failure. The second run retained the first run's producer identity in its reuse records.

The first pass spent 55.782 seconds inside recognition and 88.938 seconds across translation calls. The second avoided those calls. Its remaining 181-second wall time shows that strict model/runtime content verification is still expensive on this installation. The observed 165-second reduction relative to the first verification-enabled pass is one local recovery result, not a general benchmark; it does not establish a speed advantage over the older pipeline without fingerprint verification. Improving verification cost without weakening invalidation belongs in the resource/performance work before release.

The two checkpoint JSON files total 50,171 bytes. Both owned job workspaces were removed. The sample excerpt, saved model registry and settings remained unchanged. [The independent evidence audit](<C:/Projects/Reflow Studio/docs/validation/2026-10-09-stage-checkpoints-evidence-audit.json>) verifies checkpoint payload digests, all retained cue-artifact hashes, originating run identity and the accepted full-video baseline's unchanged SHA-256. The live execution log is `validation/2026-10-09-stage-checkpoints-live-optimized.log`.

### Final real subtitle path

After the compatibility/path-guard repairs, [the first real subtitle receipt](<C:/Projects/Reflow Studio/docs/validation/2026-10-09-subtitle-checkpoint-5d180b5c.json>) passed two normal-entry exports with the selected IndicTrans2 engine and explicit English source selection. The source was one ordinary four-second SRT cue; this test supplies source text because subtitles already contain it, rather than substituting a translated result.

The first pass made one real translation call and completed in 60.313 seconds. The second made zero translation calls, logged a verified hit and completed in 12.922 seconds. Both exported byte-identical Hindi subtitle content, with SHA-256 `b02cee32b68eeb8089f609416e0050679cbf41e96d42ce059642dca2b4a3fc9c`. Both owned workspaces were removed, and source/registry/settings hashes remained unchanged. This tests translation/export/reuse, not speech delivery or background preservation. The receipt pins the repaired implementation hashes.

After the shared persistence repair, [the latest real subtitle receipt](<C:/Projects/Reflow Studio/docs/validation/2026-10-09-subtitle-checkpoint-16e55b8a.json>) repeated the same normal-entry test successfully: 39.782 seconds with one translation call, then 9.875 seconds with zero calls and a verified hit. The exported bytes matched the preceding receipt exactly. Source/settings/registry hashes remained unchanged and both job workspaces were removed. The corresponding log is `validation/2026-10-09-subtitle-checkpoint-live-complete.log`.

### Final complete validation

The complete final backend suite passed **627 tests across 35 modules in 79.355 seconds**, with zero failures/errors and unchanged saved registry/settings hashes. This increment adds 20 tests relative to the previous 607-test foundation suite. [The final backend receipt](<C:/Projects/Reflow Studio/docs/validation/2026-10-09-stage-checkpoints-backend-complete.json>) binds the tested production/frontend file hashes; its log is `validation/2026-10-09-stage-checkpoints-backend-complete.log`.

[The final evidence binding](<C:/Projects/Reflow Studio/docs/validation/2026-10-09-stage-checkpoints-final-evidence.json>) confirms the current source matches that tested version, the latest real subtitle implementation agrees with it, and the accepted full-video baseline is unchanged. Earlier failing test attempts and the earlier full-video recovery proof retain their own separate implementation/evidence records.

The TypeScript/production frontend build passed, and the corrected application-source lint command passed with existing warnings. The existing bundle-size and hook/component-export warnings remain documented limitations. Unit/fixture checks do not establish listening quality for every provider, arbitrary videos or other operating systems; those release gates remain open.

## Remaining architecture and release work

The automatic full-video Hindi workflow still needs duration-aware dialogue adaptation before speech. Recovery avoids repeating completed inference; full artifact verification adds disk work. It does not shorten wording or certify pronunciation, emotion, background preservation or synchronization. The existing accepted editorial video remains the quality baseline.

Next work is a bounded, observable adaptation/quality policy that operates on canonical cues, preserves meaning, records revisions and stops when it cannot satisfy the speech window. After that come broader independent-source validation, capabilities/readiness, measured resource planning and scheduling, speaker assignment, optional manager integration and platform/release gates from the approved audit. A trained SLM remains deferred until there is suitable evaluation data and evidence of benefit.

Release readiness remains pending. No new packages, models, frameworks or external services were added in this increment.
