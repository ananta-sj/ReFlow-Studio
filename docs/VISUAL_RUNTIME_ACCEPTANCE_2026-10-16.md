# Separate CPU face-enhancement runtime — 16 October 2026

## Current decision

The owner approved a separate guarded CPU visual candidate after discussing why face restoration needs its own dependencies. This iteration installs the reviewed 55-package candidate, integrates an explicit application trial choice, and tests actual GFPGAN inference. Current working runtimes and user defaults are preserved. **This is not full application release approval.**

The real three-frame restoration check passes, including failed-worker output preservation and cancellation. The full six-second dubbing attempt instead stopped before enhancement because generated speech did not fit its six-second cue. A separate post-processing integration fixture uses original source audio to exercise enhancement/routing/muxing independently of that speech issue; it must not be described as a successful generated dub.

Final counts, storage, hashes, cleanup and links are recorded in [the consolidated acceptance receipt](validation/2026-10-16-visual-candidate-acceptance.json). The exact authorised packages and known vulnerability were reviewed in [the installation proposal](VISUAL_HELPERS_AND_RUNTIME_PLAN_2026-10-16.md).

## Installed environment and boundaries

`runtime_profiles/visual-candidate` uses Python 3.13.16 and Torch 2.14.1+cpu. It copies 41 established packages from the existing modern XTTS candidate, reuses the two approved BasicSR/FilterPy wheels, and installs 12 hash-pinned wheel downloads totaling **64,466,647 bytes**. No additional package was added to solve an application import problem. No model was downloaded; the existing GFPGAN v1.4, face detector and parser checkpoints are reused and hash-checked.

All package versions, source URLs, artifact SHA-256 values and active dependency links are in [the prepared lock](validation/2026-10-16-visual-runtime-lock-review.json). Built candidate files remain separate from existing environments. The `tb-nightly` prerelease is retained because upstream declares that distribution; there is no silent TensorBoard substitution. This CPU trial is not GPU acceptance or a default migration.

`core/visual_runtime.py` binds the approved lock, Python bootstrap, exact 55-package metadata closure, reviewed BasicSR files and application worker recipe. Source/bootstrap/lock drift produces an explicit error. Its model contract verifies the three reviewed checkpoint hashes before rendering. Other custom GFPGAN checkpoints are not accepted by this pinned candidate merely because their filename matches; they require a separate contract review.

`core/providers/enhancer/gfpgan_local.py` retains the current route and adds an explicit isolated route. The desktop parent validates the candidate/model contract and starts an owned child, with temporary request/log/evidence files, offline model settings and staged destination publication. Worker errors expose a bounded diagnostic tail. Cancellation keeps its original RenderCancelled type and preserves an existing destination. Runtime identity/interpreter evidence is attached to the provider for durable run manifests.

`core/run_visual.py` checks its interpreter/recipe/model hashes, limits Torch threads, activates the import guards before loading the enhancer, and runs real face restoration. Python socket/shell calls are denied; process creation is restricted to bundled FFmpeg/FFprobe paths. Optional BasicSR extension/JIT flags are disabled. Checkpoint deserialization remains restricted through weights-only loading. These are application-scoped measures, not a claim that the upstream package itself is fixed or that arbitrary native code is sandboxed.

## BasicSR security and compatibility guards

