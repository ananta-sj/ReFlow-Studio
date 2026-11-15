# Dialogue assessment and bounded wording review — 9 October 2026

## Outcome and scope

This increment connects dialogue timing assessment to the normal fixed pipeline and adds an on-demand wording-alternatives action to saved cue reviews. It uses the existing pinned IndicTrans2 translator and the selected native IndicF5 voice estimator. No model, framework, package or external service was added. It does not generate demonstration audio or revise the accepted full-video baseline.

The implementation is a partial A05/A06 milestone: durable assessment, explicit review requirements and bounded proposals are implemented. Automatic meaning-preserving compression and a reliable naturalness critic remain unimplemented. A model producing alternatives is not evidence that those alternatives preserve meaning or solve timing. The real-model results below show why that distinction matters.

The approved pipeline remains preprocessing → recognition → translation → dialogue preparation → speech synthesis → timing/mix/export. Dialogue preparation now has a recorded assessment rather than an invisible first-conflict failure. The existing recognition/translation recovery and source-cue provenance remain in place. This work does not replace the pipeline with manual sample polishing or a trained manager model.

## Normal automatic runs

`core/dialogue_adaptation.py` assesses all native speech cues, rather than raising immediately at the first overflow. Each record includes stable cue identity, index, original source text, raw translation, current wording, original/current timing, available speech window, predicted speech duration, excess duration and a fit/review status. Predictions must be finite and positive; booleans, nonfinite values and invalid durations are rejected. Cancellation is checked between cues.

Available time follows the existing automatic policy: the greater of the cue duration and the gap to the next cue's start, with the final cue limited to its own ending. This does not create a new permission to overlap another line. The existing native synthesis and output-integrity checks remain responsible for actual generated duration. A predicted fit is not an actual recording, a lip-sync score or a naturalness assessment.

The pipeline invokes assessment before speech for video and audio dubbing. Subtitle export retains its text-only plan. The fixed plans now show a dialogue stage before speech/timing/mix. If any assessed cue overflows, `DialogueReviewRequired` carries the complete report; the normal job stops before speech generation and reports the first conflict plus the total number needing review. Queue failure behavior remains compatible with existing callers. A saved quality report records `needs_review`, and the manifest sets `review_required`; a blocked job is not reported as a completed dub.

The report is published as `dialogue-report-NNN.json` using the existing durable atomic publisher, then registered in `RunManifest.quality_reports` with its file identity. Native prediction operations are recorded under the dialogue observation. No source, translation or speech-input wording is mutated by assessment. Unsupported speech routes receive `not_assessed` with an explicit reason rather than a guessed duration. Existing generation checks continue for those routes.

The supported native assessment requires the provider's native-delivery flag and duration estimator and a cloned-user cast. Wider multi-speaker/provider estimates are not certified by this increment.

## Saved-review interaction

The cue-review panel now includes **Find wording alternatives**. It uses the existing review job mechanism, configuration snapshot, revision checks and selected providers. The reviewed route is English → Hindi using IndicTrans2 and a confirmed native reference voice. Unsupported language/cast configurations, custom translation instructions, moderation and absent or changed reference evidence produce errors before accepting a proposal.

One user request permits one model query and at most three generated candidates. The UI presents distinct alternatives with predicted duration, fit status and any numeric-change warning. It states that predicted timing does not establish meaning or naturalness. Non-fitting suggestions remain visible for diagnosis but cannot be selected through the suggestion button. A fitting suggestion can fill the wording editor; it does not automatically save, generate speech or accept a take. Saving an edit and auditioning the resulting speech use the established review path.

The backend saves a versioned `reflow.dialogue-options.v1` payload linked to the current source wording, target wording and available time. Every candidate is explicitly `approved: false`, and the payload states `meaning_assessed: false` and `human_review_required: true`. Candidates matching the current translation and duplicate candidates are removed. Fits sort before overflows, then warning-free candidates, then shorter estimated duration. Numeric-sequence changes are flagged as a limited warning; unchanged numbers do not establish semantic correctness.

