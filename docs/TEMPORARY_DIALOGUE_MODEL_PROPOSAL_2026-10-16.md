# Temporary dialogue-model evaluation proposal — 2026-10-16

Status: **owner approved this temporary evaluation and verified cleanup on 2026-10-16**. The original proposal was prepared with metadata queries only; executable/model payload work began after that approval. Execution evidence and remaining limits are documented in `TEMPORARY_DIALOGUE_MODEL_EVALUATION_2026-10-16.md`. The scope below remains the approved boundary.

## Purpose and pipeline position

Test whether a small local instruction model can propose shorter spoken wording when a measured TTS take exceeds a cue's real video window. This belongs between translation/dialogue review and TTS. Whisper still recognizes speech, the selected translator still translates, and XTTS/IndicF5 still generates audio. The instruction model edits text; it cannot preserve background audio, certify pronunciation, or prove synchronization.

The present English diagnostic is 10.209 seconds before fitting and 7.853 seconds after the existing 1.3× acceleration limit, against a six-second window. The problem cannot be solved by removing its 0.417 seconds of exact trailing silence. See `SPEECH_TIMING_REPAIR_2026-10-16.md` and `validation/2026-10-16-speech-overflow-diagnosis.json`.

The input ends with “recognizable to any”, so it is an incomplete sentence. Recover and verify adjacent source context before requesting a meaning-preserving rewrite. Keep the actual six-second cue boundary fixed. If complete meaning cannot be established or retained inside that window, the correct outcome is review-required, not an invented completion or a forced successful render.

## Why this candidate, and what the earlier trial taught us

Propose **Qwen3-4B-Instruct-2507, Q4_K_M**, served by standalone **Ollama v0.40.5**. The official model card describes an instruction model with non-thinking output and multilingual capabilities; those general capabilities do not establish Hindi dialogue quality. Its size makes a bounded experiment practical. This is a comparison against the previously tested weights, not a claim that this is the best available model. A larger or different model would require a separate proposal.

The October 12 trial used these same model weights with Ollama v0.40.3. Its receipt says `completed=false`: the first case timed out at 60 seconds; the second returned a shorter candidate that the reviewer judged meaning-changing; the incomplete-context case produced no fitting candidate. Therefore it is inaccurate to call the prior evaluation successful. The cleanup audit did pass and recorded 5,965,218,657 bytes removed.

This experiment differs by verifying complete context, explicitly testing the measured English/XTTS route, separating cold loading from request latency, and measuring synthesized candidates. Reusing the model gives a controlled comparison; the runtime patch change remains a recorded variable. No model improvement is presumed.

Prior evidence: `validation/2026-10-12-ollama-eval-c_lslq8w.json` and its `-cleanup.json`; implementation references: `dev/evaluate_temporary_ollama.py`, `dev/cleanup_temporary_ollama.py`, and `dev/verify_temporary_ollama_cleanup.py`. Review these scripts before reuse; the old evaluator follows the latest release dynamically and is unsuitable unchanged for this pinned proposal.

## Exact proposed downloads

Official metadata was checked on October 16. The receipt is `validation/2026-10-16-temporary-dialogue-model-proposal-metadata.json`.

| Component | Pinned identity | Payload |
| --- | --- | ---: |
| Standalone Windows x64 Ollama ZIP | v0.40.5 | 1,471,226,485 bytes |
| Qwen model, template, license and configuration | `qwen3:4b-instruct-2507-q4_K_M` | 2,497,293,803 bytes |
| Combined archive and model payload | Excludes small metadata/HTTP overhead | 3,968,520,288 bytes, approximately 3.97 GB / 3.70 GiB |

Runtime download: https://github.com/ollama/ollama/releases/download/v0.40.5/ollama-windows-amd64.zip

Runtime ZIP SHA-256: `5134ce7e3bc8e94d0494721c799ec293b429450d0c52461b0ee3647dd3bb4bb7`.

Model manifest SHA-256: `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`.

Weight layer SHA-256: `85e4a5b7b8ef0e48af0e8658f5aaab9c2324c76c1641493f4d1e25fce54b18b9`.

Check the manifest identity before pulling weights, archive hash before extraction, safe archive paths, downloaded model identity and individual layer hashes. Stop on any mismatch; do not silently follow a changed tag or release. Record actual bytes, versions and executable identities.

Budget **10 GiB free disk** before starting for the archive, extracted libraries, model, partial-download staging and test artifacts. This is a conservative planning allowance; actual extracted v0.40.5 storage is not measured yet. Record peak storage and bytes removed. No pip packages, new Python environment, CUDA toolkit, GPU driver, Windows installer, service, PATH edit or startup item is proposed.

