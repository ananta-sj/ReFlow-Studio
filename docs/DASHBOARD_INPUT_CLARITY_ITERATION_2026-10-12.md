# Dashboard input clarity — 12 October 2026

## Problem and outcome

During the preceding native batch walkthrough, Dashboard's source selector showed the next pending video while its progress section showed the active render. Both values were correct, but neither section clearly explained their different purposes. This could look like the render had switched videos.

Dashboard now displays a separate **Currently rendering** block above the source controls while the bridge reports an active worker. It names the actual active input from render state. During pending cancellation the block says **Stopping render**. The selector beneath it is labelled **Next pending video**, or **Selected input for a future job** for non-video templates. When idle, the selector says **Selected input**.

The block explains that selections/settings apply to future jobs and that accepted batch jobs retain saved settings. The estimate card names the selected input and says it uses selected settings. Expert parameters now carry the same saved-versus-new-job distinction. The progress section labels its filename **Active input** while busy and **Last render input** after the worker becomes idle.

## Changes

Only `frontend/src/pages/Dashboard.tsx` changed in production source. Queue selection, accepted parameters, estimates, bridge calls, persistence and worker behavior were not modified.

The active filename uses `render.inputPath`, including Windows and POSIX filename separators. If an active worker has not yet supplied its input path, the block says **Waiting for active input details**. It does not substitute a queued filename and misidentify it as active. The full path remains available as the filename's title, and long filenames wrap.

The source and configuration controls remain available according to their existing rules. Browsing while active still adds drafts through the existing queue action. No active-input override is sent. An estimate continues to describe the selected pending input and selected settings; it is not represented as a measurement of the currently running job or a previously accepted item's frozen settings.

`dev/verify_dashboard_input.cjs` transpiles the actual Dashboard with the installed TypeScript compiler and renders its element tree with controlled hook/bridge state. It adds no test package or browser dependency. Assertions cover different active/pending filenames and a real browse handler invocation; they are not native screenshot acceptance.

## Validation

Four component contract checks passed:

1. Running state shows the original active filename separately from the next pending input and its estimate, and explains saved batch settings.
2. Stopping state with an empty pending queue keeps the active filename visible in Basic mode, without claiming a pending estimate.
3. Finished state identifies the previous source as historical and does not show it as currently rendering.
4. Browsing during active work calls the draft-addition action without replacing the active source.

The first verifier attempt failed because its text-flattening helper inserts extra whitespace around JSX expressions. The expected regular expressions were corrected to allow that whitespace; no production fix was needed for that harness issue. The retained final receipt/log show all four checks passed.

The production frontend build and lint exited successfully. Build output still warns about large bundles and plugin timing. Lint reports existing hook/fast-refresh warnings elsewhere; no dependency or framework was added to address them in this iteration.

Five saved root state files and the accepted Hindi video match the earlier integrity baseline. Among sources recorded by the previous durable-queue validation, only the intended Dashboard source differs. Its current hash matches this iteration's contract receipt.

| Evidence | Content |
| --- | --- |
| [Component contracts](validation/2026-10-12-dashboard-input-contracts.json) | Four passed checks and tested Dashboard source hash |
| [Contract log](validation/2026-10-12-dashboard-input-contracts.log) | Final verifier output |
| [Build log](validation/2026-10-12-dashboard-input-build.log) | Successful TypeScript and production asset build; warnings retained |
| [Lint log](validation/2026-10-12-dashboard-input-lint.log) | Successful lint exit with existing warnings |
| [Integrity receipt](validation/2026-10-12-dashboard-input-integrity.json) | Saved state/video checks, intended source difference and helper/source hashes |

Rerun the component contracts from the repository root with `node dev/verify_dashboard_input.cjs`. Build/lint use the existing `npm.cmd run build` and `npm.cmd run lint` scripts in `frontend`.

## Scope and remaining work

No backend tests or native walkthrough were rerun: backend behavior did not change, and the new component checks cover the display/state distinction. The preceding native batch report remains historical evidence for recovery/pause/error advancement. Its source-integrity verifier will now correctly flag the Dashboard change against its old hashes; do not rewrite those historical receipts to claim this version was natively tested.

No speech engines, models, external APIs, Ollama services or downloads were invoked. This iteration adds no new speech-quality or full-video acceptance. Native layout inspection of the new block at different viewport sizes remains open.

Release gates remain actual provider/subprocess cancellation and checkpoint reuse, fresh full-video STT/translation/TTS/post-processing acceptance, timing/background preservation, model-download failure/retry, measured resource and parallel-execution behavior, multiple application instances and clean-machine Windows/Linux/macOS packaging. The user's instruction to continue development without live model calls remains in force.