Finding alternatives retains the current text, canonical cue contract, candidate recording and accepted recording. Selecting and saving different wording follows the existing invalidation rules. Editing wording/timing, retranslating or combining lines clears stale alternatives; timing edits also clear another line's alternatives if its speech window changes. Stored payload validation rejects stale source/text/window bindings, invalid prediction/fit flags, automatically approved alternatives and excess candidate budgets. Failed proposal requests do not publish edited cue text or generate audio.

The review does not yet offer a dedicated overview of all automatic timing conflicts, automatic transfer from every failed run into a saved review, or cross-provider alternatives. The backend quality report is the full conflict record for automatic runs.

## Existing IndicTrans2 worker and bounded execution

Baseline translation retains its existing deterministic beam-five recipe. The new alternative mode requests up to three returned sequences with beam count five, no sampling and length penalty zero. The latter encourages alternative beam ranking; it does not implement a duration constraint or a semantic rewriting prompt. The existing pinned tokenizer/model, offline loading and source-token bounds remain in use.

Each generated sequence is checked for completion. Trailing padding is removed where distinct from EOS; unfinished outputs are rejected. The worker returns completed distinct candidates, the number of incomplete rejections, request sequence, worker identity and recipe. There is no automatic fallback to another translator or unbounded retry loop.

Proposal calls have a 180-second total session-call deadline, including startup for a fresh worker. This may reject a slow cold start; it is an explicit execution limit rather than evidence of model quality. The normal translator's existing timeout remains unchanged. Timeout errors now include the bounded tail of the worker log. Job cancellation and owned-worker cleanup continue through `FeatureSession` and `RenderContext`.

Worker logs identify runtime loading, asset checking, model loading, request start and token generation without logging the input dialogue. Watchdog traceback snapshots help distinguish model loading from blocked processing. A watchdog message headed “Timeout” is a diagnostic snapshot, not by itself a failed model request.

## Failures found and repaired during this increment

The first live multi-candidate attempt stalled. A shorter bounded request also timed out. These attempts are retained as failed diagnostic evidence; they are not counted as successful validations. The diagnostic attempt is recorded in `validation/2026-10-09-dialogue-live-diagnostic.log`, with its worker trace retained in `validation/2026-10-09-dialogue-adaptation-bff6e79d/translation-worker.log`.

Inspection found that the generated-token loop reused the outer request-sequence variable. This would corrupt subsequent request handling. The loop now uses a separate generated-sequence variable, and the successful live check below verifies three consecutive requests in one worker.

The decisive live traceback showed `IndicProcessor._postprocess` blocked in `queue.get`. Preprocessing creates a consumable source-placeholder record. Postprocessing consumes and clears that record. Calling postprocessing repeatedly for several beam alternatives after preprocessing a single input therefore exhausted the record and blocked on a later alternative.

The fix leaves the pinned vendor processor unchanged. Each alternative receives a fresh processor, preprocesses the same original source to create its own placeholder record, and restores its own decoded output. A regression fixture deliberately models consumption and verifies three independently restored alternatives, including retained source-number data. This is why mock provider-call tests alone were insufficient: they did not execute the stateful real processor.

The earlier focused-suite failure was a test expectation about operation ordering: a new parent dialogue operation precedes its timing observations. The test now checks operation kind/status rather than assuming observation index zero. Earlier failed and passing receipts remain source-version-specific.

## Real-model evidence

The driver `dev/verify_dialogue_adaptation.py` reads the SHA-verified, preserved real recognition and raw IndicTrans2 translation from the previous full-video recovery run. It does not substitute edited review wording or accepted speech takes. Recognition and full translation are reused evidence, not newly executed stages in this test. The current selected reference estimator is exercised, and the translation worker makes fresh alternative requests.

Successful receipt: [2026-10-09-dialogue-adaptation-ebea24de.json](validation/2026-10-09-dialogue-adaptation-ebea24de.json). The associated folder contains a fresh run manifest, complete dialogue report, unchanged speech-input artifact and retained translation-worker log.

All 14 cues were assessed: **11 need wording or timing review and 3 fit prediction**. The first three conflicts received one real model request each. The worker reused PID 25468 with request sequences 1, 2 and 3; the total check took 86.375 seconds, including startup and cleanup. Each returned two alternatives distinct from its original translation. None fitted:

