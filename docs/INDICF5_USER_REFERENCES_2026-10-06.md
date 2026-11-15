# IndicF5 user-reference preparation — October 6, 2026

## Current outcome

The user accepted the exact official-reference IndicF5 sentence with "yep".
That listening decision is recorded separately in
`docs/validation/2026-10-06-indicf5-smoke-user-acceptance.json`. It does not yet
accept either user voice, longer passages, timing integration or a full video.

Both original user recordings have now been decoded and transcribed locally.
Short excerpts are ready for checking their exact words. They are excerpts of
the original recordings, not newly generated speech. Their proposed transcripts
remain unverified, so no IndicF5 Sujata/Abhishek synthesis result is claimed.

## Source preservation

- Sujata: `C:/Users/19shr/Downloads/Hindi_F_Sujata.mp3`, SHA256
  `4bfa094660ff97dfb29293a59dc06b7a687f56abbe6b2fc8778d6a537faea870`.
- Abhishek: `C:/Users/19shr/Downloads/HIN_M_AbhishekS.mp3`, SHA256
  `295b74a615b593626c8219fc46689336ac3c525fb54ac3088d1774e08125a319`.

The hashes match the retained original-reference receipt from October 4.
Sources were read, not edited. Preparation produced full mono PCM16 copies
at 24 kHz for reference use and at 16 kHz for recognition. Full decoded lengths
are 17.528167 seconds and 19.774708 seconds respectively. No gain, equalization,
tempo processing or silence removal was applied to those copies.

## Transcription attempt, failure and repair

`dev/prepare_indicf5_voice_references.py` uses the already installed
Whisper-large-v3-turbo assets in `models/f5/reference-asr`. No new model download,
package installation or framework was needed.

The first invocation using the generic F5 interpreter produced no startup log
and was stopped. The empty log is retained as
`docs/validation/2026-10-06-indicf5-user-references-stalled-startup.log`.
Its underlying stall was not diagnosed; do not infer that the generic runtime
is broken from this observation alone.

The next invocation used the isolated IndicF5 evaluation interpreter. It loaded
Whisper weights, but Transformers' ASR pipeline imported TorchCodec native
libraries even when passed decoded NumPy samples. Those Windows libraries
failed to load. The failed receipt
`docs/validation/2026-10-06-indicf5-user-references-1b39f646.json` and
`docs/validation/2026-10-06-indicf5-user-references-codec-failure.log` preserve
the error and owned-workspace cleanup.

The diagnostic was changed to call the existing Whisper feature extractor and
`model.generate` directly. It feeds already decoded 16 kHz arrays, bypassing
the pipeline's optional codec import without patching installed packages or
changing production code. Offline model/processor loading, evaluation mode,
Torch inference mode, two CPU threads, cooperative decoder cancellation and
progress reporting are retained. Hindi is an explicit reference-transcription
hint, not an independently detected language result.

The repaired run completed in 200.297 seconds. Sujata recognition took 61.625
seconds; Abhishek took 132.343 seconds. The successful receipt is
`docs/validation/2026-10-06-indicf5-user-references-984652c4.json`; complete
reference copies are in the directory with that same basename. Original hashes
were rechecked after recognition. The owned job workspace was removed after
publication. This successful result verifies execution, not every recognized
word: Abhishek's draft contains obvious spelling/word recognition errors.

## Short reference candidates

`dev/prepare_indicf5_reference_excerpts.py` creates the following candidates from
the full decoded references:

| Voice | Interval | Proposed matching text |
| --- | --- | --- |
| Sujata | 0–6.600 seconds | बच्चों, क्या आपको मालूम है कि पेड़ के पत्ते हरे लेकिन फूल रंगीन क्यों होते हैं? |
| Abhishek | 0–5.730 seconds | इसके बाद हम एक ऐसे खिलाड़ी के बारे में बात करेंगे जिससे इस वर्ल्ड कप में भारतीय फैंस को काफी उम्मीदें रहेंगी। |

Sujata's first recognized segment ends at 6.16 seconds and the next begins at
6.92 seconds; the 6.6-second boundary is a candidate between them. Abhishek has
a measured low-level pause from approximately 5.391 to 6.071 seconds at the
diagnostic -28 dB threshold; the 5.73-second boundary is inside it. ASR timestamps
and silence thresholds are only preparation hints. Human listening must confirm
that each excerpt contains the proposed complete sentence and no additional
spoken words.

The proposal changes Sujata's spelling "मालुम" to "मालूम". Abhishek's proposal
corrects "खिलाडी", "वर्ल्लकप" and "मीदे" to "खिलाड़ी", "वर्ल्ड कप" and
"उम्मीदें". These are explicit proposals rather than verified transcripts.
The raw ASR text remains in both receipts for comparison.

Excerpt samples exactly equal the selected prefix of their 24 kHz full
reference copies; the runner checks equality after writing PCM16. Both files
passed complete FFmpeg decoding. No gain, EQ or tempo changes were applied.
The original sources were rechecked and remain unchanged.

Evidence:

- `docs/validation/2026-10-06-indicf5-reference-excerpts-20f08c78.json`.
- `docs/validation/2026-10-06-indicf5-reference-excerpts-20f08c78/sujata-reference-excerpt.wav`.
- `docs/validation/2026-10-06-indicf5-reference-excerpts-20f08c78/abhishek-reference-excerpt.wav`.

## Next gate

Confirm or correct the proposed text against each exact excerpt. Then use those
matched audio/text pairs for serial IndicF5 voice tests, retaining the official
reference control, native generation speed and gain-only listening preparation.
No generated user-voice audio should be treated as accepted before listening.
The shorter reference may lower generation cost because the diffusion model
processes reference frames too, but no performance improvement is measured yet.
Production routing and complete-video validation still remain pending.

## User confirmation and synthesis start

The user confirmed "correct wording, correct tone, beautiful delivery... just
so so real and natural" for both presented original-reference excerpts. Exact
hashes and matching text are recorded in
`docs/validation/2026-10-06-indicf5-reference-excerpts-user-acceptance.json`.
This confirms the conditioning inputs, not newly synthesized voice quality.

`dev/verify_indicf5_user_voices.py` now evaluates both voices serially with
the same target sentence. It strictly loads the trained model once, verifies
accepted reference hashes/text, uses 32 diffusion steps and native speed 1.0,
and prepares gain-only listening copies. Each completed voice is published
separately with hashes and duration/level evidence. The final receipt will
record overall completion or failure; listening acceptance remains separate.
No production audio processing or engine routing changed for this test.

`docs/INDICF5_INTEGRATION_REVIEW_2026-10-06.md` records the inspected runtime,
checkpoint, reference, mastering and timing requirements for later integration.
