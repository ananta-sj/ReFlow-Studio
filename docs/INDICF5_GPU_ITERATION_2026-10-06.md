# IndicF5 GPU and delivery iteration — October 6, 2026

## Current result and user feedback

The isolated GPU setup works with the trained IndicF5 model. Six bounded
short-sentence trials completed, all with valid decoded audio. The user chose
**C for both voices** from the presented A/B/C comparisons. Those are preferred
exact short takes; longer passages and the complete video remain unvalidated.

The earlier CPU recordings remain retained: Sujata was clear but emotionless
relative to the original; Abhishek was too fast and unnatural. These decisions
are not overwritten by the GPU preferences. Original reference excerpts remain
confirmed, and source recordings remain unchanged.

## Approved installation and isolation

The user explicitly approved a separate GPU evaluation runtime. The existing
NVIDIA utility reports RTX 4060 Laptop GPU, 8,188 MiB, driver 617.14.

`runtime_profiles/indicf5-gpu-evaluation` contains its own portable Python files
and GPU Torch packages. It uses the existing IndicF5 profile's non-Torch
dependencies through a relative search-path entry, with local GPU packages
first. This avoids copying all dependencies and model weights; it requires
the CPU dependency profile to remain present. It is an evaluation overlay,
not an independently validated release package.

Installed official CUDA 12.8 packages:

| Package | Version | Wheel bytes |
| --- | --- | --- |
| torch | 2.9.1+cu128 | 2,862,053,390 |
| torchvision | 0.24.1+cu128 | 9,024,408 |
| torchaudio | 2.9.1+cu128 | 2,213,241 |

