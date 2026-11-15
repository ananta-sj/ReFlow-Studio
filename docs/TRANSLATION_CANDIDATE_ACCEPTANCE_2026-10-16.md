# Separate M2M100 CPU runtime: implementation and acceptance

Date: 16 October 2026. Decision: technical acceptance for explicit trial use; no production promotion or full-release approval.

## Authorization and completed scope

The user approved the separate runtime and tests described in [the reviewed proposal](M2M100_RUNTIME_PLAN_2026-10-16.md). This iteration built that candidate, connected it to the existing M2M100 fallback, exercised actual offline translation through the subtitle pipeline, checked the native settings interface, and removed owned installation staging. No additional model was downloaded. Existing runtime selections remain unchanged.

The new directory is `runtime_profiles/translation-candidate`. It contains existing embedded Python 3.13.16, 40 copied distributions, and the newly approved SentencePiece 0.2.2 wheel: 41 distributions total. Its measured size after acceptance is **670,128,866 bytes**, in **20,043 files**. This is additional storage for the isolated candidate, not a reduction of total application size.

| Build item | Verified result |
| --- | --- |
| New dependency | SentencePiece 0.2.2, CPython 3.13 Windows x64 |
| New package archive | 1,247,987 bytes |
| Archive SHA-256 | `74f0ee601047c0c12a783088b51be4e6214a62ecd9e02278c477433cd16e0ed9` |
| Copied package payload | 19,991 files checked; 645,446,760 bytes |
| Python bootstrap | 33 files; 22,062,412 bytes |
| CPU inference stack | PyTorch 2.14.1+cpu; Transformers 5.19.0 |
| New SentencePiece installed payload | 15 RECORD-hashed files verified |
| Runtime identity | `9d498b5b21a8e7b2acadb8a9fcc5d37833758d14e9775e6c330f4d13970f69f9` |

The [proposal receipt](validation/2026-10-16-m2m100-runtime-proposal.json) contains the exact dependency versions and source metadata. The [build receipt](validation/2026-10-16-translation-candidate-build.json) records the actual copy and download. The builder used the pinned official wheel, checked its size, SHA-256 and metadata, and rejected unsafe archive destinations and collisions. It performed no dependency resolution or source compilation. Existing entrypoints outside the candidate are not silently copied into unrelated locations.

## Execution architecture

Settings now exposes **M2M100 fallback runtime**, with the current runtime and **Isolated CPU runtime (trial)** choices. The selection applies to the built-in Ollama/M2M100 translation provider's local fallback. NLLB, IndicTrans2 and API translation retain their separate routing. The legacy choice remains the default; reading old settings does not rewrite them.

`core/m2m100_runtime.py` checks the approved proposal, bootstrap, exact package metadata closure and a bound inference-source recipe. It validates the existing local model assets and exposes trial readiness. The recipe detects drift in the worker, language, source-language, generation and completion policies. Missing or invalid candidates fail preflight rather than silently executing the same request in the legacy runtime.

`core/providers/translation/m2m100_isolated.py` owns a persistent feature session within the current job. Repeated cues reuse one worker and one loaded model. Cross-job session reuse is rejected. Standalone calls receive their own owned job context, and release is idempotent.

`core/m2m100_worker.py` loads only the local checkpoint, using restricted weight loading (`weights_only=True`). Offline flags and a network audit hook apply inside the worker. Source/target language validation, tokenizer IDs, input limits, output completion and nonblank checks remain active. A generation stopping criterion checks the job cancellation signal at decoder boundaries; process and workspace cleanup are exercised with actual inference.

The existing checkpoint in `models/translation/m2m100_418M` is reused. Its weight file is 1,935,796,948 bytes, SHA-256 `d907ea45e4e4b9db163382a6674f6218b3c59566fe06d77f4055c208b4e87ed1`. It was verified, not replaced or copied into another model directory.

Frozen pipeline settings, subtitle/audio/video preflight, cue-review translation, engine readiness, a bounded CPU dependency probe and run evidence now carry the explicit runtime selection. Run manifests record the actual worker interpreter and runtime identity. The desktop parent does not need Torch, Transformers or SentencePiece for this route.

The portable inventory knows how to include the selected candidate and its plan/recipe. This iteration tests inventory closure with fixtures; it does **not** create or validate a complete relocated portable distribution.

## Validation results and limits

| Evidence | Result | Scope |
| --- | --- | --- |
| [Full backend log](validation/2026-10-16-m2m100-routing-full-backend.log) | 867 tests passed; 185.827 s | Regression suite |
| [Focused log](validation/2026-10-16-m2m100-routing-focused.log) | 73 tests passed; 11.128 s | Overlaps the backend suite; not an additional independent total |
| [Candidate native checks](validation/2026-10-16-translation-candidate-native.json) | 56 passed | Exact closure, actual native imports/origins, CPU arithmetic and tokenizer roundtrip |
| [Actual translation acceptance](validation/2026-10-16-m2m100-routing-real-corrected.json) | 17 passed | Existing weights, full subtitle pipeline, warm session, cancellation and cleanup |
| [Native interface acceptance](validation/2026-10-16-m2m100-routing-native.json) | 22 passed | Actual WinForms/WebView2 bridge, selector persistence and six-page walkthrough |
| [Frontend build](validation/2026-10-16-m2m100-routing-frontend-build.log) | Passed; 4.86 s | TypeScript/Vite; existing chunk/mixed-import warnings remain |

