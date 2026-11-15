# Synchronization control measurement — 8 October 2026

## Why this follow-up was needed

The user preferred the newer review's quality but reported speech preceding picture in the first 15 seconds of its short excerpt. Two editorial timing experiments were made. The later chart/family/lighthouse experiment was rejected: “delayed this time... the og one was much better.” Neither timing experiment changed production settings or overwrote the accepted original.

The next task is to measure the actual difference before making another correction. A word or phrase arriving earlier than its English counterpart is not by itself proof that a video file has acquired a synchronization offset. Hindi phrase order can differ from English; the accepted baseline also contains that same Hindi recording.

## Inputs

The comparison uses the previously accepted full video from `2026-10-08-spoken-hindi-full-video-887151ac.json` and the **first unadjusted** reviewed export from `2026-10-08-reviewed-strong-whisper-video-2f75ebb6.json`. It excludes both rejected manual retiming experiments.

Both input MP4 hashes are verified before analysis and again after export. The measured section is **88–105 seconds**, encompassing the user's reported preview interval. The original file, voice references, spoken draft, provider selection and production configuration remain untouched.

## More precise measurements

`dev/verify_sync_control_comparison.py` decodes pictures at 25 frames per second, using 64×36 grayscale frames to limit processing and memory. It tests candidate alignments from minus to plus one second in 40 ms increments.

Best picture alignment: **zero frames / zero seconds**. Mean absolute pixel difference at zero shift is **0.2561** on a 0–255 scale. Moving either direction by one frame increases it to approximately **4.8203**. The small zero-shift difference is consistent with different video encodes. This is a sampled picture alignment measurement, not bit-identical source-frame hashing or a measurement of the live UI player's rendering.

Audio is decoded to mono 48 kHz PCM. FFT correlation tests delays within plus/minus one second in six separate windows:

| Source interval | Best review-versus-original delay | Zero-delay correlation |
| --- | ---: | ---: |
| 88–90 s | 0 samples | 0.998966 |
| 90–94 s | 0 samples | 0.999911 |
| 94–97 s | 0 samples | 0.999700 |
| 97–100 s | 0 samples | 0.999964 |
| 100–103 s | 0 samples | 0.999714 |
| 103–105 s | 0 samples | 0.999508 |

The correlation peak therefore finds **no measurable audio displacement between these two files** in the affected section. Their waveforms are not asserted to be bit-identical: codec and mixing differences exist. This comparison does not establish perfect speech-to-shot timing relative to the original English, and does not measure preview playback drift, rendering delays or the user's perception.

## Interpretation and correction to earlier diagnosis

The evidence does not support an encoded synchronization regression between the accepted original and the first unadjusted reviewed export in this interval. It does show why a manual relative delay was not justified by that comparison.

Earlier keyword timing identified the Hindi “laser” before the English “laser.” However, the Hindi clause describes the laser before naming the lighthouse keeper, while the English clause names the keeper before describing the laser. Using that isolated noun as a visual alignment anchor can overcorrect a naturally reordered translation. The user rejected the resulting placement; it must not become production behavior.

The original accepted timing remains the baseline. No global delay, playback-rate adjustment, translation rewrite, new TTS generation or new speech alignment framework has been applied in this follow-up. The live-preview explanation is a hypothesis, not an established root cause.

## Controlled listening comparison

The diagnostic extracts the same 17-second source interval from both files using matching encoding settings and combines them sequentially into **one 34.005-second MP4**:

- Approximately **0:00–0:17: A**, accepted original.
- Approximately **0:17–0:34: B**, first unadjusted review export.

This uses one continuous playback file and common codec settings. Each half retains its own audio and picture; rejected editorial delays are not included. Timestamp resets apply equally to the audio and video excerpt. Fast-start MP4 layout places playback metadata at the beginning of the file. These controls reduce separate-file/player-startup differences; they do not prove a preview-player fault or guarantee the app never drops frames.

The combined file is a diagnostic listening artifact. It is not a replacement final dub, new voice-quality sample or release approval. Re-encoding can cause small visual/audio differences; that limitation is shared by both halves.

Receipt: `docs/validation/2026-10-08-sync-control-3c61f863.json`.

Comparison: `docs/validation/2026-10-08-sync-control-3c61f863/A_ORIGINAL_THEN_B_UNADJUSTED_REVIEW.mp4`.

Output SHA-256: `50bf8283e962932f33e612dbd4cb097d2bb172bd90daa8063cd3e44546aae3ad`.

## Verification and next decision

The user reported that both comparison halves were bad and confirmed the issue was speech before/after its matching shot. Thus zero relative export offset does not resolve the shared phrase-to-shot mismatch. The next focused experiment is documented in `SHOT_BOUNDED_HINDI_REVIEW_2026-10-09.md`; it evaluates shorter editorial phrases with unchanged voice settings, without promoting the rejected manual shifts.

Actual-media assertions passed for zero best picture displacement, zero best audio lag in all six windows, input hash preservation, video/audio stream presence, approximately 34-second combined duration and complete FFmpeg decoding. The temporary job workspace was removed. No AI model inference, package installation, cache deletion or persistent setting change occurred. These actual-media checks are the appropriate verification for this diagnostic; unrelated regression suites were not rerun.

Ask whether A and B still feel different in this single playback. If they match, preserve the baseline timing and stop the manual shifts. If they differ, identify the exact phrase/frame and distinguish playback behavior from phrase-to-shot perception before proposing another change. The encoded-file measurements and the user's listening report should both remain in the record.
