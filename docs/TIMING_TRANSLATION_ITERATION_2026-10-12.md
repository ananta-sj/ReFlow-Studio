# Timing-aware translation and video review — 12 October 2026

## Outcome

The installed IndicTrans2 alternatives were evaluated against the exact overflowing real cue from the previous live pipeline test. Two distinct alternatives were retained, predicted at **10.027** and **10.304 seconds** against **8.000 seconds** available. Neither fits. No candidate was applied, no new speech was generated, and no automatic shortening success is claimed.

Dashboard now exposes the existing line-review workspace for the standard video-dubbing template, as well as audio dubbing. Users can prepare video dialogue, inspect source/translation, check native speech timing, request installed-translator alternatives, edit wording, audition takes, approve them and export the reviewed video. The existing backend already supports retaining source video and rendering accepted review takes; this iteration connects that capability to Dashboard rather than adding another review engine.

Automatic meaning-preserving shortening remains open. The existing writer/reviewer connection infrastructure is present, but no instruction model or paid service was added or invoked. A candidate that fits the duration estimate still needs meaning and delivery review.

## Changes

`frontend/src/pages/Dashboard.tsx` shows `CueReviewPanel` for audio input or a video input using `video_dub`. The existing selected input and render parameters are forwarded. An active job's filename is not substituted for the next selected video. Subtitle-only input and the separate lip-sync template do not newly expose this review route.

The panel's existing actions remain explicit: preparing a review starts preprocessing/recognition/translation; requesting alternatives invokes the selected translator; generating/accepting speech requires separate actions. Mounting the panel does not start inference. Reviewed export uses the saved source visuals and accepted single-voice takes, rather than executing the ordinary render's optional visual stages. Existing saved-review configuration checks and busy/dirty guards remain in force.

`dev/verify_dashboard_input.cjs` adds actual-component checks for video review input identity and preservation of audio/subtitle routing. Prior Dashboard-only receipts/logs were copied to `*-before-video-review` before the expanded verifier ran.

`dev/verify_dense_dialogue_options.py` validates the original retained cue artifact hash, resolves the currently installed selected IndicTrans2/IndicF5 adapters, measures the original duration, makes one bounded request for at most three alternatives and estimates each distinct alternative. It uses offline flags and records worker diagnostics, cleanup, input identity and five saved-state hashes. Only the real ASR/raw translation evidence is reused; the alternative request is fresh. No TTS inference, source rewrite or final render occurs.

## Live evaluation

The original cue is from `Sample/2.mp4`, 16–24 seconds, retained in run `2026-10-12-live-workflow-7e72844c`. Its predicted native duration is **10.026666… seconds**. The installed alternative recipe is deterministic beam search with five beams and length penalty zero; it is a translation-variant generator, not an instruction-following localization writer.

The worker returned three complete decoded candidates. The proposal layer removes candidates identical to the existing text and duplicates, leaving two distinct options. Their measured predictions were 10.026666… and 10.304 seconds. Both retain `approved: false`, and the report explicitly says meaning is not assessed and human review is required.

The excerpt starts and ends inside a longer sentence. Its preserved cue carries `incomplete_sentence_tail: true`. Standalone shortening of this fragment cannot establish fidelity to the full utterance. A future writer evaluation should include complete sentence context and representative dense cues, rather than treating this cropped phrase as the sole benchmark.

The request completed in **44.297 seconds**. Its owned workspace was removed, the translator session was released, and the source artifact and saved app state remained unchanged. [Live evaluation receipt](validation/2026-10-12-dense-options-072f2715.json), [execution log](validation/2026-10-12-dense-options-execution.log), and the retained `translation-worker.log` inside that evaluation folder contain the observations.

## Validation and limits

Six Dashboard component contracts passed, including different active/pending sources, stopping/finished labels, browse behavior, video review routing and audio/subtitle routing. Production build and lint passed; existing bundle/hook/fast-refresh warnings remain.

Eighty-nine focused backend tests across dialogue adaptation, supervision, connection handling and cue review passed in **22.877 seconds**. An initial sandboxed attempt failed because local HTTP fixture sockets were blocked and a redirected Windows stream used CP1252. A second diagnostic attempt additionally used an unwritable system temporary location. These were harness/environment failures. The successful run used UTF-8, the workspace test temp directory and approved execution for local loopback fixtures; no real external writer/reviewer service or paid call was made. The failed redirected log and final log are retained.

Six final evidence-integrity checks passed. Five saved state files and the exact user-accepted Hindi video remain unchanged. Among sources recorded by the preceding full backend validation, only Dashboard changed in production; the full 763-test suite was not rerun here. Native layout and live video-review preparation/export were not repeated in this iteration. Existing backend review tests establish the reviewed-video behavior; these are not new human quality acceptance.

Evidence:

- [Dashboard contracts](validation/2026-10-12-dashboard-input-contracts.json)
- [Contract log](validation/2026-10-12-video-review-contracts.log)
- [Build log](validation/2026-10-12-video-review-build.log)
- [Lint log](validation/2026-10-12-video-review-lint.log)
- [Initial focused-test log](validation/2026-10-12-video-review-backend-focused.log)
- [Final focused-test log](validation/2026-10-12-video-review-backend-final.log)
- [Final integrity](validation/2026-10-12-video-review-integrity.json)

Earlier source-integrity verifiers are historical snapshots and will correctly flag the Dashboard edit. Their old receipts were not rewritten to claim this interface was previously tested.

## Concrete next evaluation proposal

Evaluate `qwen3:4b-instruct-2507-q4_K_M` as an optional local dialogue writer/reviewer through Ollama. The official [Ollama tag listing](https://ollama.com/library/qwen3/tags) lists its download at **2.5 GB**; Ollama itself and inference memory require additional resources. The [Qwen model family card](https://huggingface.co/Qwen/Qwen3-4B) describes multilingual instruction following. These are reasons to test it, not evidence that it reliably preserves Hindi meaning or produces fitting lines.

The proposed test would use the existing bounded supervision path: at most three rewrites, native duration checks, then at most one batch meaning review request. Using the same small model in both roles does not provide independent verification; its reviewer opinion stays advisory. Initially require human approval and speech audition. Keep the current translation/speech selections and accepted outputs intact; retain failed candidates and provenance.

Run locally with a short context window and sequential ownership of the GPU, releasing other stage workers before evaluation. Actual RTX 4060 memory use, latency, Hindi fidelity and shortened-cue delivery must be measured rather than promised from download size. The user previously requested a hybrid design; this local evaluation would supply its optional local component, while an explicitly configured API route remains an alternative.

No Ollama/model installation or evaluation is authorized by this document. Ask the user about the specific runtime/model and purpose before installing/downloading or changing selected connections. Automatic full-video localization and general release readiness remain pending.
