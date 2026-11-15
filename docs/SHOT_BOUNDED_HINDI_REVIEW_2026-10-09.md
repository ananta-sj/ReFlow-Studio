# Hindi phrase-to-shot review — 9 October 2026

## Scope and motivation

The user clarified that the problem is speech arriving before or after the matching shot, rather than voice quality. Comparing the accepted original with the first unadjusted reviewed export found no relative file offset, but both can share a phrase-to-shot mismatch. The previous whole-sentence/manual-pause comparisons were rejected and remain excluded from the baseline.

This follow-up tests the chart, family silhouette and lighthouse passage as three separate, visually bounded Hindi phrases. It does not change the full video, production pipeline or global voice settings. Artifact filenames retain the existing `2026-10-08` iteration prefix; this report records their verification and delivery on 9 October.

## Source evidence and wording

The source was inspected at 200 ms picture intervals with `2026-10-08-chart-shots-200ms.png`. Existing English/Hindi diagnostic word timestamps and scene-change candidates were also considered. The picture transitions define the review windows; the word estimates are not forced alignment or independent human timing labels.

The accepted Hindi sentence describes the laser before naming the lighthouse keeper. The English and shots introduce the keeper first. Moving that complete recording cannot independently align both concepts. The new editorial wording restores the subject-before-action order and generates the phrases separately with the existing IndicF5 engine.

| Phrase | Editorial Hindi | Placement in full source | Generated duration |
| --- | --- | --- | ---: |
| Chart | जगाने को ये एनिमेटेड चार्ट। | 90.600 s | 2.059 s |
| Family | ये औसत परिवार की परछाईं। | 93.600 s | 1.803 s |
| Lighthouse | लाइटहाउसवाले का सिर लेज़र से कटा। | 96.640 s | 2.507 s |

The wording is an explicit diagnostic editorial draft, not output from a new automatic scene-aware translator. Human approval is pending. The concise colloquial lighthouse wording should be checked for clarity and natural delivery.

## Duration constraints and preserved voice settings

The existing native IndicF5 estimator was run before generation. The initial more literal lighthouse variants exceeded its 2.48-second visual window: predictions ranged from 2.731 to 3.125 seconds. Those variants were not synthesized. The selected wording predicts 2.5067 seconds and generated 2.507 seconds. The chart/family predictions likewise matched actual durations within one millisecond.

The lighthouse speech finishes at **99.147 seconds**, while the next shot begins at **99.120 seconds**. An explicit one-frame allowance extends the speech window to 99.160 seconds, retaining the complete phrase at native pace. Its approximately 27 ms extension is documented; this is not an assertion of perfect subframe visual alignment. No word was truncated and no speed increase was applied.

The confirmed Abhishek voice profile remains unchanged, verified by SHA-256 `6045e90b7ee8266c822de3564f00b93b7a1f5aa1998b5d0865a919ef7ff96b00`. Calibration, seed, guidance, synthesis steps and sentence-gap settings remain the same. Three **new speech takes** were generated from the revised phrases; they are not byte-identical reuse of the accepted original. Their voice identity, naturalness and perceptual alignment still require listening review.

## Assembly and implementation

`dev/verify_shot_bounded_hindi.py` invokes the real existing IndicF5 provider under an owned render job and reuses its worker for the three phrases. It checks predicted/actual durations and releases the speech worker explicitly before final media assembly.

The preview covers source **88.000–99.160 seconds**. It preserves the prior interview's speech tail up to 90 seconds and the original opening question. Only the chart/family/lighthouse passage is replaced. It uses the original pictures and the hash-verified previously generated background stem, with the existing mix settings. No new separation, speech framework, alignment package, checkpoint or runtime was installed.

FFmpeg builds a fast-start MP4, with the picture and audio excerpt starting together. It does not introduce a global audio/video offset. The reviewed source section is 11.16 seconds long; the later summary/wordplay passage and the rest of the full video are not included or claimed corrected.

The scene-change logging experiment initially used output duration limiting after a selective video filter; sparse selected timestamps could exceed the intended inspection window. A corrected log uses `trim=duration=38` before selection: `2026-10-08-source-scene-boundaries-trimmed.log`. Original evidence is retained. Semantic identification of the shots still comes from visual inspection, not the scene detector alone.

## Verified artifacts

Receipt: `docs/validation/2026-10-08-shot-bounded-hindi-38a36120.json`.

Video: `docs/validation/2026-10-08-shot-bounded-hindi-38a36120/SHOT_BOUNDED_HINDI_1m28_to_1m39.mp4`.

Video SHA-256: `3e8ec35b6b9fc2b409836f66d64cae559459dc3953cce3cd94e3f2c5e3879fe8`.

Verification passed for:

- Three real synthesis results, duration preflight and actual fit checks.
- Explicit speech-worker release and temporary workspace cleanup.
- Video and audio stream presence, 11.16-second output duration and complete FFmpeg decoding.
- Unchanged source video, prior accepted full video and voice profile.
- Output hash rechecked before delivery on 9 October.

Raw generated phrase WAV files and the mixed review master remain alongside the video. The earlier broader regression suite is not claimed rerun; this follow-up modifies diagnostic code and artifacts, and verifies those operations with actual media.

## Pending review and next step

**User review result:** the user accepted the three-shot comparison except the opening “ऊब गए?”, which sounded rushed and gibberish-like. Supplemental feedback is recorded in `docs/validation/2026-10-09-shot-bounded-user-feedback.json`. Acceptance applies to the three-shot phrases/timing, not the opening question, full video or release. The original generation receipt's `human_accepted: false` is historical and remains unchanged; use the later feedback record for the current acceptance state.

The opening question reused the old 0.3947-second take. A fuller wording, “ऊब गए क्या?”, predicts 0.7573 seconds with the unchanged native voice profile. It is being evaluated separately; the existing 0.6-second opening window cannot accommodate it plus a comfortable pause. Do not silently move the accepted three phrases or clip the fuller question to force it into that window.

The new take is not yet human accepted. Ask whether each spoken reference now falls within its matching chart/family/lighthouse shot and whether the shorter phrases retain natural delivery. Do not promote this short test as a validated full-video workflow or release-ready output.

If this approach is accepted, use its timing/wording constraints to design a general reviewed phrase-to-shot workflow. The current fixture is specific to this source and must not become hardcoded production logic. Broader shot recognition, translated phrase grouping and pace constraints still require design, implementation and independent examples.
