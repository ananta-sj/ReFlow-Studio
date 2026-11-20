# Security remediation — November 20, 2026

## What changed

- Updated the desktop filelock/Pillow pins and replaced the vulnerable F5/MuseTalk dependency sets with reviewed Windows x64 CPython 3.11 CPU recipes. These replace coordinated dependency graphs, rather than independently upgrading Torch, TorchAudio and TorchVision.
- Retired the unsafe all-in-one portable AI dependency installer. It now forwards to desktop-only requirements. Desktop integrity repair refuses to install optional engines into the GUI environment.
- Isolated engine preparation checks the interpreter archive identity before extraction and preserves existing profiles. Resume rejects an old or unreviewed bootstrap before package installation. Verification checks actual Python/isolation state and exact dependency inventory before recording readiness.
- F5 uses an explicitly identified, reproducible metadata-only cached_path compatibility wheel so patched filelock can be installed without ignoring dependencies. Upstream executable source and licence files are unchanged.
- Provisioning verifies required FFmpeg shared DLLs and their licence before copying them into the F5 profile. Both inference and readiness checks use that same profile directory.
- F5/MuseTalk no longer fall back to importing their engines in an unreviewed base environment. One-shot and cached speech workers use isolated startup and UTF-8 diagnostics. Session cancellation still targets only the owned process.
- Updated Wav2Lip's declared CPU test stack and replaced removed librosa output APIs with SoundFile.
- Removed 60 unused files from the historical IndicF5 evaluation source copy. The owner-provided CodeQL locations were in this copy: shell-command injection, unrestricted file paths, unsafe checkpoint deserialization, expensive regexes, and a server binding all network interfaces. The live worker uses a separately installed package, not this directory. Its provenance README remains. No scan exclusion was added to conceal these findings.
- Added model-free pull-request checks, with read-only repository permissions and no release publishing or secrets.

## Evidence and limits

- Fresh OSV lookup: 175 exact package/version pairs in the desktop, optional-engine and Wav2Lip manifests returned no advisory records. Ranged/unpinned requirements, historical JSON recipes and existing private environments are outside that result.
- Fresh frontend lockfile audit: zero reported vulnerabilities.
- 35 packaging/bootstrap/compatibility/provisioning tests, 29 preview-publisher tests, 11 integrity/metadata/import-guard tests, 32 desktop readiness/resource tests, 18 runtime-probe tests and 9 actual session-process tests passed. Five focused F5/MuseTalk provider regression tests passed in the isolated model-capable trial.
- The actual trial passed eight base model-free operator/import checks and four F5 checks, including synthetic WAV decoding. No pretrained models were downloaded or loaded for this work.
- Broad mixed-environment test attempts were not fully green: the AI-only trial intentionally lacks desktop pywebview and BasicSR. The relevant bridge tests were run successfully in the desktop environment instead; the full trained face-enhancement path remains untested. These failures were not suppressed or counted as passes.
- A fresh complete installation from the final public F5 recipe has not been performed. The candidate's installed packages/API/operators were exercised, and provisioning was checked with targeted tests. See OPTIONAL_RUNTIME_SECURITY.md for the explicit recipe and limits.
- Existing Chatterbox/Community-1 and other previously installed environments were not upgraded. No claim is made that those private runtime dependencies are vulnerability-free. The original broad root requirements.txt is a legacy description, not a tested secure engine installation recipe.
- BasicSR has no upstream fix for its distributed-training command-injection advisory. The existing exact-source, isolated enhancement guard is an application mitigation; it is not an upstream package patch.

## GitHub follow-up

The owner disabled CodeQL Default setup and enabled the checked-in **CodeQL security analysis** workflow. Its older failed runs remain historical. Push the reviewed source changes to main; inspect the resulting CodeQL and pull-request checks. Compare findings against the new commit and configuration. An obsolete default-setup configuration can retain stale alerts; do not dismiss live findings merely to clear the dashboard.

**Do not bulk-approve the existing dependency PRs.** The separate Torch/TorchVision proposals are superseded by coordinated profile updates after this source is pushed. Frontend and Actions major-version proposals require their own compatibility checks; the zero-vulnerability frontend audit does not make a major-version update automatically safe. No PR was approved, merged or closed, and no branch was deleted by this work.

These changes reduce identified risks. They are not a guarantee of vulnerability-free software, trained dubbing quality, GPU qualification or release readiness.


## Follow-up after the first security push

Commit `79792a3` completed both the main-branch CodeQL workflow and desktop build successfully. The owner then supplied one new CodeQL finding, #42, concerning a filesystem check/read race in the release publisher. The publisher now opens package/checksum files first, validates the opened descriptors, and reads/hashes those same descriptors. Upload size and stream also use one descriptor. Checksum reads are bounded, descriptor cleanup covers failures, and nonblocking open prevents a FIFO input hanging the Linux publisher.

The follow-up publisher/version tests passed 32 cases on Windows. One additional FIFO regression applies only to POSIX platforms and is deferred to Linux CI, rather than reported as a local pass. A new hosted CodeQL scan must confirm resolution of #42 after this follow-up is pushed.

GitHub's exported dependency graph already contains the updated package versions. Public GitHub advisory queries for Pillow 13.0.0, Torch 2.15.0 and OpenCV 4.11.0.86 returned no matches. The owner-provided details for Dependabot #89 state affected Pillow versions `>=11.0.0,<13.0.0` and patched version `13.0.0`, which is already committed on main. That particular alert is inconsistent with the current source requirement and should be rechecked after dependency-graph refresh. This does not establish the status of all remaining alerts; none were manually dismissed.

The public PR list currently contains 13 open proposals. Five obsolete coordinated-stack update PRs were closed without merging after the preceding source update. This follow-up does not approve, merge, close or delete any further PR or branch.
