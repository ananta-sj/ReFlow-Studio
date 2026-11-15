# Native restored batch and recovery acceptance — 10 October 2026

## Outcome

The rebuilt Windows interface successfully handled a restored four-job queue. Launching it started no work. Resume Render restarted the original interrupted job and left the other jobs paused. Resume Batch started the second job; Pause After Current let it finish and held the remaining jobs. A second Resume Batch started the third job, whose deliberate error remained visible while the fourth job ran and completed. The final queue was Completed, Completed, Failed, Completed, and the interface returned to Ready.

This is native control acceptance using synthetic work inside the real bridge worker lifecycle. It establishes control wiring, persisted queue behavior, original job identity, saved parameters, completion/error events and recovery-marker cleanup. It does not establish speech quality, model inference, actual model parallelism, checkpoint reuse or release readiness.

## Authorized scope and isolation

The user confirmed that the test window could remain idle after the automation detected manual input. No new tools, packages, models, frameworks or services were installed. No API, Ollama or inference calls were made. Existing Python, FFmpeg, pywebview and the rebuilt frontend were used.

All input/output/state for this walkthrough belonged to `C:/Projects/Reflow Studio/temp/native-active-18k60c0l`, identified by its `QA_FIXTURE` marker containing `Synthetic worker only`. The helper redirects application state, temporary workspaces, outputs and model paths to that fixture. It creates a one-second blue MPEG-4 video at 320 × 180, 25 fps, without audio, then copies it into four named inputs. Successful output is a byte-for-byte copy, not a dubbed video.

The root application's five saved state files and previously accepted Hindi video were checked against the earlier baseline and remain unchanged. No finished history, input, output or recovery record was explicitly discarded through a destructive control. The synthetic failure workspace and successful fixture outputs remain available for inspection.

## Changes made in this iteration

Only developer verification and documentation changed. Production bridge, queue, recovery and frontend sources remain identical to the sources covered by the preceding passed validation receipts.

`dev/run_active_walkthrough.py` now accepts `--restored`, an optional `--fixture` path and `--phase initial|resume|default`. A fresh restored fixture seeds four accepted queue items and a current-render marker using the existing queue and recovery APIs before constructing the real bridge. On reload, the bridge restores the queue paused. The prior default walkthrough still creates its two draft inputs.

Fixture reuse checks that the resolved path stays under the workspace's `temp` directory and that the ownership marker matches. Separate initial/resume receipts retain the first launch and subsequent relaunch observations. Control-method overrides call their real implementation, then record the result; they do not substitute acceptance logic.

The helper substitutes only the inner render payload: it reports an STT stage and 25% progress, waits for an owned `release-N.flag`, then copies the synthetic input or deliberately raises an error for `THREE_FAIL_FIXTURE.mp4`. The real outer worker still owns job context, accepted parameters, queue transitions, cancellation plumbing, marker updates and bridge event publication. Closing the test window has a cleanup fallback for a still-gated synthetic worker; both tested launches were closed while idle.

`dev/verify_native_batch_evidence.py` checks the retained native text observations, bridge receipts, final persisted queue, synthetic output hashes, baseline saved state/video and previously tested source hashes. It copies phase bridge receipts into the validation directory and writes an integrity result. It does not operate the interface or start a worker/model.

## Procedure and observations

| Step | Native action or observation | Confirmed result |
| --- | --- | --- |
| Initial launch | Recovery offer appears | Four restored jobs; no payload started |
| Dialog no longer displayed | Inspect Assets | Four Waiting jobs, Batch paused; recovery record retained |
| Close idle window and relaunch same fixture | Recovery offer appears again | Same token and interrupted queue item |
| Resume Render | Inspect Assets during first gated payload | Original first item active; remaining jobs waiting; batch paused |
| Release first payload | Inspect settled queue | First Completed, three Waiting, batch paused |
| Resume Batch | Inspect second payload | Second active, no duplicate first job |
| Pause After Current | Inspect before and after release | Second finishes; third/fourth remain Waiting, batch paused |
| Resume Batch again | Release third payload | Deliberate error reported on third job |
| Automatic advancement | Inspect fourth gated payload | Third Failed; fourth Rendering at 25% |
| Release fourth payload | Inspect settled queue | Three Completed, one Failed; Ready; no Waiting jobs |
| Close idle fixture | Check receipt and process | No worker alive; process exits with code 0 |

The deliberate error is `QA middle job failure; no model execution`. It was visible in Assets and recorded as one `render_error`. There were four payload starts, three `render_finished` events, successful payloads 1/2/4 and one failed payload 3. No payload ran twice.

