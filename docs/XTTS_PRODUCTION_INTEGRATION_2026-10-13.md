# XTTS production provider integration — 13 October 2026

## Outcome and scope

The approved replacement runtime can now be invoked through Reflow's actual XTTS provider. This moves the successful evaluation recipe into application code rather than leaving it as a standalone speech experiment. The route is an explicit CPU trial. It has not become the application default, and this iteration does not establish release readiness.

No new package, framework, model or paid service was added in this integration pass. The existing 99-package replacement, existing XTTS assets and an existing sample video supplied the test inputs. Prior runtimes remain available. Saved preferences, graph, hardware profile, settings and model registry are protected by a separate integrity receipt. Temporary Ollama remains removed.

The installation history, exact package versions, advisory scan, previous unsuccessful adapter attempts, cancellation and speech-content evidence are in [the replacement runtime report](XTTS_SECURITY_RUNTIME_ITERATION_2026-10-13.md). Those are historical receipts; this document describes subsequent production changes.

## Application changes

| File | Change and reason |
| --- | --- |
| `core/xtts_compat.py` | Moves the validated, exact-version compatibility adapter into application code. Supplies the removed helper using native `torch.isin` and reconstructs dense all-ones attention masks for Coqui's learned audio-position calculation. |
| `core/xtts_worker.py` | Implements a persistent, job-owned CPU speech worker using the existing file-based session protocol. Loads one model per session, disables downloads and socket operations, and keeps caches inside the job folder. |
| `core/xtts_runtime.py` | Checks the trial profile, Python bootstrap hashes, worker/adapter hashes, exact dependency lock and installed distribution metadata. Produces an identity for manifests and worker reuse. |
| `core/providers/tts/xtts_local.py` | Adds explicit isolated selection, defers heavy legacy imports, fingerprints model assets, reuses a worker inside a job and makes the parent validate and publish audio. Keeps the legacy route as default. |
| `core/run_manifest.py` | Records runtime selection, runtime identity and model fingerprint with the provider identity. This makes output evidence traceable to the selected recipe. |
| `core/engine_readiness.py` | Recognises isolated selection in both bundled fallback and explicit local XTTS routes. Rejects missing/changed recipes and GPU selection for this CPU trial. Reports model inference as unverified during setup inspection. |
| `runtime_profiles/xtts-security-candidate/profile.json` | Binds the owned trial profile to production worker, adapter and Python bootstrap hashes. Marks production selection as an explicit trial with defaults unchanged. |

The adapter changes process-local Coqui classes. Installed third-party source is not edited. It accepts only the evaluated package family: Python 3.13.16, PyTorch 2.14.1 CPU, Transformers 5.19.0 and Coqui TTS 0.27.5. Unsupported versions must be evaluated before a new recipe is accepted. Its mask reconstruction assumes dense, unpadded CPU token input. Padded batches and GPU execution are outside this acceptance.

## Selection and lifecycle

Development callers can select `XTTSLocalProvider(runtime='isolated', device='cpu', model_path=...)`. Existing pipeline resolution can use the process environment `REFLOW_XTTS_RUNTIME=isolated`; the dashboard compute device must also be CPU. An absent variable means legacy. Unknown selections and incompatible devices raise errors rather than choosing another engine silently.

This is a development opt-in, not a completed nontechnical runtime selector. No saved selection was changed. A user-facing selector, packaging recipe and default migration remain separate work.

The isolated route requires nonblank text of at most 4,000 characters, a supported explicit speech language and a playable voice reference. It reuses existing local model assets and never downloads missing models. Calls outside a bound render job receive an owned temporary job and clean it up before returning. Within a render job, calls share one loaded model through a session keyed by runtime and model identity.

The model fingerprint hashes relevant JSON and PTH files once per job when their file metadata changes. Worker requests are serialised by the existing session lock. This supports safe session reuse; it does not establish parallel model inference or measured throughput scaling.

The child writes a unique WAV inside the caller's job workspace. The parent checks non-silent playable speech, copies it to the existing staged-output mechanism and publishes only completed audio. Failure removes the pending child output and preserves any completed destination. Job cleanup closes sessions and removes owned files. A crashed session surfaces its error; recovery is performed in a new job rather than silently retrying a failed cue.

## Readiness and identity limits

Runtime validation binds the Python executable, Python DLL, standard-library ZIP, worker, adapter, dependency lock and all distribution metadata. All 99 installed package names and versions must match the reviewed lock; duplicate metadata is rejected. Setup inspection loads no model and does not perform speech inference. Its runtime status remains unverified for output quality even when recipe identity checks pass.

These checks are not a complete package payload integrity or security certificate. They do not hash every native DLL or prove the provenance of arbitrary replacement files. The earlier third-party Python-source RECORD check remains separate evidence with its documented scope. Model fingerprints and manifest fields are provenance evidence, not a generated-speech cache. No persistent speech cache has been added.

## Real provider acceptance

[The actual provider receipt](validation/2026-10-13-xtts-production-provider.json) records five passing checks:

1. The runtime passes explicit-trial readiness validation.
2. Two speech requests share the same worker PID and one model load.
3. Killing the single job-owned worker causes the next call to report failure while preserving the completed destination hash.
4. A new job loads a different worker and produces playable speech.
5. Both owned job workspaces are removed.

The test used a six-second reference extracted from the existing `Sample/2.mp4`, existing XTTS weights and short English phrases. It retained [one successful output](validation/2026-10-13-xtts-production-provider-success.wav). The run took 416.203 seconds while backend tests were also running. This is an observation under contention, not a performance benchmark or naturalness assessment. No manual listening approval is claimed for this take.

This deliberately crashes a child worker through the production provider. It does not crash the whole native application, restore a queue across a Windows restart or validate a full video render. Earlier cancellation and exact recognised-content checks apply to the same underlying adapter recipe; production UI cancellation still needs representative workflow acceptance.

## Regression evidence and retained failures

The backend run attempts discovery in the previous 45 modules plus the new runtime-selection module and runs 775 cases. Its raw report and per-module logs are retained in [the backend receipt](validation/2026-10-13-xtts-production-backend.json). Seven module entries are not accepted in that raw run: local socket restrictions affected three, credential access affected one, a forced offline environment conflicted with two expectations in readiness, and two standalone scripts exposed zero unittest cases. Final source changes and affected tests are covered by separate reruns and a consolidated integrity report.

The first focused invocation failed because the embedded interpreter did not import the workspace automatically. A corrected invocation then encountered Windows sandbox atomic-rename restrictions in system temporary directories. The final runner uses workspace-owned temporary roots. These failed logs remain retained; they are not successful test evidence.

The initial backend local HTTP test hit Windows socket permission error 10013 connecting to its temporary localhost server. The identical test passed all nine checks when rerun with the required local permission. It did not contact an external API. That successful [permitted rerun](validation/2026-10-13-xtts-production-http-permitted.log) is kept separately from the failed original log.

The other affected modules passed 104 checks in the [environment-corrected rerun](validation/2026-10-13-xtts-production-environment-rerun.log): cue review, dialogue connections, readiness and the general suite. Local servers used test responses; the Windows credential test used a random test entry and deleted it. No live model or paid service was called. Resource warnings about audio file handles remain visible in the logs and are not suppressed or resolved by this pass.

`dev.test_model_download` and `dev.test_pipeline_dryrun` are standalone scripts that can download fixtures or mutate application state, not unittest suites. Importing them ran zero cases. They are explicitly excluded from acceptance and from the corrected future runner. Their functional areas have separate discovery tests, including model assets, deletion safety, pipeline foundation and queue contracts. No claim is made that the standalone scripts ran successfully.

The final [focused suite](validation/2026-10-13-xtts-production-final-focused.log) covers setup inspection, runtime selection and existing language/provider boundaries after final edits. It includes three new readiness cases: valid recipe without inference, unavailable runtime and rejected GPU selection. The [consolidated receipt](validation/2026-10-13-xtts-production-integrity.json) states the accepted total and any remaining failure; it must be read alongside raw results.

With the permitted and environment-corrected reruns, **778 distinct discovered backend cases pass**. Repeated focused cases are not added again to the total. The original raw report remains failed; it is preserved rather than rewritten. This is backend contract acceptance, not 778 full model/video workflows.

## Release gates still open

The application is not release-ready. Current acceptance covers an explicit CPU XTTS route, not every model, language, input or stage.

- Complete the nontechnical runtime selection and validated portable packaging/default migration. Verify lifecycle/cancellation through the native UI and a disposable packaged copy.
- Repair the other runtime families, especially the shared Python 3.10/dependency conflicts and the separate RVC/Fairseq/OmegaConf family, through reviewed package plans.
- Validate representative full videos, long/noisy/music/multiple-speaker inputs, subtitle/audio workflows, language combinations and optional stages. Retest downloads, interruption, offline use and fresh gated-model onboarding.
- Calibrate resource/ETA estimates and memory limits with measurements. Validate bounded parallel jobs under realistic model and device contention.
- Verify whole-application crash recovery and clean-machine Windows prerequisites, including WebView2 and native runtime libraries.
- Resolve the owner's application license and complete component/native/model redistribution obligations. Existing notice gaps and model terms are not cleared by a successful dependency scan.
- Review retained generation/startup warnings and broaden compatibility acceptance before treating this recipe as a general upgrade.

No Linux/macOS native acceptance, public release, license choice, default switch or comprehensive quality certification occurred in this pass.
 
## Subsequent iteration

The developer-only selection described above has subsequently gained a Settings choice, saved-selection routing and portable recipe closure. A fresh relocated QA copy passed actual speech, stage cleanup, cancellation and integrity acceptance, with the current runtime still selected by default. Slow session shutdown now stops only its owned process tree rather than cancelling the enclosing job. See [the later selection/portable iteration](XTTS_SELECTION_AND_PORTABLE_ITERATION_2026-10-13.md) for the 790-case final backend run, retained failed attempts and remaining release gates. Earlier receipts in this document remain historical evidence for their recorded source versions.
