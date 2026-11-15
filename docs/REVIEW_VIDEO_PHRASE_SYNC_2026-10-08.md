# Reviewed video: phrase synchronization follow-up

## User feedback

The user clarified the initial preference for the older render: the newer version's quality is actually better, but speech precedes the matching visuals around 1:30 or slightly earlier. Preserve that quality and investigate synchronization rather than discard the new mix or change the voice recipe.

## Diagnosis and limits

`dev/audit_review_video_sync.py` compares decoded mono 8 kHz audio and downscaled pictures from both full renders. Seven audio windows, including 90–110 and 115.62–119.24 seconds, have their best correlation at zero lag; correlations exceed 0.9997. Picture comparison at 5 frames per second also finds the closest alignment at zero shift. Stream start times are zero. This establishes no overall encoded-file shift between these renders. It does not rule out browser/player startup issues, nor prove phrase-to-picture alignment.

The source contact sheet and retained source recognition offsets locate the closing visual passage. The Hindi paragraph starts at 90 seconds and lasts 22.888 seconds inside a roughly 25.62-second window. Merely fitting that window does not preserve the timing of its internal phrases. Its last sentence about wordplay began around 107.959 seconds; the corresponding English phrase is in the fragment starting 111.12 seconds. That is a concrete candidate for the reported lead. These source fragments are approximate ASR intervals, not exact forced word alignment.

Evidence: `docs/validation/2026-10-08-reviewed-video-sync-audit.json` and `2026-10-08-sync-source-contact-sheet.png`. The sheet samples from 90 seconds at one frame per second in row order.

## Focused comparison

`dev/verify_strong_whisper_review_video.py --align-ending` creates a separate diagnostic review and export. It changes only the placement of existing PCM sentence chunks in cue 12. It requires the recorded 24 kHz mono PCM format and verifies the original waveform's frame count against all six sentence chunks and five 200 ms gaps. Each copied speech chunk is byte-for-byte unchanged. No speech model runs, no words change, and no speech tempo or gain is altered.

| Sentence | Earlier start, seconds | Comparison start, seconds |
| --- | ---: | ---: |
| Opening question | 90.000 | 90.000 |
| Chart, family silhouette, lighthouse | 90.595 | 90.595 |
| Report approaching its end | 97.749 | 98.800 |
| Pedestrians, signs, pipe | 99.837 | 100.888 |
| Final summary and sign-off | 103.023 | 105.000 |
| Wordplay / Regent's Treat | 107.959 | 110.690 |

These are editorial sentence placements, not a new automatic synchronization algorithm. The last sentence cannot be moved to 111.12 at unchanged native pace without colliding with the next accepted cue. The comparison ends it at 115.618 seconds, before the next cue at 115.62. The existing grouped chart/family/lighthouse sentence is unchanged; its individual word-to-shot alignment has not been measured or repaired. The new pauses need listening review.

The ordinary reviewed-video export checks all accepted windows and asset hashes, requires video/audio/Hindi subtitle streams, checks duration, fully decodes the result, verifies the original accepted video remains unchanged and cleans its temporary job. It reuses the previous background stem. Twelve complete takes are reused unchanged and one is repositioned internally. This use of `accepted` take records in the diagnostic manifest does **not** mean the user has accepted the new timing.

Receipt: `docs/validation/2026-10-08-ending-phrase-sync-2ccdcbaf.json`.

The preview covers original-video **1:28–2:00**, so users can evaluate the affected passage directly. Its decode check is recorded in the receipt. No existing video was overwritten, no tools or packages were installed, no global synchronization offset was introduced, and release approval remains absent.

## Next decision

The user subsequently located the issue in the **first 15 seconds of this short preview**, rather than the full video's opening. The first adjustment left the chart/family/lighthouse sentence unchanged and therefore did not address that section. See `CHART_SCENE_SYNC_2026-10-08.md` for the corrected clause-level investigation and new comparison.

Review whether the later phrases now match the shots and whether the pauses feel natural. If individual words in the chart/family/lighthouse sentence still anticipate their visuals, investigate word or clause anchors rather than delaying the whole video. Implementing general automatic alignment requires separate design and evidence; this focused comparison is not that implementation.