BasicSR 1.4.2 remains affected by **CVE-2024-27763**, represented by two aliased advisory records. Its distributed SLURM training launcher interpolates an environment variable into a shell command. The prepared lock retains that finding and its negative security-clearance flag. [Reviewed advisory](https://github.com/advisories/GHSA-86w8-vhw6-q9qq).

`core/visual_imports.py` is an application-owned import adapter. It requires the reviewed BasicSR version, rejects an already-loaded BasicSR package, verifies the exact source bytes, and compiles two modules in memory. Installed package files and upstream wheels stay unchanged.

| Module | Exact upstream SHA-256 | Application adaptation |
| --- | --- | --- |
| `basicsr.utils.dist_util` | `e6a6d7fced5146ff2e1f16cb0ce1c922171fe7e8b28c011178695ebed4f477b8` | Reject `init_dist`, `_init_dist_pytorch`, `_init_dist_slurm`; retain non-distributed inference helpers |
| `basicsr.data.degradations` | `b78e36137ff8e4d783779b5ed611fcf80305633c492ac494ee52b213806f2d83` | Use `torchvision.transforms.functional.rgb_to_grayscale` in place of removed `functional_tensor` import |

The scoped hook is removed after imports or errors; both required guard markers must be present. Changed versions/files, missing launchers and preloaded unguarded modules fail explicitly. Native acceptance exercises all three actual blocked launchers and the modern grayscale API, along with TorchVision's compiled NMS operation. Unit tests cover drift/rejection/hook cleanup. This validates the application restrictions on the tested route; it does not remove the CVE from the upstream version or cover external training use.

## Application routing and interface

The saved `enhancement_runtime` setting accepts `legacy` or `isolated`, defaulting to `legacy`. The existing user file is not automatically rewritten. Selecting the trial requires the validated candidate and local model assets. The Settings page labels it **Face enhancement runtime** and explains the separate CPU process. A disposable native WebView2 window exercises the rendered selector and real bridge persistence.

The selection reaches frozen job settings, video preflight, built-in or connected local GFPGAN provider resolution, engine readiness/probing and manifest evidence. The candidate rejects GPU selections; connected API enhancement retains its existing route. Enhancement disabled does not require this candidate. Existing templates/nodes continue to toggle the same enhancement stage.

Portable inventory accepts `visual-candidate` and includes its reviewed lock and routing recipe while retaining personal-state/model-weight exclusions. The CLI's previously omitted separation profile choice was also added to match the existing separation inventory implementation. This iteration creates an inventory, not a fresh physical portable copy or clean-machine validation.

## Lightweight media boundary repair

Actual worker execution exposed a dependency that metadata resolution could not find: `core.video_frames` imported the entire `pipeline` module for staged publication and media validation. That pulled in Pydub and the audio stack even though the child was only processing frames. Rather than install an unreviewed dependency, this iteration factors media helpers into `core/media_io.py`.

Video frames now use that lightweight module. The pipeline retains its existing validation/manifest-facing interface and delegates shared inner validation; its staged-output helper uses the common implementation. The existing duration/stream checks, previous-output preservation, publication cleanup and job ownership remain. Full backend and frame/output integrity regressions cover this change, and real child rendering exercises the absence of audio packages.

## Actual test evidence and limits

- [Installed native checks](validation/2026-10-16-visual-candidate-native.json): exact package closure/origins, actual compiled TorchVision operation, grayscale compatibility and three blocked training launchers. No face model is loaded by this dependency check.
- [Real face restoration](validation/2026-10-16-visual-candidate-real.json): clean desktop parent, dependency probe, three actual face-model forwards, a decoded one-second/three-frame video, candidate identity evidence, worker exit, real invalid-input failure preservation, cancellation and cleanup. CPU inference took **121.992 seconds** in this run; cancellation returned in **0.119 seconds**. Other checks were running concurrently, so this is not an isolated performance benchmark.
- [Native selector](validation/2026-10-16-visual-routing-native.json): disposable settings/native window and saved trial selection. Real user settings are not used for this test.
- [Full dubbing attempt](validation/2026-10-16-visual-video.json): actual recognition/speech run failed at the established timing guard: **6.605 seconds required after adjustment, 6.000 seconds available**. Enhancement was not reached. No words were cut and no failed result was presented as a completed dub.
- [Post-processing integration fixture](validation/2026-10-16-visual-stage-pipeline-final.json): actual recognition/media/face-enhancement/mux stages with an explicit source-audio fixture replacing speech generation, to check saved/frozen routing and actual enhancement identity in the manifest. This fixture does not validate TTS, translation, Hindi quality or absence of original English.
- [Installed payload/notices](validation/2026-10-16-visual-candidate-payload.json): recorded package file hashes/sizes checked, notices collected, skipped RECORD entries and missing-notice distributions identified. The initial payload scan began before the application media-source split; its original recipe identity is retained as provenance. Installed package bytes were not changed by that split; final native/real receipts use the final recipe identity.

Final backend/focused test counts and timings are in the acceptance receipt. Counts overlap and must not be summed. Discovery excludes the two pre-existing standalone scripts `test_model_download.py` and `test_pipeline_dryrun.py`. Frontend compilation/build passed using existing dependencies.

## Retained failures and corrections

1. TorchVision's official Windows wheel contains backslashes in RECORD paths while ZIP members use forward slashes. Initial verification stopped. The installer now normalises only those record paths, checks traversal/drive restrictions, verifies the same payload hashes, and retains original wheel bytes. Resume requires exact ownership markers and only touches the new candidate/staging; existing payload collisions must byte-match. An initial resume mkdir collision was corrected with an existing-directory-safe creation.
2. A focused test command included a legacy frame test that needs OpenCV, which the clean desktop intentionally lacks. The corrected desktop-focused set excludes that module; the full working-runtime suite still includes it.
3. A guard cleanup test initially inherited preloaded legacy BasicSR modules from preceding tests. Test-local module isolation was corrected; production still correctly rejects preloaded BasicSR. The failed report remains, followed by passing full/focused results.
4. The first real harness mistook the project's `gfpgan/weights` namespace folder for an installed GFPGAN engine. It now checks that namespace origin separately from absent Torch/OpenCV packages.
5. Real model loading then exposed the unnecessary pipeline/audio import described above. The media split repaired it without adding packages.
6. Windows process audit events may report `executable=None` and a quoted command-line string. The initial bundled-utility guard rejected that shape. The corrected guard parses the tool and still requires its resolved bundled path. Regression cases cover the Windows shape, external media tools, shells and network events.
7. An initial full-video harness used the UI key `enhance` rather than canonical `enhance_active`; that test parameter was corrected. The actual subsequent run then found the speech-duration conflict. The first isolated post-processing harness still constructed the base pipeline despite defining its fixture subclass; its failed attempt remains separate from the corrected fixture receipt.

Failed logs/receipts, earlier recipe snapshots and initial acceptance proposals remain under `docs/validation`. They are historical diagnostics, not additional successful runs.

## Cleanup, preservation and remaining work

Finalisation verifies protected user state, established runtime identities, reviewed F5/GFPGAN assets, candidate evidence and current source hashes before removing only owned installer staging. The candidate runtime and test evidence remain intentionally. No existing runtime or model is removed. Package notices are evidence collection; missing notices and owner/third-party/model redistribution decisions remain release work.

Open items include the generated-speech timing conflict from the full video attempt; broader Hindi/long/noisy/music/multi-speaker acceptance; RVC and remaining lip-sync runtime migrations; GPU/resource/parallel calibration; fresh portable/clean-machine/manual checks; and licensing. The existing successful Hindi samples do not close those broader gates. Do not promote this CPU trial to the default or call the whole application release-ready on the basis of these scoped results.

## Final consolidated measurements

- Backend: **930 tests passed in 273.440 seconds**. Clean-desktop focused acceptance: **48 overlapping tests passed in 29.498 seconds**.
- Actual isolated restoration/failure/cancellation: **10 checks**; installed native dependency/guard checks: **74**; native interface checks: **22**; isolated post-processing integration fixture: **9**.
- Installed runtime: **1,048,855,925 bytes**, about **1000.27 MiB**, across **21,608 files**. **21,572 package payload files** verified. No candidate cache directories were found.
- Cleanup removed **64,466,681 bytes** of owned installer staging, including its ownership marker. The runtime itself remains intentionally installed as the approved trial.
- Final runtime identity: `5bf118330fbb9f3295d65b87473a7e34759a20fde12845796584b9b3de527db0`.
- Installed notice collection covers 54 of 55 distributions. `tensorboard-data-server==0.7.2` lacks an installed notice; a verified upstream notice supplement and distribution review remain open. This is recorded rather than treated as cleared.
- Protected settings/state, all five preceding runtime identities, and the tested GFPGAN/F5 assets passed preservation checks. The rebuilt frontend is recorded by current hashes; it intentionally differs from the previous iteration.

The obsolete, miswired post-processing test was cancelled after the corrected fixture was running. Its exact source manifest and reference path identified only its owned job/request; the request was preserved as diagnostic evidence and removed to trigger the existing session recovery/cancellation path. That worker exited and its workspace was removed. Its failed report is historical evidence and is excluded from successful workflow counts.

The first focused/full diagnostic runs and the intermediate 927-test pass are retained. The final 930-test result covers the production media/process-guard changes; the final focused run also covers the test-environment cleanup correction. No additional dependencies were installed during those repairs.
