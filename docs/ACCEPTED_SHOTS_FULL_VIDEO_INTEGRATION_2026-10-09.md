# Accepted Hindi shots: full-video integration — 9 October 2026

## Objective and human acceptance

The short source window 88.000–99.160 seconds was approved with **“yep it's good”** after the accepted “बोर हो गए?” delivery was spliced into the previously reviewed chart passage. The family/lighthouse recordings and placements were preserved. Approval is recorded in `validation/2026-10-09-question-only-video-user-feedback.json`, bound to video SHA-256 `d897e336ee7c5d954f5c5766d36ca3ad9205818c227279960a69b8dbc33a9734`. The preceding wording/duration/seed trials and narrower acceptance records remain in `QUESTION_CONTEXT_REVIEW_2026-10-09.md`.

This iteration integrates that exact accepted speech section into a full video and checks the following transition. It does not infer full-video or release approval from the short review.

## Why a simple full-master patch would be incorrect

The historical cue-12 recording placed “रिपोर्ट ख़त्म होने को है।” at approximately 97.749 seconds. The accepted lighthouse now ends at 99.147 seconds. Pasting the accepted short master over the old full master would overwrite only part of the following sentence or create overlapping narration. Instead, the evaluator rebuilds cue 12 from intact, hash-verified PCM phrases, including all four subsequent historical sentences, and positions the final sign-off separately.

## Source diagnostic

The installed offline Whisper recognizer, revision `41f01f3fe87f28c78e2fbf8b568835947dd65ed9`, inspected source 99.160–119.500 seconds. Receipt: `validation/2026-10-09-source-tail-word-timing.json`; log: `validation/2026-10-09-source-tail-word-timing.log`. `dev/inspect_chart_phrase_timing.py --tail-only` exposes this diagnostic without altering the original chart diagnostic default.

Its English transcript contains the report-ending narration, illustrative pedestrians/signs/pipe, final summary, wordplay and Charlie Brooker sign-off. Word timestamps are approximate recognition estimates, not forced alignment or proof of exact visual synchronization. Anchors require human review in the resulting video.

| Passage | Diagnostic source anchor | Candidate Hindi start | Hindi end |
| --- | ---: | ---: | ---: |
| Accepted question and chart | Previously accepted short video | 90.000 | 93.200 |
| Accepted family | Previously accepted short video | 93.600 | 95.403 |
| Accepted lighthouse | Previously accepted short video | 96.640 | 99.147 |
| Report nearing its end | 99.160 | 99.360 | 101.248 |
| Pedestrians, signs, pipe | Pedestrians word: 101.660 | 101.450 | 104.437 |
| Final summary | “And then”: 104.440 | 104.640 | 109.376 |
| Wordplay | “If you're lucky”: 111.060 | 111.060 | 115.988 |
| Charlie Brooker sign-off | 116.080 | 116.190 | 118.526 |

The report sentence begins after a 213 ms gap from the lighthouse; it is preserved whole. The pedestrians line starts close to the matching English noun, rather than the preceding “illustrative shots” wording absent from the concise Hindi draft. The concise Hindi summary ends before the longer English summary; its 1.684-second gap before wordplay is retained instead of stretching the accepted speech. The final sign-off is shifted from 115.620 to 116.190 so it follows the complete 4.928-second wordplay and is close to the source sign-off. These are explicit editorial placements for this source, not production alignment rules. All later placements remain pending human review.

## Implementation and preservation

`dev/build_accepted_shot_cue.py` verifies the short-video acceptance/hash, the question-only splice, original shot files, original cue-12 hash and source diagnostic receipt. It builds a new mono 24 kHz PCM cue: accepted question/chart at the original positions, unchanged family/lighthouse samples, and the original four tail sentences copied by their recorded frame counts. It excludes the original internal fixed gaps when moving phrases, then inserts silence at the explicit new positions. Every phrase is checked sample-for-sample after placement, overlaps are rejected, and the written full cue is read back and compared with the intended PCM.

`dev/verify_strong_whisper_review_video.py --accepted-shots` imports this cue into the existing `ReviewStore` rendering workflow. It refuses the older rejected `--align-ending`/`--align-scenes` experiments in combination with this option. The other accepted takes remain unchanged; the final sign-off waveform is preserved with a new start time. Updated Hindi text accompanies the rebuilt cue, and subtitles remain tagged `hin`. Prior live recognition/translation receipts and the reviewed spoken draft remain intact; this render reuses them rather than claiming a new full recognition or translation run. No new TTS or separation is performed.

The prior separated background is reused with the existing mixing behavior. Uniform generation gain, mix ducking and final codec encoding are distinct from phrase delivery: exact-sample preservation applies to the stored speech cue, not the complete compressed MP4 soundtrack. Original source, earlier full renders and short comparisons remain preserved.

No model, reference, production voice setting, runtime, package, framework or application default is installed or replaced. Seed 7 remains confined to the accepted question's stored recording; it is not promoted as a global naturalness setting.

## Verification and review boundary

The integration runs through the real reviewed-video renderer, validates take bounds and file identities, fully decodes the full output, checks duration and Hindi subtitle metadata, and creates a separate 88.000–119.160-second ending preview. Owned temporary render files are cleaned. These media checks establish structural validity and preserved assets, not human naturalness, absence of every separation artifact or phrase-to-shot synchronization. The full-video candidate and ending preview require review before acceptance. This iteration is not a release sign-off.

## Completed render evidence

The integration completed successfully. Receipt: `validation/2026-10-09-approved-shot-full-video-55b89369.json`; log: `validation/2026-10-09-approved-shot-full-video.log`. The real reviewed-video operation reported completion. All take bounds, PCM assembly and input-hash checks passed; the full output decodes, Hindi subtitles are tagged `hin`, and duration is **122.531995 seconds**. The original source and accepted historical full video retain their hashes. The owned temporary render workspace was removed. The first eleven historical cue recordings and final sign-off recording are unchanged; the latter has the explicit new start. The modified composite cue's SHA-256 is `7a621ad45691ec29b60eae489b0e5bf3081bc8bb6b216e1b1324467fbe6150ab`.

Full video: `validation/2026-10-09-approved-shot-full-video-55b89369/REVIEWED_VIDEO_8cb879402855.mp4`, SHA-256 `2ce2e0b4954280923d60774f5945367bff1cef3d444f7357625a1507153d4d08`.

Ending preview: `validation/2026-10-09-approved-shot-full-video-55b89369/APPROVED_SHOTS_AND_ENDING_1m28_to_1m59.mp4`, SHA-256 `63819507fa0c4948ed54ae026c9799a00748b16b8e8e38a33398f9568a37c1b1`. Its full decode also passed. This preview is extracted from the completed full output, not assembled independently with another timeline.

No production code changed in this integration. Earlier backend/frontend suites are historical evidence, not claimed as newly rerun; the relevant new verification is the completed reviewed-video render and media/asset checks. Human review of the newly placed tail and complete output remains pending. Automated general-purpose shot alignment, expressive question generation across arbitrary texts and full-feature release readiness are not established by this source-specific editorial evaluation.
