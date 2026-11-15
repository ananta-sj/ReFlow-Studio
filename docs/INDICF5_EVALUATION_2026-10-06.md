# IndicF5 isolated evaluation — October 6, 2026

## Outcome and acceptance boundary

The first trained-model inference completed successfully and produced a
1.877333-second Hindi-target recording. Both the raw and listening WAV files
decode completely. This establishes local inference and valid media output;
it does not establish intelligibility, naturalness, voice identity or release
readiness. Human listening acceptance is pending.

Target text: **मेरे पास यह रिपोर्ट है।**

This is the sentence previously rejected in the XTTS cue investigation. It was
supplied directly to IndicF5: no speech recognition or translation ran in this
test. The reference is the official documented Punjabi female prompt, not the
user's Sujata or Abhishek recording. A Punjabi reference does not change the
requested target text; whether the generated audio actually speaks correct
Hindi must be assessed by listening.

## Installation and isolation

The user approved a separate IndicF5 evaluation environment. The core portable
runtime and existing generic F5 runtime were preserved. IndicF5's package uses
the same import namespace as generic F5, making separate environments necessary
to avoid replacing the existing implementation.

- Environment: `runtime_profiles/indicf5-evaluation`.
- IndicF5 package version: `f5-tts` 0.1.0.
- Inherited Torch runtime: 2.9.1+cpu.
- Official source: `dev/vendor/IndicF5`, commit
  `13f7c4d627cc10111aea8fe9c0039462cacacdc7`.
- Model repository: `ai4bharat/IndicF5`, revision
  `ba85abedf18dc479a447eaa0eccbd76ab78a47d5`.
- Local assets: `models/indicf5/evaluation/assets`.
- Missing declared dependency `jieba` 0.42.1 was installed only in the isolated
  environment. Build support used wheel 0.45.1 in workspace temporary tooling.
- Existing generic F5 remained version 1.1.22.

The user completed gated model access and authenticated locally. Credentials
are not recorded in this report or diagnostic output. The official asset
whitelist download completed; model weights and reference audio match official
LFS checksums. The checkpoint is 1,402,789,408 bytes. No manual recovery of its
partially downloaded file was necessary.

## Model loading and generation

`dev/verify_indicf5_smoke.py` loaded local assets without downloading during
inference. The official checkpoint contains speech-model and vocoder tensors
with compilation-wrapper prefixes. The runner removes those known namespace
prefixes, accounts for every tensor, and strictly loads both models:

- 364 speech-model tensors.
- 83 vocoder tensors.
- No ignored tensors or relaxed state-dictionary loading.
- All characters in the supplied Hindi sentence exist in the model vocabulary.

The reference is the full documented `PAN_F_HAPPY_00001.wav`: 8.1 seconds,
mono, 48 kHz. Its matching documented transcript was supplied. The runner loads
the audio directly, avoiding automatic reference trimming that could invalidate
the transcript match. Vocos configuration comes from the already available
local generic-F5 cache.

Generation used CPU, two Torch threads, 32 diffusion steps, native speed 1.0
and diagnostic random seed 1234. The seed is diagnostic information, not a
cross-platform promise of byte-identical reproduction. No compiled-model path
was used. Cancellation checks ran before transformer passes, with progress
reported every eight passes; the completed run observed 64 passes.

## Audio preparation and validation

The raw waveform is finite, nonzero, 24 kHz and saved as a floating-point WAV.
The listening copy is PCM16 with a constant +9.86 dB gain. Its measured loudness
is -19.35 LUFS and true peak -1.55 dBTP. Peak headroom limited the gain before
the nominal -18 LUFS target was reached.

No tempo adjustment, equalization, compression, word cuts or silence edits were
applied. Raw and listening copies have identical frame counts. Both passed
complete FFmpeg decoding. The owned temporary workspace was removed after
publishing the retained evidence.

The output is shorter than the historical 2.600-second cue window. That is only
a duration observation: it does not prove the sentence is complete or natural,
or that the final video pipeline accepts it.

## Performance and remaining work

Generation and audio preparation took 688.0 seconds; total measured runner time
was 695.515 seconds. Approximately eleven and a half minutes for this short
sentence is a significant CPU performance concern. This isolated first run
does not establish steady-state throughput, concurrency, or GPU performance.

Next, obtain human review of the exact words and naturalness. If the candidate
passes, test Sujata and Abhishek using accurately matched reference transcripts,
then varied Hindi passages. Broader quality tests should precede production
integration. Performance tuning must preserve meaning and listening quality.
No production engine selection or voice settings changed in this evaluation.
No full-video result, new backend suite result, portable release, commit or
push is claimed.

## Retained evidence

- Environment checks:
  `docs/validation/2026-10-06-indicf5-environment.json`.
- Pinned asset receipt:
  `docs/validation/2026-10-06-indicf5-download-26415d3e.json`.
- Completed smoke receipt:
  `docs/validation/2026-10-06-indicf5-smoke-7db43633.json`.
- Execution log: `docs/validation/2026-10-06-indicf5-smoke.log`.
- Raw recording:
  `docs/validation/2026-10-06-indicf5-smoke-63f2b94c/indicf5-raw.wav`.
- Listening recording:
  `docs/validation/2026-10-06-indicf5-smoke-63f2b94c/indicf5-listening.wav`.

Earlier failures remain in `docs/HINDI_GENERATION_INVESTIGATION_2026-10-06.md`.
The language rollout and NLLB explanation is in
`docs/LANGUAGE_PLAN_AND_NLLB_2026-10-06.md`.

## Listening update

The user replied "yep" when asked whether the presented recording speaks the
exact Hindi words clearly and sounds natural. This accepts that exact
official-reference sentence. The original execution receipt remains unchanged;
`docs/validation/2026-10-06-indicf5-smoke-user-acceptance.json` separately records
the listening decision. Sujata/Abhishek identity and broader Hindi coverage
remain untested. The next preparation step uses the already installed local
Whisper reference model to draft transcripts of the original user recordings;
ASR drafts require checking against their exact audio before conditioning tests.
