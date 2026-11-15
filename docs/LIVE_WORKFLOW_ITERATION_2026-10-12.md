# Installed-engine workflow and recovery — 12 October 2026

## Scope

The user authorized live tests with already installed engines, without new models or paid calls. This iteration uses the saved Whisper Turbo, IndicTrans2 and IndicF5 route, the reviewed Abhishek reference profile and existing Demucs weights. Engine tests set Reflow/Hugging Face/Transformers offline flags; no packages, frameworks, model weights or API connections were added.

Native interface testing and real-engine testing are distinct. The owned native fixture uses synthetic work to inspect Dashboard layout. The live tests call the ordinary `ReflowPipeline.run` entry with real source audio and providers; no transcript, translation or generated waveform is substituted.

## Native Dashboard acceptance

The rebuilt Windows app was opened in a fresh owned fixture, `temp/native-active-vp3_fxj2`. Its restored queue was resumed through the actual recovery dialog. Dashboard visibly showed `Currently rendering / ONE_FIXTURE.mp4`, separately from `Next pending video / TWO_FIXTURE.mp4`. The estimate named TWO, and the active progress section named ONE.

After releasing the first synthetic payload, Dashboard labelled ONE as `Last render input` and retained TWO as the selected pending input. The window was closed while idle and its process exited successfully. Six native evidence checks passed. This validates the inspected 1200 × 763 viewport; other sizes and the stopping layout were not newly checked natively.

Evidence: [native observations](validation/2026-10-12-live-workflow-native-dashboard.json), [native integrity](validation/2026-10-12-live-workflow-native-integrity.json), [fixture bridge receipt](validation/2026-10-12-live-workflow-native-bridge.json).

## Negative real-engine cases retained

### Alternate source: no recognized speech

The first eight seconds of `Sample/3.mp4` were processed with the saved real route. Whisper returned no spoken words and the run stopped before translation/speech. The run took 333 seconds, released its worker and removed its owned workspace. This is a recognition failure/empty-result outcome, not proof that the source contains no audible speech. It produced no dub and was not counted as a successful workflow.

The existing driver uses a historical date prefix, but this run occurred on 12 October. Its newly generated receipt is retained as `2026-10-09-pipeline-foundation-independent-c9786247.json`, and an explicitly dated copy is [independent negative evidence](validation/2026-10-12-live-workflow-independent-negative.json). Older receipts were not reused as current acceptance.

### Dense excerpt: translation does not fit

The 16–24 second section of `Sample/2.mp4` completed real Demucs separation, recognition and IndicTrans2 translation. Before speech generation, the duration supervisor predicted **10.027 seconds** of Hindi speech against **8.000 seconds** available. It raised `DialogueReviewRequired`; no speech take or final video was published. The owned workspace and workers were released, and saved state/source hashes remained unchanged.

This is a real limitation of automatic dubbing on dense material. The guard prevents rushed/truncated speech, but the currently installed route does not automatically produce a meaning-preserving shorter translation. Passing a simpler excerpt does not resolve that limitation. No manual wording was inserted to bypass the guard.

Evidence: [dense-excerpt receipt](validation/2026-10-12-live-workflow-7e72844c.json), [execution log](validation/2026-10-12-live-workflow-execution.log).

## Actual cancellation and separation-repeatability defect

The closing complete phrase, starting at 115.6 seconds of `Sample/2.mp4`, was extracted into a 6.9-second clip. The first live pass generated fresh recognition/translation, then requested cancellation when the actual IndicF5 worker logged `generating`. Cancellation propagated as `RenderCancelled`. The owned worker PID was recorded, its registered process exited, the session thread finished, and cleanup removed the workspace in **0.297 seconds** after the request.

The restart re-separated the same input. Its vocal WAV hash differed (`1991b029…` versus `7c02334b…`), as did its background hash. Local installed Demucs code uses Python `random.randint` for its default single stabilization shift. Recognition checkpoints intentionally bind to exact separated PCM, so differing separation makes reuse unsafe. The original run therefore missed both checkpoints and reran inference, although it eventually exported a video and stems. Its overall recovery acceptance remained false.

The worker seed fix was applied after both unseeded separations had completed, while that run continued. Its later code fingerprint can also differ from the initial pass. Accordingly, this run's misses are not presented as a controlled test isolating random separation as the only changed key input. The differing pre-fix vocal/background hashes and the installed random-shift code establish the reproducibility defect; the final fixed-code run supplies the controlled recovery verification.

