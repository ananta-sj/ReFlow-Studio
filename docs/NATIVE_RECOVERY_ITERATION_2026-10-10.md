# Native source selection and safe recovery dismissal — 10 October 2026

## Outcome

Fixed a recovery-record deletion bug: closing the interrupted-render prompt previously meant the same thing as pressing Discard. Escape, the close button and outside dismissal now leave the recovery record available. Only the explicit Discard button invokes token-checked deletion. Resume retains its existing restart path and surfaces rejection without deleting the record.

Native acceptance verified successful video selection, pending batch confirmation, rollback after a refused worker start, Escape preserving recovery, and a refused Resume preserving recovery. This is control-flow acceptance with inference blocked, not a successful model render or crash during real inference.

## Authorized scope and isolation

The user's instruction to continue development without live model calls remains in force. No packages, frameworks, runtimes or models were installed or downloaded, and no paid/provider inference was initiated.

`dev/run_control_walkthrough.py` launches the actual built frontend and `PythonBridge` in a window titled **Reflow control walkthrough**. It creates a fresh directory beneath the workspace's `temp/`, generates a one-second blue 320×180 MPEG-4 fixture with the existing FFmpeg binary, and redirects application storage before settings, registry, hardware-profile and recovery modules capture their paths. Each fixture has its own graph, preferences, settings and empty registry. The real user-state files are not copied into the fixture or changed.

The bridge subclass changes two boundaries: the video picker starts in the fixture's input folder; `_start_worker` records requests and returns a clear rejection before worker construction or pipeline execution. Normal dialog selection, draft addition, batch acceptance/rollback, session publication, render configuration, recovery detection and frontend alerts use the application code. Recovery fixtures mark onboarding/tour complete in their own state to expose the recovery prompt without overlapping onboarding. This host is a development fixture, not a new production runtime or user feature.

Fixtures are retained rather than swept. Their names and bridge records are recorded in the integrity receipt. All three desktop processes exited successfully after the walkthrough.

## Root cause and repair

The shared confirmation helper returned a boolean: confirm → true; explicit Cancel and every dismissal → false. `App.tsx` interpreted false from the recovery prompt as authorization to call `discardInterruptedRender`. The backend's stale-token guard could prevent deleting a newer record, but could not distinguish an accidental dismissal from an explicit discard of the offered record.

`use-confirm.tsx` now provides `confirmChoice`, whose outcomes are `confirm`, `cancel` and `dismiss`. The dialog's close event returns `dismiss`, the explicit cancellation button returns `cancel`, and the affirmative button returns `confirm`. Alert acknowledgements return `dismiss`. The existing `confirmAction` boolean API wraps this result, preserving ordinary callers' behavior: only affirmation allows continuation.

The recovery prompt uses the three-way API. Only `cancel` from its explicitly labelled Discard button attempts deletion; `dismiss` performs no recovery action. The wording explains that verified recognition/translation checkpoints may be reused and other stages run again. Its frontend comment and bridge documentation were updated to match the existing checkpoint implementation. No pipeline checkpoint implementation or production worker-start behavior was changed here.

## Native observations

| Walkthrough | Observation and retained evidence |
| --- | --- |
| File selection | The native Open dialog showed the fixture folder and `SOURCE_FIXTURE.mp4`; selecting it returned its exact path and created one draft. The custom initial folder avoids typing into the previously unreliable dialog focus. Arbitrary-folder navigation and multiple selection remain untested. |
| Batch confirmation | Dashboard displayed one pending video job and the selected English/CPU configuration. Start Batch reached the guarded bridge boundary with the source, `video_dub` template, render flags, worker count and singleton cast. |
| Rejected worker start | The UI displayed “Start unavailable” with the fixture rejection. Assets retained `SOURCE_FIXTURE.mp4` as “Ready to start.” The bridge receipt shows a draft with unfrozen parameters, idle render and `busy: false`. |
| Recovery dismissal | A seeded interrupted record produced the real recovery prompt. Escape closed it without invoking the guard or deleting the record. The record remained on disk after window closure and was included in the bridge receipt. This does not claim a subsequent restart of that same fixture was tested. |
| Rejected Resume | A separate seeded fixture's Resume button reached the guarded start boundary with the original source, Hindi parameters and template. “Resume unavailable” appeared; the original record remained and the session stayed idle. |

Initial automation actions were refused because manual input occurred between captures. Input was paused, the user confirmed the test window was idle, fresh state was captured, and testing resumed. This did not affect the user's saved project state. No native Discard or other UI deletion was exercised; explicit Discard and stale-token failures were checked using frontend/backend fixtures.

## Validation

| Check | Result and scope |
| --- | --- |
| Complete backend suite | 748 tests across 43 modules passed in 95.000 seconds; zero failures/errors |
| Actual frontend module checks | Eight passed, executing transpiled `use-confirm.tsx` and `App.tsx` with fixture bridge/React bindings |
| Frontend checks covered | Distinct cancel/dismiss; boolean compatibility; non-proceeding alerts; dismissal without action; original token on discard; original restart payload; rejected Resume alert; discard rejection/exception alerts |
| Production build | Passed; existing large-chunk warning retained |
| Lint | Passed; existing warnings retained |
| Source integrity | Final backend and frontend receipt hashes match current tested sources |
| State integrity | Settings, registry, graph, UI preferences and hardware profile match the previous iteration's recorded hashes |
| Accepted video | Byte-identical SHA-256 `0e4dc4a51253b5b4a0172ec2842647f0f2b643480135d6c27e4876b0442bf0a2` |

The frontend contract harness uses the existing TypeScript compiler and Node assertions, without new dependencies. Its App checks invoke the actual boot effect and recovery handler with stubbed surrounding UI/bridge effects. They establish handler decisions and payloads; native evidence independently verifies Escape and Resume rejection in the real window. The full backend suite retains token safety, publication, queue rollback and checkpoint coverage. Existing mocked failure messages in its log are expected fixture output, not successful real inference.

## Changed files and evidence

Production changes: `frontend/src/lib/use-confirm.tsx`, `frontend/src/App.tsx`; documentation-only bridge adjustment: `bridge/api.py`. Added development fixtures: `dev/run_control_walkthrough.py`, `dev/verify_recovery_frontend.cjs`. Updated the existing verification runner's label and hashed source inventory. Roadmap/release documents link this report without claiming release readiness.

Evidence is under `docs/validation/2026-10-10-native-recovery-`: `backend-complete.json/.log`, `frontend-contracts.json/.log`, initial contract receipts retained before a comment-only source revision, initial/final build and lint logs, `ui-observations.json`, `batch-bridge.json`, `dismiss-bridge.json`, `resume-bridge.json`, and `evidence-integrity.json`. UI observation text is retained; native screenshots were inspected during the walkthrough. Original fixture files remain under the three workspace-owned directories listed in the integrity receipt.

## Remaining gates

1. Populated estimates and native graph voice/language/optional-stage controls still need interactive acceptance. This iteration does not claim an estimate display was verified.
2. Active multi-job progression, cancellation during actual inference, genuine crash/relaunch and checkpoint reuse through the full native workflow remain open. Rejected starts and seeded recovery records do not replace those tests.
3. Physical resource calibration, optional-engine readiness gaps, independent complete-video quality, live hybrid-assistant evaluation and clean-machine/platform packaging remain pending under their relevant authorization.

Release readiness remains pending.