| Cue | Available seconds | Alternative predictions, seconds | Predicted fitting alternatives |
| --- | ---: | --- | ---: |
| 1 | 6.400 | 7.179, 8.021 | 0 |
| 3 | 5.000 | 5.515, 5.515 | 0 |
| 4 | 14.720 | 21.237, 21.237 | 0 |

The complete source/translation payload was unchanged. The owned successful job workspace was removed. Saved `models.json` and `settings.json` hashes were unchanged. No speech was synthesized, no video was rendered, and no candidate's meaning or naturalness was accepted. The receipt binds the main implementation files to their hashes; the full backend receipt binds the broader tested source set.

The result is useful negative evidence: alternative translation beams alone do not solve this sample's overflow. This increment therefore cannot be described as completed automatic dialogue adaptation. It provides a controlled review path and an observable report instead of silently increasing speed, clipping words or substituting unchecked shortened translations.

## Validation and file inventory

Frontend production build and application-source lint passed. Their retained logs are `validation/2026-10-09-dialogue-frontend-build.log` and `validation/2026-10-09-dialogue-frontend-lint.log`; existing bundle-size and React warnings remain. No frontend changes followed those checks.

Backend final results are recorded in [2026-10-09-dialogue-backend-complete.json](validation/2026-10-09-dialogue-backend-complete.json) and its full log. The runner discovers every `dev/test_*.py` module, uses workspace temporary storage and verifies selected production-source hashes plus saved registry/settings hashes before/after the suite. Final result: **641 tests across 36 modules passed in 193.547 seconds**, with zero failures/errors and unchanged saved state and tested sources. These tests include simulated failure paths; expected fixture failure messages are not live-engine acceptance. Browser interaction, packaging and cross-platform execution were not newly validated here.

Production changes: new `core/dialogue_adaptation.py`; integration in `core/pipeline.py`, `core/pipeline_contracts.py`, `core/run_manifest.py`, `core/cue_review.py`, `bridge/api.py`; selected translator/worker changes in `core/providers/translation/indictrans2_local.py` and `core/indictrans2_worker.py`; timeout diagnostics in `core/feature_session.py`; review API typing and panel controls in `frontend/src/lib/api.ts` and `frontend/src/components/shared/CueReviewPanel.tsx`.

Validation changes: new `dev/test_dialogue_adaptation.py`, `dev/verify_dialogue_adaptation.py` and `dev/verify_dialogue_backend.py`; additional review/provider/processor tests in `dev/test_cue_review.py` and `dev/test_indictrans2_integration.py`; revised manifest-order assertion in `dev/test_pipeline_foundation.py`; dialogue coverage registered in `dev/run_cleanup_checks.py`. Documentation follow-ups link this report without replacing historical audit inventories or their hashes.

## What remains

The next quality increment needs a bounded way to propose shorter dialogue and independently check its meaning before synthesis. Fit must then be verified against actual generated speech. The existing translator can remain responsible for translation while dialogue rewriting and semantic checking have separate contracts. Any additional model, tool or framework requires the user's existing approval process; none is introduced here.

A general naturalness/emotion critic, automatic safe correction policy, cross-language/provider coverage, capability readiness, real resource estimates, scheduling/performance, multi-speaker assignment, optional API/Ollama manager, provisioning and cross-platform release checks remain on the approved roadmap. Training a proprietary reviewer remains deferred until meaningful evaluation data exists. The accepted editorial Hindi video remains a baseline for comparison, not evidence that fresh arbitrary videos now finish automatically. Release readiness remains pending.

## Final evidence integrity

[The independent integrity receipt](validation/2026-10-09-dialogue-evidence-integrity.json) passed eight checks: current live-source hashes; registered report/cue artifact hashes and sizes; report/receipt equality; original raw cue identity; three consecutive requests from one worker; bounded unapproved alternatives; the accepted video SHA; and honest needs-review manifest state. The accepted video still has SHA-256 `0e4dc4a51253b5b4a0172ec2842647f0f2b643480135d6c27e4876b0442bf0a2`. The full suite followed the successful real-model check, and no production changes followed either final validation. Historical failed workspaces/evidence have not been broadly removed.
