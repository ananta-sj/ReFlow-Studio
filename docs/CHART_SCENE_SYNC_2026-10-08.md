# Chart, family and lighthouse: corrected synchronization comparison

## Clarified target

The user specified **0:00–0:15 of the short comparison**, corresponding to approximately **1:28–1:43 in the full source**. The prior sentence-only adjustment left the chart/family/lighthouse sentence unchanged and therefore missed the principal reported problem. This follow-up targets that sentence explicitly. Preserve the voice delivery and quality the user preferred; do not delay the entire video or globally accelerate speech.

## Investigation

The existing file comparison established no whole-track shift between the older and newer encodes. The new diagnostic `dev/inspect_chart_phrase_timing.py` uses the already installed pinned Whisper large-v3-turbo model to estimate word times for the exact accepted Hindi sentence and the corresponding nine-second English excerpt. It uses local safetensors, offline loading, the existing GPU runtime and eager attention for word timing. No package or model was installed.

The word results are recognition-based diagnostic estimates, **not forced alignment against a verified supplied transcript**. Both recognized excerpts reproduce the expected chart/family/lighthouse content. They provide useful clause-boundary hints, not a general guarantee of millisecond word accuracy.

With the original Hindi sentence starting at 90.595 seconds, its family and laser references arrive earlier than the English references and shots. For example, the estimated Hindi laser word starts around 95.115 seconds, while the English laser word starts around 98.16 seconds. The visual contact sheet independently locates the family silhouette around 94 seconds and lighthouse/beheading around 97–98 seconds.

Evidence: `docs/validation/2026-10-08-chart-phrase-word-timing.json`, plus the existing source contact sheet. The extracted diagnostic WAV files live in the corresponding `2026-10-08-chart-phrase-word-timing` directory. They are retained for reproducibility and are not replacements for the original source or accepted reference audio.

## Dependency failure and repair

The first diagnostic attempted the installed Transformers ASR pipeline with an audio filename. It tried to load unavailable TorchCodec Windows libraries and failed. Passing a predecoded array still triggered that pipeline's unconditional import. Both failure logs are retained as `2026-10-08-chart-phrase-torchcodec-failure.log` and `2026-10-08-chart-phrase-torchcodec-array-failure.log`.

The working diagnostic bypasses pipeline preprocessing: bundled FFmpeg decodes the waveform, the existing feature extractor prepares it, and the existing model generates token timestamps. The tokenizer decodes word timestamps using the same installed implementation. No TorchCodec installation or runtime replacement was needed, and production recognition remains on its existing FFmpeg-based worker path.

## Comparison construction

`dev/verify_strong_whisper_review_video.py --align-scenes` splits the saved accepted sentence at **2.20 and 4.15 seconds within that sentence**. Word estimates suggest these are the gaps after the chart and family clauses. A 20 ms waveform RMS check around each cut must be below 0.005 of full-scale amplitude, reducing the risk of cutting audible speech. The run passed both checks. Low RMS is not proof of perceptually seamless phrasing, so the comparison still needs listening review.

The three pieces concatenate exactly to the complete original sentence PCM. Every piece remains byte-for-byte identical when placed in the new cue. No speech samples are removed, resynthesized, stretched, normalized or faded. The diagnostic only inserts timing gaps and changes placement. It preserves the original opening question and positions later sentence chunks after the expanded visual sequence without overlap.

| Piece | New absolute start | Purpose |
| --- | ---: | --- |
| Opening question | 90.000 s | Preserve accepted question |
| Chart clause | 91.000 s | Follow chart shot |
| Family silhouette clause | 94.000 s | Match family shot |
| Laser/lighthouse clause | 97.450 s | Move laser reference toward beheading shot |
| Report approaching its end | 100.456 s | Follow the completed preceding clause |
| Pedestrians/signs/pipe | 102.544 s | Retain native speech and avoid overlap |
| Final summary/sign-off | 105.730 s | Match later summary passage more closely |
| Wordplay / Regent's Treat | 110.690 s | Preserve previously proposed later placement |

The eight pieces finish at 115.618 seconds, before the next cue at 115.62. All take windows and non-overlap assertions passed. Sentence structure differs between Hindi and English, so exact word-for-word visual synchronization is not established; in particular the Hindi lighthouse subject follows the laser description. These anchors are an explicit editorial comparison for this source, not hardcoded production behavior or an automatic synchronization implementation.

## Export verification and artifacts

Full export receipt: `docs/validation/2026-10-08-chart-scene-sync-f4cb0e7e.json`.

The ordinary reviewed-video operation rendered the full source with twelve unchanged accepted takes and one internally repositioned take. It reused the prior background stem. No new TTS or separation was performed. It verified input/take hashes, source preservation, source duration, Hindi subtitle metadata and a full video decode. It also verified that the original accepted video remains unchanged and removed the temporary job workspace.

The new **32-second preview covers original 1:28–2:00**, including the user's reported first 15 seconds. Its full decode check and exact path are recorded in the receipt. Neither older comparison was overwritten. No persistent settings, application voice profile or playback speed was changed.

## Pending review

Follow-up measurement: `SYNC_CONTROL_MEASUREMENT_2026-10-08.md` compares the accepted original with the first **unadjusted** review at 25 fps and 48 kHz. It finds zero best picture shift and zero best audio lag in all six windows spanning 88–105 seconds. This does not establish a preview-player fault, but does not support another relative file delay. A controlled single-file A/B excerpt has been prepared without the rejected manual placements.

**Review result: rejected.** The user reported: “delayed this time... the og one was much better.” The manually anchored comparison overcorrected timing perceptually and must not replace the original. The exact artifact intended by “og” has not been separately confirmed, so preserve all originals and retain the prior accepted baseline. No timing change was applied to production code or global settings. Feedback is recorded in `docs/validation/2026-10-08-chart-scene-sync-user-feedback.json`. Stop further guessed placement adjustments; structural decode and waveform checks did not establish acceptable synchronization.

Ask the user whether the chart, family and lighthouse now match the speech and whether the inserted pauses sound natural. The comparison's manifest uses accepted-take records to exercise the render contract; that does not imply human approval of the new placements. Preserve the previously accepted full-video baseline until this comparison is accepted. Global workflow alignment, broader language support and release validation remain separate work.
