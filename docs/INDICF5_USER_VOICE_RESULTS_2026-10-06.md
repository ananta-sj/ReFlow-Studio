# IndicF5 user-voice baseline results — October 6, 2026

## Listening verdict

Both original reference excerpts and their transcripts were confirmed by the
user. The original voice recordings remain unchanged. Those confirmations do
not approve generated speech.

The generated Sujata and Abhishek controls both completed technically, but
neither has full listening acceptance:

- Sujata: initial positive feedback was corrected. The user described an
  "emotionless feeling" compared with the original, while saying it was
  otherwise good. Insufficient expressiveness is the current delivery issue.
- Abhishek: the user said "too fast and unnatural delivery". The native model
  output needs a more comfortable pace and a delivery comparison.

The accepted official-reference IndicF5 sentence remains a separate control.
Do not promote its acceptance to user-voice quality or full-video readiness.

## Controlled CPU baseline

Target text for both voices: **मेरे पास यह रिपोर्ट है।**

| Voice | Reference duration | Generated duration | Inference time | Listening gain | Listening loudness / true peak |
| --- | --- | --- | --- | --- | --- |
| Sujata | 6.600 s | 1.952 s | 557.563 s | -2.24 dB | -17.98 LUFS / -3.79 dBTP |
| Abhishek | 5.730 s | 1.205333 s | 372.578 s | -3.61 dB | -18.91 LUFS / -1.55 dBTP |

Both runs used the same target, 32 diffusion steps, native generation speed 1.0
and seed 1234 reset immediately before synthesis. The CPU model was loaded once
for the serial batch. All 364 speech-model and 83 vocoder tensors loaded
strictly. Accepted reference audio hashes and matching text were checked before
inference, and the audio hashes were rechecked afterward.

Each raw waveform is finite, nonzero and 24 kHz. Listening copies use constant
gain only, with identical frame counts and complete decoding checks. No added
tempo adjustment, EQ, compression or word editing was applied. Thus Abhishek's
fast delivery occurred in native model generation; it is not the older 1.342
Hindi pipeline tempo applied afterward. The generation duration derives from
the reference audio/text ratio in upstream `infer_batch_process` when no fixed
duration is supplied. That explains the duration-setting mechanism, not every
perceived naturalness problem.

The batch took 940.187 seconds overall and removed its owned temporary
workspace. Each completed voice was published separately, preserving results
even if a subsequent case had failed. The final receipt records completion,
but retains `human_quality_accepted=false`; listening records are separate.

## Evidence

- Runner: `dev/verify_indicf5_user_voices.py`.
- Execution receipt:
  `docs/validation/2026-10-06-indicf5-user-voices-d47f7b63.json`.
- Execution log: `docs/validation/2026-10-06-indicf5-user-voices.log`.
- Media directory: `docs/validation/2026-10-06-indicf5-user-voices-d47f7b63`.
- Sujata listening SHA256:
  `b9daf2ac7ab7841e7243355cc74303544c0b11209652c7c352af045e592e9ba2`.
- Abhishek listening SHA256:
  `32204f760b752f25297f7a9004799df14a9e79d2cd8581a50a1dd94fd2d81297`.
- Sujata feedback history:
  `docs/validation/2026-10-06-indicf5-sujata-generated-user-acceptance.json`.
- Abhishek rejection:
  `docs/validation/2026-10-06-indicf5-abhishek-generated-user-review.json`.

## Performance preparation and next experiments

The existing NVIDIA utility confirmed RTX 4060 Laptop GPU, 8,188 MiB, driver
617.14. The current evaluation is CPU-only. The user approved a separate GPU
evaluation runtime with the official matched Torch 2.9.1, torchvision 0.24.1
and torchaudio 2.9.1 CUDA 12.8 packages. Preparation and download are underway;
GPU speech and actual speedup remain unverified.

A sandboxed live-file view showed zero download bytes, but inspection of the
task-owned elevated download process showed approximately 840 MB written.
The transfer was therefore not restarted. Do not treat that stale size view as
proof of a network stall.

After package/device verification, retain GPU baselines and compare bounded
generation variants. For Abhishek, adjust native generation duration/pace and
listen for complete words and comfortable delivery. For Sujata, compare
generation guidance and seed variation without asserting that either is a
guaranteed emotion control. Keep each parameter change explicit, references
fixed and listening preparation gain-only. No production default should change
on the basis of technical execution alone.

Production integration, longer Hindi passages and the complete moving-video
workflow remain pending. See `docs/INDICF5_INTEGRATION_REVIEW_2026-10-06.md` for
the inspected reference, runtime, mastering and timing requirements.
