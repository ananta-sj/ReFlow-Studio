# IndicF5 evaluation paused at the user's request

> Historical report: the unused `dev/vendor/IndicF5` executable source copy was removed in the 2026-11-20 security review. See its retained provenance README. This report does not qualify current dependencies.

The user requested: “stop for now... i will ask u to continue later on”.
No continuation or background monitoring is authorized until that request.
The download session was interrupted and ended with exit code 1. The isolated
environment verifier had completed with exit code 0. No smoke synthesis was
started. No known ongoing evaluation session remains.

## Preserved state

- Official source: `dev/vendor/IndicF5`, commit
  `13f7c4d627cc10111aea8fe9c0039462cacacdc7`.
- Isolated runtime: `runtime_profiles/indicf5-evaluation`.
- Existing generic F5 remains version 1.1.22; the isolated IndicF5 package is 0.1.0.
- Dependency copy completed in 832.656 seconds. Missing declared dependency
  jieba 0.42.1 was installed only into the new profile.
- Initial legacy package installation failed; the successful retry used wheel
  0.45.1 from a workspace-only temporary build directory. Failure logs retained.
- Hugging Face access was confirmed after the user's local login. Credentials
  are kept under the ignored evaluation auth directory; never print or include
  them in diagnostics, handoffs or commits.
- Official model revision: `ba85abedf18dc479a447eaa0eccbd76ab78a47d5`.
- Small files were downloaded and hashed. A partial weight download is retained;
  inspect actual files and the download receipt on resume rather than assuming
  completion. Expected weight size is 1,402,789,408 bytes.
- Checkpoint header inspection found 447 tensors in `ema_model` and `vocoder`
  namespaces with compilation-wrapper prefixes. That inspection did not load
  trained weights or establish complete download integrity.
- Production app/voice settings were not changed. No new listening acceptance,
  complete video result, commit, push or release.

## Resume only when requested

1. Read `docs/validation/2026-10-06-indicf5-environment.json` and related logs to
   confirm the completed import/dependency/small-forward checks. These do not
   prove trained speech generation.
2. Inspect the current pinned assets and interrupted download receipts/log. Use
   `dev/download_indicf5_evaluation.py` to resume incomplete official assets.
   It writes a distinct receipt and executes no model code.
3. Verify all trained model/vocoder weights load strictly. The prepared
   `dev/verify_indicf5_smoke.py` uses local weights and existing Vocos config,
   strips only known compilation namespace prefixes, and avoids automatic
   downloads/compilation. It has not been executed or validated yet.
4. First smoke uses the documented Punjabi female reference prompt to speak the
   failing Hindi line. This is not Sujata/Abhishek identity acceptance. Review
   reference transcript/loader behavior and record all evidence.
5. Then test the user's voices with correctly matched reference transcripts,
   broader Hindi passages and listening checkpoints. Do not integrate on the
   basis of import success, a small untrained forward or a duration measurement.

Earlier Hindi failures and accepted controls remain documented in
`docs/HINDI_GENERATION_INVESTIGATION_2026-10-06.md` and
`docs/CURRENT_VIDEO_CUE_RETEST_2026-10-06.md`. Full-video work remains unvalidated.

## Resume update — October 6

The user requested continuation. The pinned download completed successfully;
`docs/validation/2026-10-06-indicf5-download-26415d3e.json` records the exact
asset sizes and checksums. Model weights and reference audio match the official
LFS checksums. No manual partial-file recovery was needed.

The first trained speech test is running through
`dev/verify_indicf5_smoke.py`, with its output in
`docs/validation/2026-10-06-indicf5-smoke.log`. All 364 speech-model tensors and
83 vocoder tensors loaded strictly. The documented reference is 8.1 seconds;
the test supplies the Hindi sentence directly, without recognition or
translation. Generation progress has been observed, but no final recording or
listening acceptance exists at this checkpoint. Inspect the eventual unique
smoke-test receipt before claiming success. Production settings remain unchanged.

The user also requested a complete explanation of language rollout and NLLB.
`docs/LANGUAGE_PLAN_AND_NLLB_2026-10-06.md` explains the separate recognition,
translation, speech and assembly stages. English-to-Hindi is the first complete
workflow acceptance target; arbitrary source languages and other target
languages are not yet certified. NLLB already serves the tested local
translation route and cannot repair a speech-only failure.

### Completed first inference

The previously running smoke test completed with exit code 0. Receipt
`docs/validation/2026-10-06-indicf5-smoke-7db43633.json` records the 1.877333-second
output, complete decoding checks and 695.515-second total runtime. Evidence is
published under `docs/validation/2026-10-06-indicf5-smoke-63f2b94c`.
`docs/INDICF5_EVALUATION_2026-10-06.md` documents setup, exact scope, preparation,
performance and remaining gates. Human quality review is pending; there is no
production integration or validated full video. The inference session has
finished, and its owned temporary workspace was removed.

### Later GPU checkpoint

The official-reference smoke passed listening. Confirmed user-reference pairs
were prepared; the CPU generated voices still needed delivery improvements.
The user approved separate GPU packages, whose checksums, dependencies and CUDA
operations were verified. The GPU voice sweep completed and the user preferred
C for both. Longer selected-settings recordings completed technically and now
await listening. See `docs/INDICF5_GPU_ITERATION_2026-10-06.md` and the latest
sections of `docs/HANDOFF_FULL_VIDEO_VALIDATION_2026-10-04.md`; do not resume the
historical interrupted download or repeat already completed installation.
All iteration background sessions have finished. Production integration and
complete-video acceptance remain outstanding.
