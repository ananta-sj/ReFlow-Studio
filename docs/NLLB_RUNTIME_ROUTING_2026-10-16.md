# NLLB runtime routing — 16 October 2026

## Purpose and result

This iteration moves selected NLLB translation into a job-owned process in an
existing modern CPU environment. It follows the recognition-runtime work and
repairs execution architecture rather than adjusting voice samples.

The app has an explicit **NLLB translation runtime** choice: **Current runtime**
or **Isolated CPU runtime (trial)**. The saved default remains current/legacy.
The trial reuses the already approved `xtts-security-candidate` package
environment; it does not load XTTS speech weights and does not require an
XTTS voice to be selected. NLLB retains its selected translation checkpoint.
No package, model, framework, Ollama installation or paid service was added.

IndicTrans2, API translation and the Ollama/M2M100 default retain their existing
routes. This iteration does not claim all translation engines are migrated or
that NLLB output quality has improved simply because it uses another runtime.

## Findings

NLLB and the M2M100 fallback previously loaded Torch/Transformers into the app
process. The clean desktop candidate lacks those packages. IndicTrans2 already
has a separate worker, but NLLB did not have a saved, feature-specific route.

The existing modern CPU environment contains PyTorch 2.14.1+cpu and Transformers
5.19.0. Its NLLB tokenizer can read the existing local `tokenizer.json` without
SentencePiece. An offline feasibility test loaded the original 600M checkpoint
and translated three sentences across English→Hindi and Hindi→English. All
eight model/tokenizer/metadata files retained their hashes.

The same environment lacks SentencePiece. The installed M2M100 tokenizer
requires that package and its checkpoint does not supply an equivalent fast
tokenizer JSON. Copying a Python 3.10 native package into Python 3.13 would not
be a valid migration. Adding SentencePiece directly to the existing exact
99-package environment would also invalidate its XTTS package lock. Neither
action was taken. M2M100 needs a separately reviewed compatible environment or
another approved dependency plan before that route can be modernized.

## Code changes

| Area | Change |
| --- | --- |
| `core/nllb_runtime.py` | Verifies the existing CPU environment and a new NLLB source recipe. Its identity includes the underlying runtime and NLLB worker/policy source hashes. Missing/stale recipes report unavailable. |
| `core/nllb_runtime_manifest.json` | Binds the worker, provider, language policies, completion guard and generation-control sources to the approved underlying package identity. |
| `core/nllb_worker.py` | Persistent offline CPU translation worker. Loads NLLB once, processes serial cue requests, checks the stop marker during decoder generation, and closes its owned context on exit. It validates the interpreter and refuses network operations. |
| `core/providers/translation/nllb_local.py` | Adds an explicit runtime choice and lazily creates a job-owned session. Validates source/target/instructions before starting the worker. Rejects unsupported explicit GPU selection for the CPU trial. Repeated cues in one job reuse the worker; a standalone call owns and releases its temporary job. `release()` closes the session and drops model references. |
| `core/providers/resolve.py` | Routes only selected NLLB connections to this environment. Other translation providers are unchanged. |
| `core/pipeline.py` | Passes frozen NLLB settings through resolver/preflight for audio, video and subtitles. Translation stage cleanup now releases NLLB on success, failure and generator close. |
| `core/cue_review.py` | Passes the selection to review translation/alternative operations. Corrected-cue translation uses the existing stage cleanup context, including failures. The new legacy default is omitted from historical review digests; opting into isolation changes the recipe. |
| Settings, bridge and frontend | Adds a validated saved choice, reports local availability, refuses saving an unavailable isolated route, and exposes a disabled/enabled selector with its scope explained. Existing saved files are not rewritten just by reading the new default. |
| Readiness/probe | Checks the selected CPU environment without model construction. An explicit probe runs Torch/Transformers/tokenizer imports and CPU arithmetic in that interpreter, with package-origin and no-network checks. It loads no translation weights. |

Source/target language mappings, forced target token, input-window checks,
nonblank output requirement and end-of-sequence/output-cap checks remain in
effect. Fixed-vocabulary NLLB still rejects custom instructions. Moving it into
a worker does not turn it into an instruction-following dialogue editor.

The worker is stage-owned and serializes its calls. Separate jobs have separate
processes/model instances; sharing one provider session across jobs is rejected.
This is not a claim that parallel model loads are free of RAM costs. The route
is CPU-only regardless of the render panel's GPU choice; existing resource
estimates already treat NLLB translation as CPU work.

## Verification

### Offline feasibility