This matched set follows the official
[PyTorch version instructions](https://pytorch.org/get-started/previous-versions/#v291).
Actual artifact links and SHA256 values came from the official CUDA 12.8
package index. Full wheel hashes, metadata names/versions and inherited
dependency requirements were verified before local installation. Installation
used only the approved wheels, no dependency changes and no package cache.
No system driver, production runtime or source model was replaced.

Afterward, metadata still shows Torch 2.9.1+cpu in both existing CPU profiles,
IndicF5 0.1.0 in its CPU profile and generic F5 1.1.22 in its profile. The CPU
IndicF5 Python search-path hash is unchanged. These checks and the explicit
target install substantiate isolation; they are not an exhaustive hash of
every inherited package file.

## Transfer recovery and cleanup

The initial pip transfer was slow. A sandboxed live-file view showed zero bytes,
but inspection in the download process's host context confirmed writes in
progress. The task did not discard that progress. The official CDN supported
exact byte ranges and published a SHA256 for the selected Windows CPython 3.10
wheel.

A 1,043,333,120-byte contiguous prefix was preserved, then the initial transfer
was stopped. The remaining bytes were downloaded with eight bounded workers
in 32 MiB ranges. Every response's status, byte range and body length were
checked; completed ranges were saved for resumption. The assembled full wheel
matched SHA256
`64399adaa8ea0896d02cf844cba3c5dd77e769520a1af73572599e0eaa2cf551`.
That remainder attempt took 597.516 seconds; this is not total download time.

After package, device and trained-speech checks passed, the three wheel files
and the old task-owned partial transfer were removed with exact-path ownership
and checksum checks for the completed wheels. Cleanup removed 3,989,238,047
bytes, approximately 4.0 GB. Receipts, logs, installed packages, models,
references and generated media were retained. No recursive user-data cleanup
or global cache purge occurred.

## GPU verification and measured scope

All three imported GPU packages resolved inside the new profile. CUDA 12.8 was
available, and actual GPU matrix multiplication, torchvision NMS and torchaudio
resampling passed. Device checks alone did not accept speech quality.

Trained speech then loaded all 364 model and 83 vocoder tensors strictly.
References matched the confirmed audio hashes/transcripts and contained no
characters outside the vocabulary. The same local pinned assets were reused,
with no model download during inference. The vocoder and model ran on CUDA.

| Case | Output seconds | Inference seconds | Native speed | Guidance | Seed |
| --- | --- | --- | --- | --- | --- |
| Sujata A | 1.952 | 6.375 | 1.0 | 2.0 | 1234 |
| Abhishek A | 1.205333 | 7.297 | 1.0 | 2.0 | 1234 |
| Sujata B | 1.952 | 6.140 | 1.0 | 1.5 | 1234 |
| Sujata C | 1.952 | 5.500 | 1.0 | 2.0 | 42 |
| Abhishek B | 1.866667 | 5.875 | 0.65 | 2.0 | 1234 |
| Abhishek C | 1.866667 | 6.047 | 0.65 | 2.0 | 42 |

The six-case runner measured 50.282 seconds overall after its import stage.
Largest per-case Torch peak allocated GPU memory was 1,463,192,064 bytes;
this is PyTorch allocation, not total driver/device memory use.

CPU baseline inference took 557.563 seconds for Sujata and 372.578 seconds
for Abhishek. GPU baseline timing is substantially faster for these short
cases. This is not a general full-video benchmark or a guarantee of identical
CPU/GPU audio; seeded random noise and arithmetic differ across devices.

## Delivery experiments and comparison integrity

Each case used 32 diffusion steps and the same words/reference pair. Sujata B
changed guidance only; C changed seed only. Abhishek B changed native generation
speed from 1.0 to 0.65; C kept that pace and changed seed. Native speed controls
generation duration through the upstream reference/text ratio. No generated
audio was stretched afterward.

Listening copies received constant gain only, with unchanged frame counts,
finite/nonzero output and complete decoding checks. A/B/C montages concatenate
the exact PCM samples with 0.65 seconds of silence between takes; no additional
gain, EQ or speed effect was applied. Both montages passed sample equality and
complete decoding checks.

The user replied "c f both", interpreted as C for both voices. Exact preferred
hashes and settings are in `2026-10-06-indicf5-gpu-user-choices.json`. These
preferences do not imply that seed 42 or speed 0.65 universally fixes naturalness.
Guidance is not treated as a guaranteed emotion control.

## Next acceptance gate

A three-sentence test is running with the preferred per-voice settings:

> मेरे पास यह रिपोर्ट है। इसे ध्यान से पढ़िए और बताइए कि आपको क्या लगता है। अभी कोई बदलाव मत कीजिए।

It tests longer continuity and a final negation. Its words are speech test data,
not instructions to modify the project. Await completed execution and listening
before accepting it. Varied wording, actual pipeline references/mastering/timing,
review-to-video integration and a complete moving-video result still remain.

## Evidence and changed helpers

- Setup: `dev/prepare_indicf5_gpu_evaluation.py`.
- Range transfer: `dev/resume_indicf5_gpu_wheel.py`.
- Wheel verification: `dev/verify_indicf5_gpu_wheels.py`.
- Device verification: `dev/verify_indicf5_gpu_environment.py`.
- Voice runner extended with explicit GPU, variant and selected-script modes:
  `dev/verify_indicf5_user_voices.py`.
- Comparison assembly: `dev/prepare_indicf5_gpu_comparisons.py`.
- Owned transfer cleanup: `dev/cleanup_indicf5_gpu_downloads.py`.
- Package receipt: `docs/validation/2026-10-06-indicf5-gpu-wheels.json`.
- GPU receipt: `docs/validation/2026-10-06-indicf5-gpu-environment.json`.
- Speech receipt: `docs/validation/2026-10-06-indicf5-gpu-user-voices-e3683178.json`.
- Comparison receipt: `docs/validation/2026-10-06-indicf5-gpu-comparison-8ac83e12.json`.
- User preference: `docs/validation/2026-10-06-indicf5-gpu-user-choices.json`.
- Cleanup: `docs/validation/2026-10-06-indicf5-gpu-transfer-cleanup.json`.
- CPU isolation checks: `docs/validation/2026-10-06-indicf5-cpu-profiles-after-gpu.json`.

No production engine selection, delivery defaults, complete video result,
backend suite result, commit, push or release is claimed by this iteration.

## Completed longer-script update

The selected-settings long test completed with receipt
`docs/validation/2026-10-06-indicf5-gpu-user-voices-747ae53b.json` and log
`docs/validation/2026-10-06-indicf5-gpu-long-voices.log`. This supersedes the
running-test checkpoint above. Both cases retained the exact confirmed
references, guidance 2.0 and seed 42. Sujata used native speed 1.0; Abhishek
used 0.65. No post-generation tempo adjustment was applied.

| Voice | Output duration | Inference time | Listening LUFS / true peak | Torch peak GPU allocation |
| --- | --- | --- | --- | --- |
| Sujata | 8.096 s | 10.125 s | -18.76 / -1.55 dBTP | 1,492,942,848 bytes |
| Abhishek | 7.744 s | 8.250 s | -22.03 / -1.55 dBTP | 1,486,353,408 bytes |

The whole measured runner took 28.125 seconds after imports. All weights loaded
strictly; target/reference characters were supported. Finite/nonzero waveform,
native 24 kHz output, frame-preserving gain-only listening copies and complete
decoding passed. Abhishek's gain was peak-limited, so its integrated loudness
remains below the nominal target. No compressor or limiter was introduced to
force it higher. Its quieter level is documented, not silently represented as
meeting -18 LUFS.

Recordings are in
`docs/validation/2026-10-06-indicf5-gpu-user-voices-747ae53b/sujata-selected`
and the sibling `abhishek-selected` directory, each containing `raw.wav` and
`listening.wav`. Listening SHA256 values:

- Sujata: `50aee2f692d90814a921016bd8250a73f64115a2c09def01f157c56703d41963`.
- Abhishek: `ef50e2b199038285f5fa39072a23092b06db0c7502c2c9d43e6e41191f28b7a0`.

Human listening acceptance was subsequently declined for naturalness: the user
said, "they are good but on deep analysis they look more robo like". The exact
review is retained in `docs/validation/2026-10-06-indicf5-long-user-review.json`.
This supersedes the earlier pending-review status. Clear or pleasing short
speech and the C preferences do not establish natural longer delivery.
All generation/download/installation sessions in this iteration have finished,
and owned render workspaces were removed. GPU model execution is technically
verified; user-voice production integration and full video are still pending.

## Robotic-delivery investigation: controlled generation sweep

No new engine, package or framework was introduced. The isolated GPU diagnostic
runner gained a `--prosody` mode, requiring the verified `--selected` choices.
It tests one parameter at a time against the longer-script baseline: 64 rather
than 32 diffusion steps, or guidance 1.5 / 2.5 rather than 2.0. Seed 42,
confirmed audio/text reference pairs, target wording and native speed remain
fixed. Sujata stays at speed 1.0; Abhishek stays at 0.65. Guidance changes are
experiments, not a promised emotion control. More steps need not improve
expression. The receipt's top-level 32-step value describes the baseline;
each case's `nfe_step` is authoritative for this mixed-step sweep.

Execution receipt: `docs/validation/2026-10-06-indicf5-gpu-user-voices-87b036a9.json`.
Log: `docs/validation/2026-10-06-indicf5-gpu-prosody.log`.
Batch finished in 83.203 seconds after imports. All six cases completed strict
model/vocoder loading, finite/nonzero waveform checks, frame-preserving gain-only
listening-copy checks and full decoding. These are technical passes only.

| Voice / case | Steps | Guidance | Duration | Inference, rounded |
| --- | --- | --- | --- | --- |
| Sujata / steps64 | 64 | 2.0 | 8.096 s | 19.44 s |
| Sujata / guidance15 | 32 | 1.5 | 8.096 s | 9.09 s |
| Sujata / guidance25 | 32 | 2.5 | 8.096 s | 9.20 s |
| Abhishek / steps64 | 64 | 2.0 | 7.744 s | 16.94 s |
| Abhishek / guidance15 | 32 | 1.5 | 7.744 s | 8.38 s |
| Abhishek / guidance25 | 32 | 2.5 | 7.744 s | 8.67 s |

The comparison builder now accepts a verified baseline receipt and creates
A/B/C/D recordings. A is the previous longer take; B uses 64 steps; C uses
guidance 1.5; D uses guidance 2.5. It verifies source recording hashes, identical
text and per-voice reference identity, then concatenates exact PCM samples with
0.65-second silent gaps. It applies no additional gain, effects or tempo change.
Per-take constant gains from generation remain; levels are not perfectly
matched because of peak headroom. This may affect preference and should not be
mistaken for improved expression.

Comparison receipt: `docs/validation/2026-10-06-indicf5-gpu-comparison-4ce65b0d.json`.
Its sibling folder contains `sujata-ABCD.wav` (34.334 s) and
`abhishek-ABCD.wav` (32.926 s). Exact source hashes, parameters and segment
positions are preserved in this receipt; complete decoding and sample equality
passed. Human preference and naturalness acceptance are pending for this sweep.

## Alternate reference phrases prepared, not used

`dev/prepare_indicf5_alternate_references.py` prepares sample-exact 24 kHz PCM
slices from the previously decoded, hash-verified original recordings. Receipt:
`docs/validation/2026-10-06-indicf5-alternate-references-1f79a3cd.json`.
Sujata uses 10.82 seconds through the original end; Abhishek uses 6.00–13.65
seconds. Neither reference has gain, EQ or tempo processing. Stored transcripts
are explicitly unverified, ASR-derived wording, including spelling corrections;
they must be confirmed against these exact excerpts before conditioning.

The hypothesis is that reference phrase structure and expression may influence
the generated declarative passage. This is unproven. No synthesis has used the
new excerpts. A future reference comparison must also account for the engine's
duration estimate changing with reference length and transcript length; simply
changing references can otherwise confound expression with pace.

Production configuration is unchanged. The current release blockers remain
human naturalness acceptance, dedicated IndicF5 integration with verified
audio/text reference pairs, engine-specific timing, and complete video workflow
validation. All current GPU generation sessions have completed.

## Listening result for the controlled sweep

The user replied: "d in sujata but none in abhishek". Review receipt:
`docs/validation/2026-10-06-indicf5-prosody-user-review.json`.
Sujata D (`sujata-guidance25`) is preferred for this exact longer passage:
guidance 2.5, 32 steps, seed 42, native speed 1.0. This is a relative preference,
not explicit confirmation that the robotic quality is fully resolved or that
other passages will behave similarly. Preserve the earlier short C preference
as historical evidence rather than overwriting its scope.

All four Abhishek takes are rejected. Neither doubling steps nor these guidance
changes established acceptable naturalness. Do not select a least-bad take or
promote any Abhishek preset. The next bounded experiment is a different phrase
from the user's original recording, with exact transcript confirmation before
conditioning and explicit handling of reference-dependent duration estimates.
No additional tool or framework is needed. Defaults remain unchanged.

## Confirmed alternate Abhishek reference and duration control

The user answered "ok" to the presented alternate original excerpt and its
exact proposed transcript. This is recorded as transcript confirmation in
`docs/validation/2026-10-06-indicf5-alternate-abhishek-acceptance.json`, not
approval of generated delivery. Sujata's alternate transcript remains
unverified and is not used.

The diagnostic runner now has `--reference-comparison`, requiring selected GPU
settings and excluding the prosody sweep. Two Abhishek cases use the same long
target, seed 42, guidance 2.0 and 32 steps: the original confirmed reference as
control and the confirmed alternate reference. Both request 7.744 seconds of
generated speech (726 hops, 185,856 samples at 24 kHz). The engine's
`fix_duration` counts reference plus generated hops; the runner adds the
reference's floored hop count to the target hops plus one centered-vocoder frame,
then checks the output frame count exactly. A tiny numerical epsilon avoids floating-point truncation of the
requested total-hop count. No generated waveform is stretched or cut.

Native speed 0.65 is retained in the receipt, but explicit total duration
overrides the upstream text/reference speed-based duration estimate in these
two cases. Equal target duration does not force identical word timing. Equal
seed also does not produce identical noise tensors because reference lengths
change total sequence length. This comparison isolates overall duration, not
every internal variable or stochastic effect. A favorable result would still
need repeat-seed and another-passage checks.

Each reference requires unchanged audio hash and matching confirmed transcript;
alternate paths must remain inside the validation directory. The same strict
weights, vocabulary checks, serial GPU execution, gain-only preparation and
decode checks apply. No production route, package or framework is changed.

The initial reference comparison failed the exact frame-count gate before
publishing audio: `docs/validation/2026-10-06-indicf5-gpu-user-voices-7f89b674.json`.
It completed strict loading and the control inference, then cleaned its owned
workspace. The first calculation omitted the local Vocos head's centered ISTFT
convention: it returns `(mel_frames - 1) * 256` samples. Inspected local
`vocos/spectral_ops.py` and pinned `config.yaml` confirm centered padding. The
runner now asserts that head convention and requests one extra generated mel
frame. This corrects generation duration without adding waveform samples,
cutting audio or applying tempo processing. Future failures report actual and
expected frame counts. Retry log:
`docs/validation/2026-10-06-indicf5-reference-comparison-retry.log`.

The corrected retry completed successfully with receipt
`docs/validation/2026-10-06-indicf5-gpu-user-voices-7f1af934.json`.
Both outputs are exactly 185,856 samples / 7.744 seconds. The control took
8.734 seconds of inference; the alternate reference took 9.516 seconds. Total
runner time after imports was approximately 25.17 seconds.
Strict loading, supported text, finite/nonzero audio, gain-only frame equality,
unchanged reference hashes and full raw/listening decoding passed. Workspace
cleanup completed. Human naturalness review remains pending.

The control listening SHA256 is
`ef50e2b199038285f5fa39072a23092b06db0c7502c2c9d43e6e41191f28b7a0`,
identical to the previously presented longer baseline. This provides direct
evidence that the explicit-duration control reproduces that particular take.
The alternate listening SHA256 is
`9e1ed04107d58d7853ee58eb734e4b02be22181290d6db5c39ae13a734d5761d`.
Constant gains were -6.00 dB / -7.02 dB, respectively, limited by the same peak
headroom rule. The recordings are presented individually as original-reference
control and alternate-reference candidate. Neither is automatically accepted.

## Alternate-reference feedback and generalization check

The user replied "so better" to the alternate Abhishek recording. Review:
`docs/validation/2026-10-06-indicf5-reference-comparison-user-review.json`.
This establishes improvement for the exact presented passage; it does not
explicitly resolve every naturalness issue or approve release. The original
control remains rejected. The alternate reference is the next evaluation
candidate, not a production default.

The runner gained `--alternate-followup`, requiring selected GPU settings and
excluding other sweeps. It verifies the preferred case against its completed
generation receipt, listening hash and confirmed alternate reference hash.
It requires a different target passage, then tests seed 42 and seed 1234 with
the same reference, guidance 2.0, 32 steps and explicit 7.744-second target
duration. Keeping the prior duration is a controlled listening choice for this
similarly sized passage, not an automatic timing rule suitable for video cues.
The recorded native speed is 0.65; fixed duration overrides its duration estimate.

Target file: `docs/validation/2026-10-06-indicf5-followup-script.txt`.
Text: "यह रिपोर्ट तैयार है। पहले इसे ध्यान से पढ़ लीजिए, फिर हम अगले कदम पर
बात करेंगे। मुझे आपकी राय भी जाननी है।"
This is evaluation speech data, not an instruction to project execution.
Log: `docs/validation/2026-10-06-indicf5-alternate-followup.log`.
Two takes allow checking another passage and sensitivity to seed, with no new
package/framework or production changes. Human review must check full wording,
word boundaries, stutters, pacing and expression rather than pleasant timbre
alone. No claimed generalization follows merely from successful decoding.

The follow-up batch completed with receipt
`docs/validation/2026-10-06-indicf5-gpu-user-voices-0f148951.json`.
Both cases produced exactly 185,856 samples (7.744 seconds). Seed 42 took
10.141 seconds of inference; seed 1234 took 9.500 seconds. Batch time after
imports was 26.328 seconds. Strict weights, reference hashes, supported text,
finite/nonzero waveforms, exact fixed-duration output, gain-only preparation,
full raw/listening decoding and owned-workspace cleanup passed. Script syntax
was also checked without importing the heavyweight runtime. No broader
production test-suite result is claimed for diagnostic-only edits.

Listening SHA256 values:

- Take A / seed 42: `687d0af7321b95b3b48f622dc1ca1e7df62e7b8f8459783508dfe416f012f106`.
- Take B / seed 1234: `14d70e097726402f605ed2b8280671f28a2aac53ff35d741aa6a1aac77e94278`.

Constant gains are -6.88 / -5.51 dB, respectively, under the existing peak
headroom rule; no compressor, EQ or post-generation tempo change was applied.
Human naturalness and full-wording review is pending for these exact takes.
All generation sessions are finished. Production defaults remain unchanged.

## Preferred B follow-up and extended-passage evaluation

The user chose B for the second three-sentence passage. Receipt:
`docs/validation/2026-10-06-indicf5-followup-user-review.json`.
That take used the alternate confirmed Abhishek reference, seed 1234,
guidance 2.0 and 32 steps. This remains an exact-passage preference, not
full-video or release acceptance. The user's subsequent "ok" authorized the
proposed longer-passage check.

The diagnostic runner now supports `--long-followup` with
`--alternate-followup --selected --gpu`. It verifies the B choice against its
completed receipt, listening hash and reference hash. A single continuous
six-sentence passage is supplied from
`docs/validation/2026-10-06-indicf5-extended-script.txt`. Its wording is speech
test data, not project instructions. Selected B settings are preserved.

Requested output duration scales 7.744 seconds by the UTF-8 byte-length ratio
of the new text to the B passage, then rounds to the nearest 256-sample hop.
This follows the local engine's text-length duration heuristic while preserving
the recently preferred pace calibration. It is an estimate, not a claim of
measured syllable rate, natural phrasing or correct video timing. Explicit
duration again overrides speed 0.65's native estimate; no post-generation
stretching or cuts are applied. The runner rejects totals above the model's
4096-frame limit instead of allowing its internal duration clamp to silently
shorten output. All prior strict loading, reference integrity and frame-count
checks remain. No production changes or new dependencies are introduced.

Log: `docs/validation/2026-10-06-indicf5-extended-followup.log`.
Human review must check the full passage, especially the final two sentences,
for word loss, language drift, unnatural gaps, stutters and robotic delivery.

The extended test completed with receipt
`docs/validation/2026-10-06-indicf5-gpu-user-voices-9af33aa8.json`.
Output is 25.376 seconds / 609,024 samples at native 24 kHz. Inference took
28.578 seconds; total measured runner time after imports was 38.765 seconds.
Torch peak GPU allocation was 1,583,331,840 bytes, not total driver VRAM.
Seed 1234, guidance 2.0, 32 steps and the confirmed alternate reference were
retained. Both raw and listening files fully decoded; exact output frame count,
finite/nonzero waveform, unchanged reference and strict weight checks passed.
Owned workspace was removed. Script syntax was checked independently.

Listening preparation used constant gain -8.54 dB, with -21.99 LUFS and
-1.55 dBTP measured afterward. Peak headroom prevents reaching the nominal
-18 LUFS target; no compressor or limiter was added. Listening SHA256:
`597acc758646fc53b2d5eeff9f3f826939d86d111bce91b2ecd08271a3e2a0b2`.
Raw SHA256:
`0589941430a5cbfb561d4c30b93e85d18d9fcfc35ccec70af2ba0240adaff080`.
Full wording, absence of stutters and sustained natural delivery await human
review of this longer take. Successful decoding alone does not verify speech
content. All inference sessions have finished; production defaults and full
video release status are unchanged.

## Extended passage failed intelligibility; sentence-wise diagnostic

The user rejected the continuous passage: "no... not natural throughout... but
was good during 2- 15 sec... before and after that words are gibberish".
Review: `docs/validation/2026-10-06-indicf5-extended-user-review.json`.
The reported time ranges are approximate listener observations, not aligned
word timestamps. The result fails intelligibility as well as naturalness.
Do not repair the report by retaining only the good middle or promote it as an
accepted paragraph. The failure's cause is not established: longer sequence
generation, local timing estimates and reference conditioning remain possible
contributors. Technical waveform integrity did not guarantee correct speech.

Next diagnostic: generate the exact same six sentences independently with
`--segmented-followup --long-followup --alternate-followup --selected --gpu`.
The runner requires exactly six sentences and reconstructs their joined text
to verify unchanged wording. Reference, seed 1234, guidance 2.0 and 32 steps
remain fixed; model and vocoder load once and generation stays serial. Sentence
target durations divide the paragraph's 25.376-second hop budget by UTF-8 text
length. Largest-remainder allocation preserves the total 2379 target hops;
each sentence retains the centered-vocoder compensation and exact frame check.
This heuristic can still misallocate word time, so successful completion is
not a naturalness pass. Shorter independent generations change both sequence
length and local timing, so this is a practical bounded comparison, not proof
of a single root cause.

Log: `docs/validation/2026-10-06-indicf5-segmented-followup.log`.
`dev/assemble_indicf5_sentence_review.py` builds a paragraph from completed,
hash-verified sentence listening files in order with 0.20-second silent gaps.
It checks exact text, mono 24 kHz format, frame counts and sample equality,
then fully decodes the assembly. No audio words are trimmed, no crossfade,
post-tempo, extra gain, compressor or EQ is added. Individual generation
listening gains may differ by sentence; transitions therefore require review.
No new package/framework or production change is involved.

Sentence generation completed successfully with receipt
`docs/validation/2026-10-06-indicf5-gpu-user-voices-fbf9cf81.json`.
All six exact-frame, strict-weight, reference-integrity, finite/nonzero waveform,
gain-only listening and full decoding checks passed. Total runner time after
imports was 59.203 seconds; individual durations / inference times:

| Sentence | Output seconds | Inference seconds |
| --- | --- | --- |
| 1 | 3.477333 | 8.875 |
| 2 | 4.960000 | 7.578 |
| 3 | 4.330667 | 7.266 |
| 4 | 5.781333 | 8.468 |
| 5 | 3.232000 | 6.500 |
| 6 | 3.594667 | 6.922 |

Their speech durations total exactly 25.376 seconds. Assembly receipt:
`docs/validation/2026-10-06-indicf5-segmented-listening-5e24a3c2.json`.
Five 0.20-second gaps produce a 26.376-second, 633,024-sample paragraph.
Sample-exact concatenation, full decoding and owned-workspace cleanup passed.
Assembly SHA256:
`d076483aa44aaba4b2f7be0c3bd20603c6a9abf974d58e1341ac0bf37417c67f`.

The assembler's final console print initially raised a Windows cp1252 Unicode
error after the completed audio, receipt and cleanup were already written.
The complete receipt was inspected to distinguish logging failure from media
failure. Console JSON output now escapes non-ASCII characters; UTF-8 receipt
content is unchanged. Assembly was not unnecessarily regenerated. Diagnostic
scripts were syntax-checked. This paragraph still requires human intelligibility
and naturalness review; no result is inferred from technical checks alone.
All inference sessions have finished. Production remains unchanged.

## Accepted segmented Abhishek result and video-cue preparation

The user replied "no, it's quite clear and natural... actually good" to the
sentence-wise paragraph. In context this confirms clarity/naturalness, rejecting
the prompted concerns about gibberish, stutters and transitions. Acceptance:
`docs/validation/2026-10-06-indicf5-segmented-user-acceptance.json`.
It applies to the exact 26.376-second assembly and its recorded hash. The
continuous 25.376-second failure remains rejected; other wording, actors,
automatic timing and video are not accepted by this response.

The user then approved proceeding to video validation. Code inspection confirms
that `_dub_segment_bound` currently applies Hindi tempo 1.342 even to speech
that would be generated with a different engine. Applying it to these native
IndicF5 candidates would change accepted delivery. A dedicated engine-aware
timing/mastering path and verified reference-pair route remain needed before
claiming production integration. No default has been changed.

The retained 2026-10-04 real-video cue report also contains unsuitable recognition
and translation drafts: misrecognized English phrases, literal/awkward Hindi,
English fragments and a final cue extending beyond the 44-second excerpt.
Generating polished speech for those drafts would compound upstream errors.
They remain historical failure evidence, not approved source text.

`dev/prepare_indicf5_video_cues.py` now prepares fresh offline drafts from
`Sample/2.mp4`'s first 44 seconds. It hashes the original, extracts mono 16 kHz
audio with existing FFmpeg, runs the existing local Whisper-large-v3-turbo on
the verified GPU runtime using direct feature extraction/model generation,
and then the existing local NLLB adapter for English-to-Hindi translation.
No tools, packages, models or frameworks are newly installed. Recognition and
translation run sequentially, releasing the recognition model before translation.
The recognizer's decoder hook checks cancellation; core translation generation
uses existing cancellation controls. Models use local-files-only/offline mode.

Recognition uses contiguous up-to-30-second blocks, English language hint and
deterministic decoding. Block-edge phrasing and timestamps still require review;
these are not word-level alignments. Every emitted phrase must have finite,
in-range, increasing start/end values and nonempty text. Missing timestamps fail
preparation. The script checks the original source hash afterward and publishes
unique receipts, raw recognition blocks, timed source cues and translated drafts.
Human source/translation review flags remain false until checked. The retained
decoded source audio permits direct comparison. No video is rendered by this
preparation step, and no full-pipeline pass is claimed.

Preparation log: `docs/validation/2026-10-06-indicf5-video-cues.log`.

Initial preparation stopped during recognition because model weights loaded as
half precision from their configuration while extracted input features remained
float32. The runner now explicitly casts floating audio features to the model's
actual dtype and records that dtype; integer attention masks remain unchanged.
This is a diagnostic input compatibility correction, not an installation or
change to IndicF5 voice precision. No recognition or translation output from
the failed attempt is accepted. Its receipt preserves failure and workspace
cleanup. Retry log: `docs/validation/2026-10-06-indicf5-video-cues-retry.log`.

The corrected preparation completed with receipt
`docs/validation/2026-10-06-indicf5-video-cues-dc446977.json`, twelve source and
translated phrases, and 29.469 seconds measured after imports. Original source
hash and cleanup checks passed. Recognition used configured `torch.float16`.
Content review found residual recognition ambiguity, fragment-based translation
failures, dropped meaning, misinterpreted film vocabulary/profanity and a
fixture ending mid-sentence. These drafts are not approved speech input.
Detailed evidence and explicitly labeled editorial proposals are in
`docs/INDICF5_VIDEO_TEXT_REVIEW_2026-10-06.md`. No full video was rendered from
these unsuitable drafts. All preparation/inference sessions are finished.