Pre-fix evidence: [live receipt](validation/2026-10-12-live-workflow-1c688090.json), [retry log](validation/2026-10-12-live-workflow-retry.log), [output audit](validation/2026-10-12-live-workflow-1c688090-output-audit.json).

## Production repair

`core/run_demucs.py` now seeds Python `random`, NumPy and Torch with zero before invoking the existing Demucs entry point. The existing model, default single stabilization shift, restricted checkpoint loader and command interface remain in use. This makes the CPU separation recipe repeatable rather than removing stabilization or weakening checkpoint integrity.

Two fresh actual CPU workers separated the same 6.9-second WAV. Their vocal and background WAV hashes were byte-identical. The runs took 31.312 and 28.032 seconds; cleanup succeeded. This proves repeatability for the tested CPU/runtime/input. It is not a guarantee of identical CUDA results on every device, and the separated stems still require listening review for residual narration.

Evidence: [repeatability receipt](validation/2026-10-12-demucs-repeatability-89153e25.json), [repeatability log](validation/2026-10-12-demucs-repeatability.log).

## Verification tooling and audit correction

`dev/verify_live_workflow_recovery.py` checks installed Demucs weight identity before work, extracts an owned source excerpt, runs cancellation then restart against the same output/checkpoint directory, and records manifests, checkpoint events, worker cleanup, source/state hashes and output/stem identity. Its watchdog requests job-owned cancellation after 900 seconds per pass. It uses no arbitrary process termination. Closed session objects can remain registered on the completed context; the verifier checks that their threads finished and processes released instead of interpreting a retained closed object as an alive worker.

`dev/verify_demucs_repeatability.py` performs two actual separations and compares their file hashes. `dev/verify_live_workflow_output.py` inspects exported streams/cues, frame timing, video similarity, stem duration/non-silence and the published background mix without model calls. `dev/verify_dialogue_backend.py` has a `live-workflow` label and records these helpers and the repaired worker in its source hashes.

The first video audit incorrectly required identical decoded pixels. The existing merge path deliberately encodes H.264 at CRF 18, so that assertion would reject a correct export. The audit was corrected to require identical frame timing/count and an FFmpeg SSIM of at least 0.97. It records whether decoded pixels happen to match separately; it does not claim lossless video preservation. The threshold is a verification criterion, not a user acceptance of appearance or shot/speech alignment.

A second harness issue was found after export: the run driver searched for stem WAVs directly under the evaluation directory, while production publishes video and stems inside a bundle subdirectory. Its original receipts therefore report `passed: false` and zero collected stem records, even for the fixed-code run. Those receipts were preserved. The driver now searches beside the actual output for future runs. The independent output audit loads all four explicit stem paths beside the exported video and verifies the underlying execution/cleanup records, manifests and hashes; it does not silently change the original driver's verdict. No additional inference was run merely to correct this metadata lookup.

The pre-fix exported master matched reconstruction from its exported dubbed/background stems through the production ducking method. The background was non-silent but very quiet (about -52.31 LUFS before mixing), so this clip does not provide a strong music/ambience quality challenge. Hindi delivery, residual English leakage, speaker similarity and fine synchronization require listening/viewing; file/stream checks alone do not prove them.

## Final acceptance

The controlled fixed-code run is [0eeba52c](validation/2026-10-12-live-workflow-0eeba52c.json). Its first pass performed fresh recognition/translation and cancelled real IndicF5 speech generation. Cancellation through cleanup took **0.234 seconds**; the cancelled manifest retained evidence but no completed video. The first pass took 391.953 seconds including verification, inference and model initialization.

The restart used the same source/parameters and produced identical separated vocal/background hashes. Both STT and translation checkpoints hit. The restart manifest contains no STT or translation inference operation; speech ran again. It exported a complete video, Hindi subtitle stream and four audio stems. Its total elapsed time was **217.844 seconds**, including repeated verification, separation and speech initialization/generation. The completed output duration is **6.9 seconds**, with **172 video frames**, unchanged frame timing and **SSIM 0.998571** against the input excerpt.