Previous 4,096-token evaluation reported 3,178,149,969 bytes of GPU model allocation. This is historical model allocation, not total GPU usage or a guarantee for the new runtime. Plan roughly 4–6 GiB available VRAM and 6–10 GiB available system memory as unverified allowances; measure before and during execution. Run one request at a time, one loaded model, 4,096-token context. Unload the instruction model before GPU TTS where necessary. Reuse the existing driver and bundled Ollama libraries; record CPU fallback rather than installing support software. Stop on resource pressure or unsupported hardware.

## Application work required before live evaluation

Installing Ollama alone is insufficient. `core/providers/dialogue_chat.py` currently hard-codes English-to-Hindi prompts. `core/dialogue_supervision.py` accepts only that pair and requires a native-delivery duration estimator. The dense English/XTTS case meets neither contract.

Prepare a bounded, explicit measured-overflow review path alongside the established Hindi estimator path:

1. Pass validated source/target language labels into prompts; initially support only the tested English-to-English and English-to-Hindi pairs. Reject unsupported pairs. Preserve current Hindi behavior and tests.
2. Accept a timing conflict bound to source/cue hashes, transcript revision, TTS provider/reference identity, actual available seconds, measured duration, and fitting policy. Invalidate proposals when any binding changes.
3. Keep measured duration separate from prediction. XTTS has no established native duration estimator here. Text-length ratios may help rank candidates but must never create a verified-fit status or suppress the need to synthesize.
4. Reuse the existing local OpenAI-compatible connection and bounded JSON validation. Test with a disposable registry/settings snapshot; leave saved user settings and normal rendering defaults unchanged.
5. Keep proposals advisory and require explicit selection before applying wording. Same-model writer and reviewer are correlated opinions, not independent meaning verification. Preserve original wording and make failed/uncertain proposals inspectable.

These are proposed changes, not completed functionality. Implement and exercise deterministic fixtures before downloading the runtime. Do not remove existing fail-closed timing checks, accelerate beyond established limits, truncate words, extend the source video, or automatically enable dialogue rewriting.

## Isolation, privacy and request budget

Create a uniquely marked `temp/ollama-eval-*` workspace. Place runtime, model cache, temporary home, application-data directories, scratch files, CUDA cache and logs inside it using child-process environment variables only. Bind the owned server to a free `127.0.0.1` port; verify PID/port ownership and startup identity before sending text. Do not reuse an existing server. No sign-in, cloud model, web search or exposed LAN endpoint is proposed. Set `OLLAMA_NO_CLOUD=1`, verify the server reports cloud disabled, and route loopback traffic without a proxy.

Download requests necessarily contact upstream services. Inference uses the local model; inspect owned-process connections during inference and report the limits of that observation. It is not a proof of every packet on the computer. Send only selected test text/context, never credentials, full project directories or unrelated media. No paid API calls or external text-review service.

One explicit warm-up with a 180-second deadline; then retain the existing 60-second dialogue request limit. A timeout is a failed case, not grounds for an unlimited retry. At most eight live text cases, one writer request and one batch critic request per case, at most three candidates each: **16 dialogue requests maximum**, plus one warm-up. No tools or shell execution are offered to the model. Incomplete/malformed JSON, wrong IDs, excessive candidates and output-limit failures remain errors. Total live text phase bounded to 25 minutes, excluding downloads. Download phase bounded to 30 minutes with explicit connect/read deadlines and progress; stop and clean partial payloads on expiry. No automatic second model.

## Acceptance matrix

| Check | Evidence required |
| --- | --- |
| Existing Hindi behavior | Focused regression suite preserves language, duration prediction, consent, cancellation and stale-result guards |
| New measured English path | Tests distinguish measured overflow, unmeasured alternatives and actual fitting; reject stale cue/audio/configuration bindings |
| Dense English cue | Verified complete source context; original six-second window and original measured take retained; up to three proposals, no invented ending |
| Two Hindi dialogue cases | Revisit the earlier complete opening and establishing-shot cases with source context; report naturalness/meaning concerns rather than assuming success |
| Names, numbers and negation | Separate English and Hindi fixtures retain explicit names/quantities/negation; include deliberately changed candidates that must remain blocked |
| Quoted hostile text | Embedded instructions are treated as dialogue data; no tool/action capability; inspect actual output for instruction following failures |
| Impossible/incomplete target | Very short budget and missing-context cases return no acceptable proposal or remain review-required; never delete a claim to obtain a pass |
| Service failures | Deterministic invalid JSON, wrong language, timeout, cancellation, disconnection and changed connection tests; no fallback to a remote provider |
| Actual speech timing | At most six candidate syntheses total using existing approved engines/assets; no iterative unlimited regeneration; report raw/fitted durations and speed with full words retained |
| Application integration | Exercise the explicit action through the real application bridge with a disposable session; model suggestions do not silently replace the transcript |
| Cleanup and preservation | Owned processes stopped; temporary runtime, archive, weights, generated keys, caches and staging absent; existing state and runtime identities preserved |

