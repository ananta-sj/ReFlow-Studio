# Stronger recognition, sentence review and video export — 8 October 2026

## Outcome and scope

The existing Whisper large-v3-turbo installation is now an explicitly selectable recognition provider in the app. A live test recognized the entire 122.532-second `Sample/2.mp4`, grouped its timestamped fragments into 14 cues and translated every cue with the installed IndicTrans2 provider. Recognition and translation workers were released between stages. No model, package, framework or runtime was installed in this iteration.

Reviewed video export now works through the existing cue-review operation. The full-source export comparison uses 13 previously accepted Hindi takes, their accepted spoken wording/timeline and the previously generated background stem. It removes an invented final “Thank you” over digital silence. This comparison does **not** represent fresh TTS generation or fully automatic wording adaptation. The fresh machine transcript and translations remain untouched in a separate review.

The main unresolved quality issue is measurable: **only 3 of the 14 fresh raw translations fit the native IndicF5 speech windows** at the accepted voice calibration. Eleven need wording or timing review. Changing recognizers does not solve translation verbosity by itself. Release approval is still absent.

## Existing assets and runtime contract

Recognition uses the existing `models/f5/reference-asr` checkpoint, identified as `openai/whisper-large-v3-turbo`, revision `41f01f3fe87f28c78e2fbf8b568835947dd65ed9`. The checkpoint remains at its existing path; the directory name does not make this an F5 speech generator.

`dev/pin_installed_whisper_turbo.py` verified all 12 installed files against previously captured upstream repository metadata. It checked exact upstream sizes, the large safetensors file against its upstream LFS SHA-256 and smaller files against Git blob identities. It then wrote `core/whisper_turbo_manifest.json` with exact local SHA-256 values. The safetensors file is 1,617,824,864 bytes, SHA-256 `542566a422ae4f3fd23f1ba11add198fca01bbf82e66e6a2857b3f608b1eb9d1`.

Recognition reuses `runtime_profiles/indicf5-gpu-evaluation/python.exe`, with verified PyTorch `2.9.1+cu128`, Transformers `5.18.0` and the first NVIDIA GPU. The successful live run reported `torch.float16`; the code records the actual model dtype. It does not require replacing the core portable Python or converting this checkpoint into CTranslate2 format. GPU availability and runtime versions are checked by the worker. Local-only loading and safetensors are used without remote model code.

IndicTrans2 remains a translation engine. IndicF5 remains the Hindi speech engine. This iteration does not change either accepted voice profile, calibration, seed, sampling steps, guidance, sentence gap or playback speed.

## Implementation changes

### Recognition provider and lifecycle

- `core/whisper_turbo_assets.py` validates the installed pinned assets and locates the existing GPU interpreter. Small files are hashed during validation; complete weight hashing is performed before worker model loading.
- `core/providers/stt/whisper_turbo_local.py` implements the separate `whisper_turbo` provider, preserves language metadata, checks media bounds and closes its feature session in `finally` before returning recognition results. Direct calls own and clean their job context.
- `core/whisper_turbo_worker.py` decodes mono 16 kHz audio using existing FFmpeg and recognizes 30-second blocks. It retains decoded text, timestamp offsets, block language evidence, model revision, dtype and decoder completion evidence. It checks cancellation between work and during decoding/model calls.
- `core/model_contract.py` recognizes the pinned checkpoint contract instead of mistakenly requiring a faster-whisper `model.bin`.
- `core/providers/resolve.py` routes the selected preset to the new provider. It does not silently substitute the small recognizer or a CPU route.
- `core/runtime_checks.py` checks the isolated runtime for this preset rather than requiring faster-whisper in the core interpreter.

The recognizer skips blocks containing exactly digital zero samples. This prevented the older transcript's invented final line on this source. It is **not** a general voice activity detector or a guarantee against hallucinations in quiet, noisy or musical sections.

Language confidence is the minimum masked language-token probability across spoken blocks, provided every spoken block agrees on the language. The run reported English with probability `0.9997343420982361`. This measures the model's language choice, not word correctness or calibrated transcription accuracy. Mixed block languages retain unknown aggregate language metadata rather than inventing certainty.

### Sentence grouping

`core/sentence_grouping.py` groups unfinished timestamp fragments until terminal punctuation, subject to a 30-second span, 0.6-second gap, 1,500-character limit and matching speaker identity. It preserves original fragments as provenance. Complete short sentences remain independent cues. A conservative English block-boundary rule can join a lowercase continuation after conjunction punctuation while recording that punctuation adjustment.