All **15 independent output/recovery audit checks passed**. The master PCM matches the production ducking reconstruction from the dubbed/background stems, the streams fully decode, and source/translation cue artifacts and output hashes agree with the manifest. Workers/processes released and both owned workspaces were removed. The original driver verdict remains false solely because it collected stems from the wrong directory; that distinction is explicit in the [independent audit](validation/2026-10-12-live-workflow-0eeba52c-output-audit.json).

The user then reviewed this exact automatic output and answered **“Natural, timing matches, no English audible.”** The [human review receipt](validation/2026-10-12-live-workflow-human-review.json) binds that response to SHA256 `42d80384957dfe5e74a5ba7b80d962bf383bc1380d6c22e6dedbc0e72deace0a`. This is human acceptance of delivery/timing/no audible English on this specific short clip, not proof for arbitrary videos or an assessment of every translation style. The earlier machine audit's human-review flags remain false because it was generated before the response; the separate later review receipt is authoritative for that acceptance.

The spoken content is the closing phrase “Charlie Brooker, Newswipe, London.” This demonstrates the full installed route and recovery mechanics with real media; it is a small proper-name-heavy utterance. The dense eight-second excerpt remains blocked, and a longer automatic render is not claimed successful.

Evidence: [final execution log](validation/2026-10-12-live-workflow-final.log), [raw run receipt](validation/2026-10-12-live-workflow-0eeba52c.json), [independent output audit](validation/2026-10-12-live-workflow-0eeba52c-output-audit.json), [human review](validation/2026-10-12-live-workflow-human-review.json). The video is inside the output bundle recorded by these receipts.

## Regression and integrity validation

Seventeen focused checkpoint tests passed. The final complete backend suite passed **763 tests across 44 modules**, with zero failures/errors. It was repeated as audit helpers were corrected so final recorded source hashes match the delivered helper code. Earlier successful receipts/logs were retained separately; the final complete receipt and integrity audit provide the authoritative counts/state/source checks. No backend inference is exercised by that suite; the live provider evidence above is separate.

Existing frontend build/lint and four component contracts from the Dashboard iteration remain historical results. The current native observations validate the rebuilt Dashboard with the same source hash. No frontend source/build changed in this live iteration.

Saved state/video/source-integrity details are recorded in `validation/2026-10-12-live-workflow-integrity.json`. The final backend receipt is `validation/2026-10-12-live-workflow-backend-complete.json`; its current run log is `validation/2026-10-12-live-workflow-backend-verified.log`. Prior logs/receipts retain the initial backend pass and the pass before the stem-audit correction.

The final evidence audit passed **13 checks**: delivered/tested source hashes, five saved state files, the previously accepted Hindi video, the source video, native Dashboard evidence, separation repeatability, identical cancel/restart stems, independent output acceptance, hash-bound human review, worker/workspace cleanup and preservation of the original stem-lookup failure. No user settings or previously accepted media changed. New owned run records, checkpoint caches, output bundles, diagnostics and the normal local Demucs repository YAML are expected validation artifacts, not a size-cleanup operation.

Recheck without inference:

```powershell
& 'C:/Projects/Reflow Studio/build/windows-portable/python.exe' -B 'C:/Projects/Reflow Studio/dev/verify_live_workflow_evidence.py'
```

The verifier is deliberately tied to retained receipts/artifacts. A later production edit or artifact deletion should invalidate its corresponding identity check rather than rewrite historical acceptance. `dev/verify_live_workflow_recovery.py` reruns live engines; it is not the evidence-only recheck.

## Remaining release gates

The dense-excerpt timing guard still needs a usable localization/adaptation path: meaning-preserving shortening, or explicit cue review when the selected translation cannot fit. No new instruction model/API was authorized or installed in this iteration. There is no automatic adversarial reviewer assessing subjective emotion or voice naturalness here.

Real native bridge/queue recovery after a process crash is a separate gate from this direct real-pipeline cancellation/restart test. Earlier native controls and synthetic abrupt-process tests remain useful evidence, but they do not establish a genuine model-running native crash recovery. Long video quality, noisy/multispeaker/music-rich inputs, other languages, optional lip sync/enhancement/filtering, downloads/retries, multiple instances, measured resource estimates and clean-machine/platform packaging remain open.

Cold-start and fingerprint verification time is material even on short inputs. Elapsed provider operations and total pass times are retained, but nested operation times overlap and cannot simply be added. Estimates remain uncalibrated; this run is not a validated CPU/GPU throughput or memory-budget model.
