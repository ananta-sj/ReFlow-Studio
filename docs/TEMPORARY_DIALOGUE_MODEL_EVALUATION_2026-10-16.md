# Temporary dialogue evaluation — 2026-10-16

Status: **bounded evaluation completed; temporary runtime/model removed and preservation verified**. Technical integration checks passed. The dense cue is **not resolved**, and this model is **not approved as an automatic quality judge**. The owner explicitly approved the pinned evaluation and verified cleanup described in `TEMPORARY_DIALOGUE_MODEL_PROPOSAL_2026-10-16.md`.

## Application changes

`core/providers/dialogue_chat.py` now builds explicit English/Hindi target prompts and rejects other language pairs before making a request. Existing callers that omit language labels retain the English-to-Hindi behavior.

`core/dialogue_supervision.py` retains the established native Hindi estimator path and introduces a separate version-two measured-take report. The latter does not call an unavailable duration estimator: original predicted duration, candidate predicted duration and candidate fit are null. The prior actual take remains overflowing. A meaning-preserved model opinion never sets acceptance or verified audio fit. Numeric/script warnings and bounded request/candidate limits still apply. Saved evidence validates the original text, available time, take identity, configuration and cue/revision provenance. Regenerating or editing invalidates measured evidence.

`core/cue_review.py` connects the measured path to the existing explicit `supervise` review action for English/source-language cloning. It requires an overflowing saved candidate and checks the actual source/reference/take before requests and publication. Existing Hindi reference requirements remain. No normal render automatically invokes assistance. No saved model connections or default settings are changed.

The frontend understands null timing results and tells the user to generate a take to measure them. Confirmation text describes eligible candidates and unverified timing. No new framework or frontend dependency was added.

## Verification so far

- Focused suite: 85 tests passed in 29.699 seconds. Includes established Hindi supervision, endpoint/consent checks, review persistence and new measured English integration. These tests use fixtures, not live model outputs.
- Frontend type-check and production build passed; existing bundle-size/plugin-time warnings remain advisory. Built assets were refreshed because the displayed timing state changed.
- Full backend suite: final run passed 941 tests, with saved state and captured sources unchanged. Receipt: `validation/2026-10-16-assisted-review-backend-complete.json`; log: `validation/2026-10-16-measured-dialogue-backend-final.log`.
- Eight final measured-review tests passed, including three added checks for false audio duration, take modification during a request, and the real bridge dispatch with a fixture worker. Counts overlap with the full/focused suites; they must not be added as independent coverage totals.
- Live local model evaluation: all eight cases returned structured results, with 13 dialogue requests and one separate warm-up. No request failure or paid call. One actual English XTTS candidate was synthesized; it did not fit the original six-second window.
- Mandatory cleanup/preservation verification passed. Consolidated receipt: `validation/2026-10-16-temporary-dialogue-acceptance.json`; reproducible consolidation: `dev/finalize_temporary_dialogue_evaluation.py`.

Initial test attempts are retained: one lacked the embedded Python import path; another was interrupted after widespread fixture setup errors without a completed traceback summary, after which temporary/FFmpeg paths were set explicitly; a corrected restricted run hit blocked loopback access; an unrestricted run had one Unicode console-encoding error. The final focused run uses workspace temporary files, bundled FFmpeg, UTF-8 and loopback access. These failures are test-harness evidence, not passes.

## Live evaluation design and limits

`dev/evaluate_temporary_dialogue_model.py` pins Ollama v0.40.5 and the approved Qwen manifest/layers. It verifies hashes, uses a marked project-owned temporary directory, runs loopback-only with cloud disabled, and owns all runtime/model/cache data. The receipt is `validation/2026-10-16-temporary-dialogue-evaluation.json`; the bounded execution log has the same stem.

Final review added a comparison of claimed take duration with decoded audio duration, and allowed the user to explicitly select advisory-preserved, unmeasured wording for a new take. This selection does not accept audio. The final frontend build and full backend suite passed after those production changes. `dev/cleanup_temporary_ollama.py` now also refuses recovery teardown while the new evaluator is still running.

Eight text cases cover the dense English line, two historical complete Hindi cues, English and Hindi facts/negation, quoted hostile instructions, an impossible budget and incomplete context. Synthetic measured durations for negative fixtures are explicitly labeled and cannot establish a real TTS result. The dense case uses the seeded XTTS duration diagnostic plus separately identified complete historical source context. Its original measured waveform used a truncated sentence; this distinction is retained in the receipt.

The live text harness supplies placeholder take-file/hash fields to the supervision function; those are harness metadata, not a saved audio identity. Its dense duration is checked against the separate actual timing receipt and hash-bound waveform when consolidating results. Actual file-hash binding and the bridge action are covered separately by integration fixtures with real WAV files. Live text queries are not a live desktop video-workflow validation. Fifteen bundled runtime notice files were inventoried by relative path, size and hash in `validation/2026-10-16-temporary-ollama-notices.json`.

At most sixteen dialogue requests plus one warm-up, three candidates per case, and six speech syntheses were authorized. The current evaluator selects at most three advisory-preserved English candidates for actual seeded XTTS measurement. Failure/uncertainty remains review-required, and the runtime/model must be removed even when no candidate succeeds. No retry with another model, paid endpoint, new Python packages or driver installation is included.

## Remaining acceptance limits

A same-model critic is not independent semantic validation. Fast enough speech may still sound unnatural. The existing six-second source window and speed limit remain in force. Human listening/meaning acceptance and release readiness cannot be inferred from a fitting duration, a successful model call or a fixture test. This experiment does not complete the outstanding wider release gates.

## Actual live results