`core/pipeline.py` applies this grouping only to a provider opting into it and a single-voice workflow. Other providers and multi-voice behavior retain their previous grouping route. Limits deliberately take precedence over attempting semantic reconstruction; a real pause or length limit can still split an unfinished sentence. This happened near 81.82–82.50 seconds in the live source.

Newly prepared review manifests retain the complete transcription payload under `recognition`. The successful preparation below started before that manifest addition and video snapshot code were loaded; its receipt still contains the complete recognition result. The separately constructed video comparison explicitly retains that fresh recognition payload.

### App connection and resource estimates

`bridge/api.py` exposes installed-recognizer status and an idempotent connection action under the existing busy lock. Connecting preserves the current active recognizer. Setting the stronger entry active is a separate explicit action and rechecks the runtime.

`frontend/src/pages/Marketplace.tsx` adds a stronger-recognition card in the recognition tab; `frontend/src/lib/api.ts` exposes the matching typed API. This card connects existing files. It is not a download/install button.

The estimate routes this selected recognition stage to `cuda:0`, including when the workspace's general compute setting is CPU. It also warns that startup, speed and memory estimates for this route are not calibrated. No unsupported throughput benchmark or GPU parallelism guarantee is introduced. GPU-heavy stages remain sequentially released in this tested workflow.

Persistent registry settings were not changed by the live diagnostics. They used isolated selection records with real providers, not transcript or translation fixtures.

### Durable reviewed video export

Previously `core/cue_review.py` assembled accepted audio only. It now supports a source video snapshot when review preparation requests `review_video`. Preparation confirms a real video stream with existing ffprobe, copies the source into owned durable review storage and records its hash.

The bridge requests this for recognized video extensions. The review panel identifies audio versus video output and labels the final action accordingly. Existing saved audio-only reviews keep their original export route.

Rendering verifies that every accepted take fits, verifies take hashes, verifies any saved background and verifies the source video hash. It assembles accepted speech without regenerating it, writes subtitles and uses existing `merge_av` to produce a unique staged MP4. Before publication it requires video, audio and subtitle streams and a duration within 150 ms of the saved source. Failed muxing publishes no final video and leaves the accepted review intact.

The asset path guard was extended narrowly: WAV assets retain the existing rule, and video access permits only the recorded `source-video` filename with a supported extension. Traversal, arbitrary paths and reparse-point protections remain in place.

`core/pipeline.py::merge_av` now accepts subtitle-language metadata. Hindi exports use `hin`, English uses `eng`, and other currently unmapped cases use `und`. Previously Hindi subtitles were labelled English. The existing accepted video was not modified; the new video has the corrected tag. Mapping all additional language tags remains future work.

## Failures encountered and corrected

The first strong recognition test failed because the initial completion guard expected EOS at the end of Whisper's postprocessed timestamp sequence. The installed Transformers implementation strips this marker during timestamp processing. Valid output was therefore incorrectly rejected.

The repair requests the structured generation result and validates the underlying decoder output and actual generated-step count, before timestamp postprocessing. `core/whisper_completion.py` rejects missing completion evidence, missing underlying EOS and reaching the 440-token generation limit. Regression tests cover valid completion and rejection cases.

The failed preparation receipt `2026-10-08-strong-whisper-app-review-f5a0695f.json` and `2026-10-08-strong-whisper-eos-check-failure.log` preserve the failure evidence. The succeeding full run confirms the repaired check operates with real model output.

The first reviewed-export diagnostic invocation used the accepted output's receipt-relative path as a project-relative path and failed before creating a review. That diagnostic path resolution was corrected to use the receipt's recorded artifact directory. This did not modify the accepted output.

## Live results and honest comparison

`docs/validation/2026-10-08-strong-whisper-app-review-9ad56e5a.json` records successful full-source recognition and all 14 live IndicTrans2 translations. It records recognition worker release before translation, translation worker release before speech, source preservation and cleaned temporary workspaces. No new TTS was run in that preparation-only test.

The first ten recognized cue texts and boundaries match the prior accepted draft's source cues. Later indices differ because a 0.68-second pause split a passage, some boundaries moved by 20 ms, and the digitally silent final block generated no speech. Equal cue counts therefore do not establish equal cue identities. Accepted takes must not be reused merely by index against the fresh timeline.

The model still repeats some questionable source wording, including “walkie-talkie preamble” and “auteur.” Its high English language score does not settle those words. This iteration establishes the installed stronger route and provenance, rather than claiming flawless recognition or a head-to-head accuracy victory.

