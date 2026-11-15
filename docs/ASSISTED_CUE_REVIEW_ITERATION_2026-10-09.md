# Assisted saved-cue review — 9 October 2026

## Outcome and authorization

Hybrid assistance is now available as an explicit saved-cue review action. It uses the existing connection adapter and asks for shorter wording, followed by a bounded meaning review. It does not run during ordinary dubbing, accept wording, generate speech or render media. The user elected to continue other development without live model calls. No tool, framework, package, model or paid request was added. Connection setup and actual Hindi model-quality evaluation remain pending.

## User flow

The review panel exposes **Suggest shorter wording with assistance** when both selected connections are configured and there are no unsaved edits. Before a request, a disclosure shows the writer/reviewer models and endpoints, exact saved source/current text, available speech window, candidate sharing and the maximum two-request budget. Remote roles include a possible-charge notice. Configuration checks do not contact services.

The native speech estimator checks the original first. Already-fitting wording produces a zero-request report. Overflow permits one writer request with at most three distinct alternatives. Only candidates with a predicted fit and no objective number/script warnings reach one batch meaning-review request. No retries or alternate providers are selected. A preserved-meaning opinion enables **Use this wording**, which fills the editor; the user must still save and audition. Predictions and model opinions do not establish audible timing, naturalness or semantic correctness.

## Configuration, identity and races

The action freezes settings and registry selections and binds the report to the saved review configuration, cue ID, input revision and durable run ID. It verifies the retained source/reference audio identities and confirmed voice profile. The current supported action is English-to-Hindi with the confirmed user voice; active profanity filtering or custom translation instructions require a separate evaluation and are rejected for this action.

Before every request and before publication, guards recheck cancellation, saved review revision, selected configuration and connection consent/readiness. Concurrent manual edits survive and prevent stale publication. Revocation during a writer request prevents the subsequent critic request and publication. A request already in flight cannot be recalled. Changing registry/settings configuration requires preparing a fresh review for assistance; this guard does not retroactively alter accepted media.

Run records save requested connection identities, request observations, report artifacts and publication status. Successful publication updates the review using its expected revision. Failures retain the previous review/report/takes. Existing accepted and candidate audio are preserved. The artifact output is the saved review document, not a new audio/video result. Reports remain explicitly unapproved and human-review-required.

## Stored-report integrity and invalidation

Loading a report validates its schema, exact input text/window binding, role/run/configuration identity, candidate identities and uniqueness, request budgets, timing predictions, warning calculation, meaning states and outcome consistency. Forged approval flags, inconsistent durations and altered source bindings fail validation. Saved whitespace is preserved exactly so publication does not produce a binding mismatch.

Source/translation/timing edits and cue combinations invalidate affected suggestions. Changing a neighboring window invalidates its affected timing report. Retranslation clears old reports, and successful beam-alternative generation clears an older assisted report. Unaffected neighbors and existing audio remain retained; editing the UI hides stale suggestions until the saved state is refreshed.

## Changes

- `core/cue_review.py`: frozen explicit action, media/configuration/revision guards, durable publication, safe failure and suggestion invalidation.
- `core/dialogue_supervision.py`: request guards, bound reports, stored-report validation and exact input-whitespace preservation.
- `bridge/api.py`: assisted action allowed through existing review job ownership/cancellation machinery.
- `frontend/src/lib/api.ts`, `CueReviewPanel.tsx`, `Settings.tsx`: typed reports/readiness, request disclosure, manual candidate selection and accurate scope copy.
- Tests: persistence, malformed reports, concurrent edits, consent changes, failure retention, zero-request fits, no synthesis, and actual disposable localhost HTTP through the review operation. The validation runner records source hashes and saved-state integrity.

## Validation and evidence

The first focused run exposed eight fixture errors: the helper saved an existing review without supplying the expected revision. The fixture was corrected to increment the revision and pass the prior revision. The repaired focused run passed 75 tests in 31.968 seconds. Subsequent whitespace, zero-request and actual HTTP review tests are covered by the final suite.

**684 backend tests across 38 modules passed in 172.219 seconds**, with zero failures/errors, unchanged tested production sources and unchanged saved settings/registry. Receipt: `validation/2026-10-09-assisted-review-backend-complete.json`; complete log has the same base name. Frontend production build and source lint passed; retained logs are `validation/2026-10-09-assisted-review-frontend-build.log` and `validation/2026-10-09-assisted-review-frontend-lint.log`. Existing build/lint warnings remain. Browser interaction was not exercised in this increment.

The localhost fixture server executes the actual connection adapter and saved-review operation, then shuts down. Its responses are fixed JSON, not real generated Hindi or evidence of meaning-review quality. No new speech/video was produced. The previously accepted editorial video remains the historical baseline, not proof of arbitrary-input success.

## Remaining limits

Live writer/reviewer evaluation is deferred at the user's request. Automatic rewriting/acceptance, acoustic emotion/naturalness checks, independent-video/provider/platform validation and the optional manager remain incomplete. Same-model writer/reviewer agreement is not independent evidence. Existing transport checks bound responses, but cannot immediately interrupt a blocking socket read; hard-deadline cancellation remains a hardening item. Release remains pending.