The real test ran from the separate desktop runtime, with no AI packages in that parent and an intentionally invalid general worker override. Ollama discovery was mocked unavailable so the test exercised the actual isolated fallback without a live API or Ollama installation. The candidate dependency probe then ran in the candidate interpreter.

The complete `subtitle_translate` pipeline translated a two-cue English SRT into Hindi. Both original timing windows, 0–2 seconds and 2–4 seconds, survived. It produced a completed manifest, published the subtitle output within disposable test storage, recorded the real runtime identity, and cleaned up its worker. Separate warm-worker requests produced English→Hindi, Hindi→English and English→French output without a second model load or PID change. Oversized input was rejected and a subsequent request succeeded in the same worker.

Examples recorded in the actual receipt include `Hello world.` → `हैलो दुनिया।`, `नमस्ते दुनिया।` → `Hello to the world.`, and `Good morning.` → `Bon matin !`. These are evidence of actual execution; they are not a human-approved semantic benchmark. Nonempty output alone does not establish translation quality.

Cancellation was requested only after observing an active generation boundary. Cancellation and release completed in **0.551 seconds**, with the owned worker exited and its workspace removed. This is one measured acceptance case, not a universal latency guarantee.

Native interface checks are programmatic integration tests with disposable settings. They do not replace manual visual/accessibility review or clean-machine acceptance. The real translation test does not establish complete dubbing, long-video synchronization, background preservation or speech quality.

## Retained failures and corrections

The first actual-pipeline attempt failed in test setup: configuration had already created the scratch output directory, and the test tried to create it again. The test now permits the existing owned directory. The failed [original receipt](validation/2026-10-16-m2m100-routing-real.json) and log remain alongside the successful corrected receipt. This did not require a production pipeline change.

The initial notice inventory omitted British-spelled `LICENCE` files, incorrectly reporting a third missing package notice. The inventory helper was corrected and rerun; the initial closeout and acceptance JSON snapshots remain as `*-initial.json`. The corrected inventory identifies installed notice files for 39 packages and two absent installed notice sets: SentencePiece and tokenizers.

## Notices, preservation and cleanup

License text for those two gaps was collected separately from the official matching version tags: [SentencePiece v0.2.2](https://raw.githubusercontent.com/google/sentencepiece/v0.2.2/LICENSE) and [tokenizers v0.23.3](https://raw.githubusercontent.com/huggingface/tokenizers/v0.23.3/LICENSE). The [upstream supplement receipt](validation/2026-10-16-translation-candidate-upstream-notices.json) records origin, bytes and hashes; finalization rechecks those files. These are upstream supplements, not files found in the installed wheel RECORD. Package installations were not modified to conceal that distinction. Collecting them does not clear distribution rights, model conditions or the owner's undecided Reflow code license.

The [final acceptance receipt](validation/2026-10-16-translation-candidate-acceptance.json) verifies original XTTS, NLLB and recognition runtime identities, protected saved-state hashes, existing XTTS/NLLB assets and the M2M100 model contract. It records current implementation, runtime-profile and frontend-build hashes. Saved application defaults remain unchanged. Temporary Ollama evaluation storage remains absent.

Only the explicitly owned translation installer staging directory was removed, after marker and contents checks. Cleanup removed **1,248,026 bytes** including the downloaded wheel and ownership marker. No model was removed. The final candidate scan found **zero `__pycache__` directories**. This is a scoped cleanup, not a claim that every historical app cache was removed.

## Changed implementation and reproducibility

- Runtime lifecycle: `core/m2m100_runtime.py`, `core/m2m100_worker.py`, `core/providers/translation/m2m100_isolated.py`.
- Selection and execution: `core/llm_translator.py`, `core/providers/translation/ollama_m2m100_local.py`, `core/providers/resolve.py`, `core/settings.py`, `core/pipeline.py`, `core/cue_review.py`.
- Readiness and evidence: `core/runtime_checks.py`, `core/engine_readiness.py`, `core/runtime_probe_contract.py`, `core/runtime_probe_worker.py`, `bridge/api.py`.
- Interface and packaging: `frontend/src/pages/Settings.tsx`, `frontend/src/lib/api.ts`, `packaging/build_portable.py`.
- Build and validation helpers: `dev/build_translation_candidate.py`, `dev/evaluate_translation_candidate.py`, `dev/prepare_m2m100_routing_recipe.py`, `dev/test_m2m100_runtime.py`, `dev/evaluate_m2m100_routing.py`, `dev/evaluate_m2m100_settings_native.py`, `dev/close_translation_candidate.py`, `dev/collect_translation_upstream_notices.py`, `dev/finalize_translation_candidate.py`.

Builder creation is deliberately one-shot and refuses an existing target/staging tree. Do not rerun it against the accepted candidate. Diagnostic and acceptance helpers produce evidence; native/live checks use disposable state, not the user's normal settings. The final receipt binds tested sources and lists the exact evidence. Source changes require new relevant validation; inference-source changes also require an explicitly refreshed runtime recipe.

## Remaining release work

This completes the approved M2M100 candidate build and technical integration. It does not complete all product release gates. Remaining work includes broader translation and recognition quality acceptance (including automatic Hindi/Urdu ambiguity), runtime ownership for remaining separation/RVC/visual engines, representative long/noisy/music/multispeaker video workflows, download retry/offline onboarding, parallel/resource calibration, a physically relocated Windows portable and clean-machine test, manual interface/accessibility checks, and licensing/redistribution decisions. Other platforms remain experimental. Neither this candidate nor the application is declared release-ready.