`dev/audit_strong_whisper_review.py` applies the existing native IndicF5 duration estimator to every fresh translated cue without generating audio or loading AI weights. `2026-10-08-strong-whisper-native-fit-audit.json` retains each raw translation, source window, predicted native duration and fit decision. Only 3/14 fit. The estimator uses the unchanged confirmed Abhishek profile; it does not shorten text, speed audio or claim human-quality acceptance.

### Full video comparison and provenance

`dev/verify_strong_whisper_review_video.py` creates a **separate diagnostic review**. Before import it verifies the source hash, accepted render receipt hash, spoken draft hash and accepted MP4 hash against `2026-10-08-full-video-user-acceptance.json`. Every reused take is checked against its original recorded synthesis-output hash. It retains the accepted timeline and spoken wording for the first 13 cues, excluding the final invented “Thank you.” It verifies and reuses the same previously generated background stem.

This diagnostic timeline/wording import is explicit editorial fixture use. It is not an automatic app operation for correcting raw machine translation, nor evidence that the app can align arbitrary old takes to a new transcript. The fresh raw review remains unchanged. No fresh separation or fresh speech generation is implied by this export.

Successful export receipt: `docs/validation/2026-10-08-reviewed-strong-whisper-video-2f75ebb6.json`.

Output: `docs/validation/2026-10-08-reviewed-strong-whisper-video-2f75ebb6/REVIEWED_VIDEO_ba872b047e46.mp4`.

Output SHA-256: `370832d3c33de5394638106e5fe5c83249a5295de58eaf94a9ba44fd233b8ec0`.

Duration: **122.531995 seconds**. Video/audio/subtitle streams are present; subtitle language is `hin`; full FFmpeg decode passed. The source and original accepted video remain unchanged, and the temporary render workspace was removed. The new comparison has not yet received human acceptance. Background separation quality and absolute absence of English bleed cannot be established solely by these structural checks.

## Verification

`docs/validation/2026-10-08-strong-whisper-final-tests.log`: **137 tests passed** in 55.387 seconds across stronger-recognizer integration, transcription metadata, IndicTrans2 integration, cue review, output integrity and architecture contracts.

Coverage includes distinct provider resolution, worker release on success/failure, metadata preservation, sentence/provenance limits, installed connection behavior, CPU-workspace GPU routing, bounded timestamp correction, accepted-take persistence, stale revisions, path rejection, real video muxing, Hindi subtitle tags, source tampering, failed mux preservation and audio-review compatibility. Synthetic audio in unit tests verifies storage/mux contracts; it is not used to claim real voice quality.

`docs/validation/2026-10-08-strong-whisper-final-frontend-build.log`: production frontend build passed in 3.45 seconds. The pre-existing large-chunk warning remains; it is not a build failure. The live export additionally validates the full 122-second source rather than relying solely on the small synthetic mux test.

## Remaining work and release boundary

Initial user comparison: **“previous one was better.”** The user then clarified that the new version's quality was actually better, except that speech appeared ahead of picture around 1:30 or slightly earlier. The new export remains unapproved as a replacement pending timing review. Neither existing video was changed. The feedback and clarification are retained in `docs/validation/2026-10-08-reviewed-video-user-comparison.json`; diagnosis and focused comparison are documented in `REVIEW_VIDEO_PHRASE_SYNC_2026-10-08.md`.

1. Add a clear normal-review preview of native speech duration before generation, exposing the eleven raw-translation overflow cases to the user.
2. Implement and evaluate source-faithful spoken Hindi adaptation or review assistance. Keep raw translation and edits separately; avoid solving verbosity with clipped words or blanket speed increases. No extra model/framework should be added without the user's approval.
3. Make timeline grouping/correction available as a normal reviewed operation. The explicit diagnostic import used here is not a substitute for that UI.
4. Audit difficult source wording, quiet audio, mixed languages, long statements, multiple speakers and noisy/music-heavy videos with independent examples. One source does not establish general recognition or dubbing quality.
5. Review this new video's ending and mix. Existing human approval covers the prior full-video baseline, not this newly exported file or release readiness.
6. Validate fresh-machine provisioning and packaging of the optional GPU recognizer/IndicTrans2/IndicF5 routes. Current installed-machine success does not prove all Windows, Linux and macOS distributions work. The current recognition route requires the existing verified NVIDIA runtime.
7. Continue the broader feature/release audit, including language-tag mappings, resource calibration, cancellation of live GPU work and longer multi-speaker workflows. This iteration's checks are not a blanket sign-off on all project features.

No caches or user media were deleted, no existing accepted artifact was overwritten, no persistent default provider was switched, and no commit or push was performed in this iteration.