The accepted jobs specified English source, Hindi target, `CLONED_USER`, CPU, two parallel workers, background preservation off and subtitles included. The UI's future-job configuration showed one worker. Every actual synthetic worker invocation retained the accepted two-worker parameters. This verifies freezing/propagation of accepted settings; no inference workers were exercised, so it is not a measurement of parallel throughput.

All four original IDs, input paths, template IDs and parameter dictionaries survived the relaunch and terminal transitions. Recovery used the original first item rather than appending another queue item. After completion, the persisted queue matched the final bridge receipt, the recovery marker was absent, and the bridge was idle.

## Evidence and verification

The evidence verifier passed **26 checks**. Its result is [native batch integrity](validation/2026-10-10-native-batch-integrity.json).

| Artifact | Content |
| --- | --- |
| [Initial UI observations](validation/2026-10-10-native-batch-initial-ui.json) | Recovery offer, dismissal observed and four paused waiting jobs |
| [Resume UI observations](validation/2026-10-10-native-batch-resume-ui.json) | Relaunch offer, current-only recovery, pause, failure advancement and final Ready |
| [Initial bridge receipt](validation/2026-10-10-native-batch-initial-bridge.json) | Initial idle session, preserved recovery record, no payload starts |
| [Resume bridge receipt](validation/2026-10-10-native-batch-resume-bridge.json) | Accepted controls, payload/events sequence, final queue, saved future-job configuration |
| [Integrity receipt](validation/2026-10-10-native-batch-integrity.json) | Assertions, evidence/helper hashes, user state/video hashes and validation limits |

Screenshots were inspected through the native automation tool during the walkthrough; this iteration archives accessibility text, not standalone screenshot files. UI refreshes were taken after actions because a capture's accessibility tree can lag behind its screenshot/document text. Assertions use the document-text section of the retained captures.

Recheck retained evidence with:

```powershell
& 'C:/Projects/Reflow Studio/build/windows-portable/python.exe' -B 'C:/Projects/Reflow Studio/dev/verify_native_batch_evidence.py'
```

This verifier is specific to the retained fixture and baseline. If fixture files or previously tested sources change later, a failed recheck needs investigation; do not reinterpret it as a new native run.

The previous iteration passed 763 backend tests across 44 modules and 25 frontend contracts, plus build/lint. Those are historical results, not tests rerun here. This iteration verified that their recorded source hashes still match. No production changes required rebuilding or repeating the complete suite.

## Automation interruptions and exact limits

The initial screenshot was obscured by another application. No coordinate action was taken from that obscured capture. Manual-input guards paused automation, and the user confirmed the window was idle before testing continued.

An Escape attempt returned a manual-input error; the next fresh capture showed the dialog closed. The record remained, but this run cannot reliably attribute that dismissal to the Escape action. The earlier native recovery iteration separately covered deliberate dismissal. This report therefore claims preserved recovery after observed closure, rather than a newly verified Escape interaction.

One index-based click was rejected because coordinate geometry was unavailable. A fresh screenshot and state-derived click successfully activated Resume Render. Rejected attempts did not replace the successful control receipts.

The initial interrupted marker was deliberately seeded, not produced by killing this native window. The preceding durable-queue iteration independently exercised abrupt process exit/restart with synthetic work. Combining the two provides useful coverage but does not turn this native run into a genuine crash test.

Native Discard, Remove, Clear Finished History and Factory Clean were not activated. This iteration does not validate those destructive controls. It also does not validate engine cancellation, downloads, resource estimates or end-to-end language/audio behavior.

## Findings and remaining work

No production fault was found in the tested recovery/pause/failure sequence. A separate clarity issue was observed in Dashboard: its source selector can show the next pending input while the progress footer identifies the active input. The worker and Assets row used the correct original input, but Dashboard should explain which selection applies to future work. This remains an interface follow-up, not a queue identity failure.

The sidebar displayed around 81% system RAM usage. That is machine-wide usage, not a measured attribution to Reflow or evidence of an inference-memory problem. Startup and resource use were not benchmarked here; model-specific estimate calibration remains open.

Release work still includes actual provider/subprocess cancellation and checkpoint reuse, a fresh full-video workflow with real STT/translation/TTS/post-processing, synchronization/background preservation and speech-quality acceptance, model-download failure/retry behavior, measured resource and parallel-execution estimates, multiple application instances, clean-machine Windows packaging and Linux/macOS validation. Earlier accepted audio/video samples remain preserved; this synthetic fixture adds no new listening acceptance.

The next development work can address the Dashboard selection explanation and remaining concurrency/control cases without live inference. Real provider or model evaluation remains subject to the user's current instruction to continue development without live model calls and to discuss new tools/models first.