The eight text cases are: one dense English, two complete Hindi, two names/numbers/negation (one per target), one hostile-quoted-text, one impossible-time, and one incomplete-context. Negative response handling uses deterministic fixtures rather than extra live requests.

Record model/runtime identity, prompts, inputs and their provenance, bounded responses, timings, hardware allocation, all rejected variants and reasons, source hashes and final selection status. Existing XTTS/IndicF5 references, models and seeds/settings must be explicit. Six TTS calls are a ceiling, not a quota: synthesize only semantically plausible candidates. Run speech sequentially after unloading Ollama when resource contention warrants it. Bound each speech operation to ten minutes and the combined synthesis phase to one hour, with cancellation and cleanup.

A fitting waveform is a timing result, not proof of natural delivery or faithful meaning. Ask the owner to review only a small final comparison if a candidate passes objective checks. Technical completion can be reported without human acceptance; do not label the dialogue quality approved or the application release-ready before the relevant review and remaining release gates. If all candidates fail, retain the diagnosis and review-required outcome and remove the model anyway.

## Removal on success, failure, cancellation or interruption

Capture before/after hashes for `settings.json`, `models.json`, `graph.json`, `ui_preferences.json` and `hardware_profile.json`; record the six established runtime identities. Record existence/metadata of normal Ollama locations, relevant startup entries, user/system PATH and Ollama environment values without printing secret values. Existing Ollama installations or user model stores, if present, are never cleanup targets.

Write the ownership marker and process/command-line receipt before launch. Put cleanup in a `finally` block plus a separate recovery command for an interrupted host. Stop only processes whose creation identity, executable/command line and ancestry belong to the owned evaluation, then confirm the port is no longer owned by that server. Verify the resolved cleanup root is under workspace `temp`, marker matches, and there are no symlinks/junctions/reparse points before recursive removal. If ownership cannot be proven, refuse deletion and report the exact remaining path; never broaden deletion to the user's profile.

Delete the owned runtime, ZIP, model blobs/manifests, partial downloads, temporary keys, scratch, caches and logs on every outcome. Retain only bounded sanitized reports, selected review media and implementation/test changes in documented project locations. Verify cleanup immediately after the test phase and before waiting for a listening review; selected media remains playable without Ollama. Audit process absence, released endpoint, unchanged external locations/state and actual removed byte counts. If a process still holds a file, perform only bounded owned-process cleanup retries and report any residue explicitly.

Removal is mandatory even if the model works well. Product support continues through user-configured local/API connections. Bundling this runtime/model, leaving it installed, switching defaults, or testing another model is outside this proposal.

## Sources and licensing

- [Ollama v0.40.5 release](https://github.com/ollama/ollama/releases/tag/v0.40.5) and the official GitHub release API provide the archive identity. Current patch observed: v0.40.5; previous local evaluation: v0.40.3. New runtime behavior must be validated, and this proposal is not a security certification.
- [Ollama Windows documentation](https://docs.ollama.com/windows) describes the standalone CLI and GPU libraries. No separate GPU support download is included here.
- [Ollama FAQ](https://docs.ollama.com/faq) documents local cloud-disable and resource controls. These settings must be verified in this pinned build.
- [Ollama model tag](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M) and official registry manifest identify the quantized artifact; exact layer sizes/digests are in the metadata receipt.
- [Qwen model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) identifies Apache-2.0 for the upstream model; [Ollama license](https://github.com/ollama/ollama/blob/main/LICENSE) identifies MIT for Ollama's code. Bundled components have their own notices. Inspect and retain evaluation license evidence with the receipt. This does not decide the owner's Reflow license or clear all distribution rights.

## Approval requested

Approve this single temporary Ollama v0.40.5 + pinned Qwen3 4B evaluation, approximately 3.97 GB of payload downloads and a 10 GiB free-space allowance, including the bounded application changes, tests, existing-engine speech measurements and mandatory verified removal. Until approval, only the proposal and its metadata receipt are prepared; no model/runtime payload was downloaded and no application code or defaults were changed by this proposal step.
