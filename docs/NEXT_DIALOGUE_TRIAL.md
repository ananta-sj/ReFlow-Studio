# Dialogue-adaptation trial — replacement authorized

The installed MT candidates do not reliably shorten Hindi dialogue while keeping
meaning and natural grammar. The next proposed experiment targets instruction
following and rewriting, rather than another translation-only model.

Outcome: replacement verified and evaluated; not approved for production.
See `QWEN35_DIALOGUE_TRIAL_2026-11-15.md` for observed failures. The plan below
records the authorized scope, rather than a pending download request.

Candidate: Qwen3.5-9B, Unsloth Q4_K_M GGUF, approximately 5.68 GB.
Publisher artifact:
https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/blob/3885219b6810b007914f3a7950a8d1b469d598a5/Qwen3.5-9B-Q4_K_M.gguf
Published SHA-256:
`03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8`.
Original model: https://huggingface.co/Qwen/Qwen3.5-9B

The existing portable runner contains the qwen35 architecture identifier. This
is a compatibility precheck, not proof that inference will work. Reuse the runner
and ask separately if an additional software change proves necessary.

The owner approved this replacement on November 15, 2026. Download into a new owned isolated trial directory using the existing
resumable transfer helper. Pin metadata and verify the complete checksum before
loading. Only after verification, retire the failed 4.62 GB HY-MT 7B trial weights,
keeping its diagnostics and the active application models. Net retained model
growth would be approximately 1.06 GB; download assembly temporarily needs more.

Acceptance sequence:

1. Test the failed mother-Europe line for both facts, natural first-person grammar
   and the source-derived speech budget. Test the village/father line for the
   correct relationship and female agreement. Do not provide hand-written target
   answers to the candidate model.
2. Check the complete known scene, plus separate quantity, negation, relationship
   and gender fixtures without unrelated scene-history contamination.
3. Bound candidate count and generation; reject unfinished output, lost facts,
   over-budget wording and malformed responses. Model confidence is not approval.
4. Run actual matched voices and word/timing checks only after the wording passes.
   Continuous listening and complete-episode checks remain necessary afterward.

This experiment has no promised quality outcome. It does not authorize an active
model switch, system-wide installs, driver/security changes or another model
download if this candidate fails. The earlier Qwen3-4B trial failed; the newer
generation and larger size are reasons to evaluate, not evidence of success.