`dev/evaluate_nllb_existing_runtime.py` and
`validation/2026-10-16-nllb-existing-runtime-feasibility.json` record the original
checkpoint and all file hashes, exact runtime versions and these outputs:

- “Hello world.” → “हैलो दुनिया.”
- “Good morning. This is a short test.” → “सुप्रभात, यह एक छोटी सी परीक्षा है।”
- “नमस्ते दुनिया।” → “Hello world.”

All five feasibility checks passed. The timed model/translation portion took
57.142 seconds. These short examples establish mechanics, not semantic-quality
approval for long or expressive dialogue. The newer tokenizer/runtime may
produce different wording than older Transformers releases.

### Regression and interface acceptance

- Full existing-runtime backend suite: **846 tests passed**, 159.889 seconds,
  `validation/2026-10-16-nllb-routing-full-backend.log`.
- Focused clean-desktop suite: **76 tests passed**, 6.055 seconds,
  `validation/2026-10-16-nllb-routing-focused.log`. Counts overlap the full suite.
- TypeScript/Vite build passed. Existing chunk-size/mixed-import warnings remain.
- Hidden native WinForms/WebView2 walkthrough passed **22 checks**, including selecting and
  persisting the NLLB runtime through the actual bridge:
  `validation/2026-10-16-nllb-routing-native.json`.

Native acceptance is programmatic integration on this machine, not manual
visual/accessibility approval or a clean-machine Windows test. Runtime choices
were written only into disposable test settings.

The real worker acceptance passes **13 checks**, recorded separately in
`validation/2026-10-16-nllb-routing-real-corrected.json`. It exercises a saved
selection, real preflight and dependency probe, repeated cue translation,
actual interpreter identity in the run manifest, worker reuse/release, and
decoder cancellation. The final acceptance receipt records the measured checks
and distinguishes that result from the earlier failed harness attempt. A
decoder boundary was observed before cancellation was requested;
cancellation plus worker release took **0.572 seconds**. The desktop parent
remained free of Torch and Transformers throughout this integration run.

### Retained failures

The first metadata inspection stopped at missing SentencePiece. The later NLLB
tokenizer feasibility run proved that NLLB itself does not need it here; M2M100
still does. No dependency was silently added to make the inspection pass.

The first full worker harness translated both directions in one process and
verified stage release, but then failed `StopIteration` when looking for a
translation operation. It had created a manifest without binding the existing
thread-local manifest context used by `_translate_line`. The corrected harness
binds that context like a production run and preserves the failed receipt.
This was a test-fixture correction, not a production evidence bypass.

## Preservation and packaging

The trial shares an existing package environment, so there is no duplicate
Torch installation or new multi-GB portable copy. A portable inventory that
includes `xtts-security-candidate` already carries the underlying runtime and
bound lock; the normal core tree carries the NLLB worker and manifest. The
default portable setup without that profile will report this option unavailable.
This iteration validates inventory closure without asserting distribution rights
or creating a release archive.

Final closeout verifies the existing environment identity, its installed Python
source RECORD hashes, protected saved state and NLLB/M2M100 model hashes. Native
package binaries are not claimed to receive a new security audit in this pass.
The closeout passed for all **13,902** checked Python sources across the **99**
installed distributions. The unchanged underlying runtime identity is
`85a69c83e2310e8e53303987947f2313cb4c6aa70627eeccae3b85b564fd8163`.
The slow restricted-runner audit was stopped only after checking its process
identity; the identical audit completed with normal file access. Both logs are
retained, with the successful run in
`validation/2026-10-16-nllb-routing-finalization-permitted.log` and the consolidated
result in `validation/2026-10-16-nllb-routing-acceptance.json`.
Original outputs, references, registry/defaults and all prior runtime recipes
are retained. Historical acceptance receipts remain historical snapshots when
application source changes; their baselines are not rewritten to hide edits.

## Remaining work and approval boundary

1. Review a separate M2M100-capable runtime/dependency proposal. SentencePiece
   support for the target Python must be verified before requesting installation;
   the working XTTS environment must remain intact. No such install is authorized
   or performed by this iteration.
2. Validate longer and multilingual NLLB output semantically and compare its
   wording against the existing baseline; nonempty output is not a quality score.
3. Continue Demucs, RVC and visual-engine runtime migration, full audio/video
   workflows and clean-machine acceptance.
4. Resolve owner licensing and third-party/model redistribution requirements.

The NLLB trial and the broader application remain in different acceptance scopes.
Passing this iteration does not mark Reflow release ready or change defaults.
