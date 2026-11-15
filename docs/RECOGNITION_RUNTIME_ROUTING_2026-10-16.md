# Recognition runtime routing — 16 October 2026

## Outcome

CPU recognition can now explicitly use its existing separate Python 3.13
runtime through application settings. Both audio and video pipelines pass
that choice into the provider, preflight checks validate the selected runtime,
and run manifests record the interpreter and runtime identity actually used.
This removes the need for a global interpreter override for this route.

The setting remains **Current runtime** by default. The separate environment
is labeled **Isolated CPU runtime (trial)** and is available only when the
local recipe validates. Selecting it changes the CPU worker environment,
not the checkpoint, language, GPU recognition provider or API connection.
No dependencies, models or frameworks were added. Saved user defaults and
model connections were not changed during development or acceptance.

This completes explicit CPU recognition routing for an opt-in trial. It is
not an approval of automatic Hindi recognition, all engines, a public release
or a clean-machine Windows installation.

## Problem addressed

The clean desktop candidate does not contain faster-whisper, Torch or
Transformers. The CPU STT wrapper previously inherited the general worker
interpreter, and preflight tried importing faster-whisper in the desktop
parent. A process-local override could make an evaluation work, but a normal
saved application choice could not select that interpreter. The same override
also affects unrelated workers, so it was unsuitable as the production route.

The separate recognition runtime and converted evaluation checkpoint already
existed under earlier installation approval. This iteration connects that
runtime to the app without changing package versions or relocating models.

## Implementation

| File/area | Behavior and reason |
| --- | --- |
| `core/recognition_runtime.py` | Validates an explicit CPU route using a portable recipe, Python bootstrap hashes, inference-source hashes, the exact dependency lock, and installed distribution metadata. Missing, changed or duplicate metadata fails clearly. `resolve('isolated')` ignores the global worker override; `resolve('legacy')` retains existing worker resolution. |
| `core/runtime_integrity.py` | Standard-library-only path, hash and canonical identity helpers. Minimal engine workers can validate a recipe without importing desktop/pipeline packages such as psutil. Links/junctions in recipe paths are rejected. |
| `runtime_profiles/recognition-candidate/routing-recipe.json` | Binds the already evaluated engine sources and existing Python 3.13.16 bootstrap to the reviewed 24-package lock. Stores relative source names and hashes, with no machine-specific executable path. It does not assert release approval. |
| `core/settings.py` | Adds validated `recognition_runtime`, with `legacy` as its read default. Reading an older settings file does not write a migration. Accepted jobs use the existing frozen settings snapshot. |
| `core/providers/resolve.py` | Accepts runtime selection only for CPU faster-whisper providers. Cloud/API and pinned GPU Whisper resolution are independent of this setting. |
| `core/providers/stt/whisper_local.py` | Resolves and records the selected executable and recipe identity before creating the subprocess. Uses `-B` to avoid worker bytecode caches. Clears old runtime evidence before another invocation so a validation failure cannot inherit an earlier successful interpreter identity. |
| `core/pipeline.py` | Passes the snapshot selection to both audio/shared and video recognition routes, and into their preflight parameters. Existing legacy calls retain their prior resolver argument shape. |
| `core/runtime_checks.py` | Isolated CPU preflight validates that environment instead of importing faster-whisper into the desktop process. No automatic fallback occurs if the isolated recipe is unavailable. |
| `core/engine_readiness.py` | Reports the selected CPU route and identity. Optional runtime probing runs in that environment. A failed probe for a selected local checkpoint remains `needs_setup`; later artifact reporting does not overwrite that failure. |
| `core/runtime_probe_contract.py`, `core/runtime_probe_worker.py` | Add a bounded CPU-only faster-whisper probe: validates the actual interpreter, package import origins, required native imports, ONNX CPU provider and a small NumPy arithmetic operation. Applies the existing decoder compatibility adapter. It loads no model and blocks socket connections through the existing probe framework. |
| `bridge/api.py` | Exposes readiness for the selector, refuses saving an unavailable isolated runtime, and supplies the saved selection to engine inspection. |
| Frontend settings/types | Adds the CPU recognition runtime selector and a description explaining its scope. The option is disabled if local validation fails. No new UI library was used. |
| `core/run_manifest.py` | Retains the selected recognition provider's actual runtime evidence after inference. The existing operation finalizer also refreshes provider identity on failure. |
| `core/cue_review.py` | Omits the new legacy default from old review digests, preserving existing review compatibility. An explicit isolated choice remains part of the configuration digest. |
| `packaging/build_portable.py` | Adds an explicit recognition profile option. Inventory validates the recipe and includes its exact lock and runtime recipe alongside the runtime. Models and personal settings are not included by this option. |

Runtime validation checks the declared bootstrap, inference recipe and package
metadata on selection/use; it is not a full package-payload hash scan on every
render. The separate acceptance integrity pass verifies installed payloads.
Recipe hashes are a reproducibility/drift check, not a security boundary
against someone who can rewrite the application and its recipes together.