Pinned identities matched the proposal: Ollama v0.40.5, model manifest `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`, and all model layer hashes. Runtime archive size/hash also matched. The separate cold warm-up took **74.913 seconds**; a normal 60-second request budget would not have covered that load. Normal requests retained their existing time limit. The longest case below includes two sequential requests, not a single request exceeding its limit.

Ollama reported 3,180,247,121 bytes allocated for the loaded model, entirely in GPU memory, at a 4,096-token context. This is model allocation, not a measured total or peak GPU footprint. The model was explicitly unloaded before CPU speech synthesis; `/api/ps` then returned an empty model list. The owned-process TCP snapshot contained only loopback listeners/connections. This point-in-time observation does not establish every packet emitted during the process lifetime.

| Case | Seconds | Recorded result and interpretation |
| --- | ---: | --- |
| Dense English | 61.594 | Writer and critic returned three alternatives. The critic preserved only the effectively original full sentence; its shorter paraphrases were rejected with unreliable explanations. No timing prediction was invented. |
| Hindi opening | 4.172 | All three variants exceeded the existing native duration prediction; no critic request was spent on them. |
| Hindi establishing shot | 5.844 | Two variants fit prediction; one was rejected for changing “of a location” to “for a location”, while the other received an advisory preserved opinion. Neither new Hindi audio nor human acceptance was obtained. |
| English facts/negation | 3.875 | The critic distinguished “did not approve” from the stronger “rejected” and retained the contraction-based paraphrase as advisory only. Timing remains unmeasured. |
| Hindi facts/negation | 2.375 | All variants exceeded the deliberately tight one-second prediction budget. |
| Quoted hostile text | 4.640 | Returned quoted dialogue rather than executing an instruction. The critic rejected all variants, but some reasons misquoted or misidentified their differences. No tools or shell capability were exposed. |
| Impossible 0.1-second window | 4.016 | Returned meaning-preserved opinions on some wording despite the impossible target. All fit values remained null, all approvals false. A meaning opinion therefore cannot be used as a timing verdict. |
| Incomplete source context | 0.328 | Returned no alternatives. |

No result automatically changed a transcript or accepted a take. The Hindi establishing-shot suggestion still needs a fluent speaker's assessment: a preserved model opinion does not establish natural grammar or retention of the technical “establishing shot” role. The critic also rejected English paraphrases partly for changes of wording/structure rather than demonstrating a changed claim, and one explanation confused the complete source with the truncated current text. These observations are direct reasons to retain advisory status.

## Actual speech measurement

Only the advisory-preserved dense candidate was synthesized, using the approved existing isolated CPU XTTS runtime, existing cleaned reference and seed 7. Text:

> Before long a standard news report visual language established itself, one that's immediately recognizable to anyone.

Raw duration: **8.587 seconds**. At the established maximum **1.3×** tempo, the complete take measured **6.606 seconds**, exceeding the **6.000-second** window by **0.606 seconds**. It was retained as `validation/2026-10-16-dialogue-candidate-1.wav`, SHA-256 `a280749e21e9eb8622e3c2af6e87b7af2c53baa46655d562e78d3ab130b94027`. No words were cut and the source window was not extended. This is a standalone timing candidate, not a finished dubbed video. It is not accepted for quality or rendering.

The original diagnostic measured a truncated sentence; this test uses the complete sentence. Their different durations do not establish a model quality gain or a controlled speed improvement. No additional candidates were generated to force a favorable outcome, and no new Hindi speech was synthesized in this evaluation.

## Verified removal and preservation

The evaluation took **1,812.921 seconds** including downloads, loading, text queries, speech generation and cleanup. Immediately before removing the owned directory, its remaining files totaled **5,971,131,687 bytes** (about 5.97 GB). This is an observed pre-removal size, not continuous peak storage telemetry; job scratch had already been cleaned.

The consolidated receipt confirms:

- The owned directory `temp/ollama-eval-5ojpcpd7` is absent, including the runtime ZIP, extracted executables/libraries, weights, manifests, partial downloads, temporary home/key files and caches.
- Owned server/runner processes exited and the owned endpoint was released.
- Normal external Ollama locations remained as before; user/system environment and relevant startup-entry snapshots matched.
- The five protected app-state files and all six established runtime identities matched their baselines. All eight original XTTS assets, including the checkpoint, matched the prior SHA-256 baseline. Original speech/timing evidence and historical context hashes also matched.
- No Python package, Windows service, installer, startup item, global PATH change, permanent model connection or paid call was added.

Only implementation/test changes, bounded reports, notice metadata, diagnostic logs and the one review WAV remain. The model/runtime is removed even though the quality objective did not pass. No listening review was required before cleanup.

## What this resolves, and what remains

Resolved in code: explicit measured-overflow assistance for English review cues, honest unmeasured timing in the UI, saved-take duration/hash checks, stale evidence invalidation, and explicit wording selection followed by regeneration. The existing Hindi estimator path and guarded consent/cancellation behavior remain covered by regression tests.

Not resolved: reliable shorter wording for the six-second diagnostic and trustworthy automatic semantic/naturalness grading. The small-model reviewer showed both useful rejection and contradictory reasoning. The next development work should distinguish source claims from acceptable paraphrase, require review reasons to cite actual supplied text, and keep measured speech fit separate from meaning. Any revised prompts/model must be evaluated before claiming improved quality; this completed run does not validate later changes.

No further runtime/model download, paid evaluation, automatic rewrite or default switch is implied. The wider Windows release gates—including licensing decisions, remaining engine assets/workflows, broader real-video tests and clean-machine validation—remain separate outstanding work. **This iteration does not make the app release-ready.**