## Verification

### Saved setting to actual inference

`dev/evaluate_recognition_routing.py` runs the clean desktop interpreter with
disposable application configuration and settings. It sets an intentionally
invalid global worker override, saves the isolated selection, freezes settings,
and selects the existing converted CTranslate2 checkpoint through a disposable
registry snapshot. No user model registration is written.

The corrected run passes **18 checks**:

- Reloads the saved selection and passes real audio-job preflight without
  recognition packages in the desktop parent.
- Passes the actual isolated dependency probe with `model_loaded=false`.
- Runs the real shared pipeline recognition helper on the existing English
  test audio and confirmed Hindi reference, including normalization, grouping,
  source-language resolution and manifest artifacts.
- English words match the known sentence exactly and preserve automatic
  detection confidence; explicit Hindi retains hint origin and null confidence.
- Records the selected interpreter, `isolated` selection and matching runtime
  identity in each operation; both workers exit and owned workspaces disappear.
- Confirms that a later settings change does not alter the accepted snapshot.
- Surfaces a bounded missing-media worker error and cancels an observed owned
  worker, with a measured acknowledgement of 0.129 seconds.
- Confirms that the desktop parent still has no Torch, Transformers or
  faster-whisper package.

Evidence: `validation/2026-10-16-recognition-routing-real-corrected.json` and
its log. Cancellation observes an active child; it does not establish
interruption at a particular decoder token. The helper test stops after the
recognition/source-moderation stage; it is not a full dubbed video render.

### Interface and portable inventory

`dev/evaluate_recognition_settings_native.py` extends the existing native
WinForms/WebView2 harness, using temporary app state and a hidden test window.
The corrected native receipt passes **26 checks**, validating the existing six-screen walkthrough,
speech selector and the new recognition selector, including its enabled option
and persisted value through the real JavaScript/Python bridge. This is native
programmatic integration acceptance, not manual visual/accessibility approval.

Evidence: `validation/2026-10-16-recognition-routing-native-ready.json`.
The frontend TypeScript/Vite build passes; existing chunk-size and mixed-import
warnings remain. The portable inventory is written to
`validation/2026-10-16-recognition-routing-portable-manifest-final.json`. No new
multi-GB portable copy was created and no redistribution approval is implied.

### Regression checks

The first full shared-runtime run passes **831 tests** in 200.422 seconds.
Final scoped desktop acceptance passes **104 tests** in 3.853 seconds. Counts
overlap. The repeated full suite passes **831 tests** in 151.534 seconds after
the helper dependency repair. Its suite was loaded before the final additional
malformed-recipe case; the 104-case desktop run includes that case and the final
type guard. The final receipt binds both runs to the current source snapshot.

New tests cover recipe/bootstrap/source/lock/version drift, duplicate metadata,
missing recipes, route independence, frozen saved settings, invalid selection
preservation, bridge rejection before saving, isolated preflight, failed
readiness probes and inclusion of the recipe/lock in portable inventory.

### Retained failures and corrections

1. The recipe preparer initially looked for the unchanged decoder adapter hash
   in the source-hint receipt, which did not list it. It now checks that one
   source against the earlier candidate acceptance and all remaining inference
   sources against the source-hint receipt. No package was reinstalled.
2. The first focused run failed one fixture cleanup assertion because the new
   `-B` argument moved the output-path argument. The fixture was corrected;
   worker error and cleanup behavior were not weakened.
3. The first real probe failed with missing psutil. The validator's imported
   hash helpers pulled in pipeline/render-context dependencies. The new
   standard-library helper module removes that coupling. No psutil was added to
   the recognition environment.
4. Two native attempts failed assumptions in the old harness: a fixed delay
   was too short for the asynchronous settings call, and another attempt tested
   Settings before its loaded controls appeared. The harness now waits up to
   30 seconds for rendered controls and reads saved values until completion.
   Original failed receipts are retained. No production delays or automatic
   test-success paths were added.

## Preservation, limits and next work

The historical integrity verifier still reports `original_sources_preserved=false`
because this iteration intentionally changes pipeline, preflight and bridge
source. All five other preservation checks pass: all **2,316 installed package
payload files**, saved user state, original model assets, existing XTTS identity
and continued absence of the temporary Ollama installation. The iteration
closeout records the exact expected source differences rather than rewriting
the historical baseline.

Automatic Hindi detection still confuses the confirmed Hindi reference with
Urdu. Explicit Hindi improves script selection but does not remove existing
word errors. The separate runtime remains an opt-in CPU trial, with unchanged
checkpoint selection and no automatic model download initiated here.

Other engines still require their own supported-runtime work, particularly
NLLB/M2M100, Demucs, RVC and visual processing. Existing GPU routes also retain
their earlier portability/support limitations. Broader long/noisy/multispeaker
workflow acceptance, clean-machine prerequisites, owner licensing and missing
third-party notices remain release gates. Any additional package/model/tool
installation still requires the user's prior approval.
