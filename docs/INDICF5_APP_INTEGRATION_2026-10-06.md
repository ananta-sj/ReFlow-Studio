# IndicF5 backend integration — October 6, 2026

## Evidence permitting this integration

The user described the exact 52-second Hindi review video as "it's actually
quite good...". Its positive overall listening acceptance is recorded in
`docs/validation/2026-10-06-indicf5-video-user-acceptance.json`. That scope is
the reviewed Hindi/Abhishek fixture, not arbitrary translation, actors or
release. The prior rejected long continuous take remains rejected.

No new model, framework, external tool or package is introduced here. This
integration reuses the already approved isolated IndicF5 runtimes, official
local weights, confirmed reference audio/text and accepted generation settings.
User model connections/default selections have not been rewritten.

## Implemented backend route

`core/model_contract.py` now recognizes `model_type=inf5` with exact
`architectures=[INF5Model]` for a TTS entry, requiring the local safetensors
checkpoint and vocabulary. It returns a separate IndicF5 identity and Hindi
capability rather than treating those weights as XTTS or generic F5 v1 Base.
No `auto_map`/remote Python from model configuration is executed.

`core/providers/resolve.py` selects `IndicF5TTSProvider` from that contract.
A local TTS entry must provide `meta.reference_profile`: a reviewed reference
profile path. `core/speech_language.py` preflight validates Hindi and that
profile; other targets and RVC substitution are rejected for this route.
Existing XTTS configuration/language checks are retained. Generic F5 voice
entries still use their separate contract and runtime.

`core/providers/tts/indicf5_local.py` validates a versioned reference profile,
audio hash, confirmed-reference flag, transcript, pace calibration, seed,
guidance, step count and sentence gap. Selected input audio must match either
the original confirmed-source hash or the conditioned excerpt's hash. Different
audio cannot silently reuse the transcript. No reference ASR, cleaning or
model download is invoked during synthesis.

The confirmed Abhishek excerpt was copied, not moved, to
`models/indicf5/references/abhishek/reference.wav`; the same SHA256 was checked.
Its `profile.json` contains the matching transcript and preferred B calibration:
seed 1234, guidance 2.0, 32 steps, 0.20-second sentence gaps and the exact
7.744-second calibration passage. Original MP3s and validation files remain.
The profile is tied to this accepted voice, not a general cloning-quality
guarantee. Changed/custom profiles require their own listening review.

The provider selects the existing isolated GPU or CPU evaluation interpreter
according to the requested device. GPU metadata must be verified; the worker
also checks actual CUDA availability, torch version/origin and f5-tts version.
The CPU path checks its actual supported torch/package versions at worker
startup, but the new CPU provider path has not been timed or human-accepted
in this iteration. Existing evaluation CPU speech evidence is historical.
Platform/profile packaging still requires release validation.

`core/feature_session.py` accepts an explicit worker operation while preserving
the generic F5 default. IndicF5 uses its own `core/indicf5_worker.py` and session
identity. Sessions belong to a render job, calls are locked, failure diagnostics
propagate, timeout/cancellation use existing owned-process controls, and cleanup
closes the worker. One model is reused across cue calls. Explicit release after
speech prevents its isolated GPU allocation persisting into lip-sync/enhancement.

The dedicated worker requires isolated f5-tts 0.1.0 and the tested torch runtime.
It strictly accounts for all 447 safetensors: 364 speech and 83 vocoder tensors.
The matching small Vocos architecture configuration is stored as
`core/indicf5_vocos.yaml`; it describes the tested architecture and does not
download vocoder weights. Trained vocoder weights come from the IndicF5 checkpoint.

Short sentence units preserve text and reset the selected seed. Requested
duration follows the accepted calibration's UTF-8 byte ratio, rounded to mel
hops, with the centered-vocoder extra-frame compensation. Totals above the
4096-frame model limit fail instead of silently clipping. Outputs must be
finite/nonzero native mono 24 kHz, exact expected frame count, and gain-only
PCM preparation targeting -18 LUFS while protecting -1.55 dBTP. Short ungated
speech uses finite true peak rather than claiming a measured LUFS result.
Sentence joins insert only the configured digital silence. Full decoding and
unchanged reference checks precede staged publication.

## Pipeline changes preserving accepted speech

Both audio/video paths detect IndicF5's exact-reference requirement and retain
the supplied original/confirmed reference instead of automatically cleaning it.
The provider verifies it against the selected profile and conditions on the
confirmed excerpt. Other engines keep existing cleaning behavior.

For cloned IndicF5 speech, `_dub_segment_bound` skips extra mastering and sets
post-generation speed to 1.0. The provider already applies the reviewed gain
recipe. XTTS's earlier Hindi 1.342 adjustment is retained for its existing
route. Audible cue overflow still fails with segment context; no faster tempo
or word truncation is silently substituted. Non-cloned/RVC routes do not inherit
the new native-delivery policy. Video and audio paths release the IndicF5 worker
when their speech work is complete, including before later video stages.

## Regression verification and discovered console failure

`dev/test_indicf5_integration.py` adds eight checks covering separate resolution,
missing/wrong assets, reference mutation/unconfirmed profiles, invalid generation
fields, Hindi-only capability, foreign-reference rejection before worker startup,
native mastering/tempo preservation and audible-overflow refusal/cleanup.
Related existing speech integrity, language, parallel speech, feature sessions,
cancellation and model contracts were run together: **129 tests passed** in
37.532 seconds on the successful run. Log:
`docs/validation/2026-10-06-indicf5-integration-tests-retry.log`.

The first combined run encountered eight existing RVC failures caused by status
emoji printing to a Windows cp1252 stream. `core/rvc/rvc_handler.py` now uses
ASCII status markers for initialization, ready and conversion messages. This
prevents status output from failing speech operations; RVC model/conversion
behavior is unchanged. The original failing run (129 tests, eight errors) is
retained in `docs/validation/2026-10-06-indicf5-integration-tests.log`.

## Real provider verification

`dev/verify_indicf5_app_provider.py` uses the actual resolver/provider, confirmed
profile, isolated GPU worker and two native utterances from the accepted-video
generation. It does not substitute a fake speech model. Both PCM sample arrays
and rates match the previous candidate exactly, despite different WAV container
headers. One worker PID served both calls, explicit release passed and owned
workspace cleanup passed. User registry/defaults remained untouched.

Receipt: `docs/validation/2026-10-06-indicf5-app-provider-0c692499.json`.
Log: `docs/validation/2026-10-06-indicf5-app-provider.log`.
Measured total after helper imports: 145.203 seconds, including parent/provider
lazy imports, isolated worker startup/loading, two calls and release. This is
not the 12-second warm inference time or a calibrated universal startup estimate;
other regression work ran concurrently. It must not be used to advertise a
fixed per-cue latency.

## Actual video pipeline validation completed

`dev/verify_indicf5_app_video.py` runs the normal `video_dub` pipeline with the
real IndicF5 resolver/provider, user-reference path, cue synthesis, timing,
mix timeline, subtitles and final publication. A private fixture registry avoids
changing user connections. Source recognition and translation are deliberately
the previously reviewed fixtures, since raw automatic NLLB text failed meaning
checks. This test does not claim live ASR or automatic-translation acceptance.
Background is disabled in this first integration check. Log:
`docs/validation/2026-10-06-indicf5-app-video.log`.

The test requires eight generated cues, one reused worker, explicit release,
52-second timeline, video/audio/subtitle streams, full decoding, original source
hash preservation and owned-workspace cleanup. All these checks passed in
`docs/validation/2026-10-06-indicf5-app-video-70d9ba1c.json`. The retained output is
`docs/validation/2026-10-06-indicf5-app-video-70d9ba1c/outputs/source_DUBBED_HI_b9127a40ca30.mp4`.
Measured time after helper imports was 176.734 seconds; the pipeline's own timer
reported 2 minutes 31 seconds. These timers have different starting points.

`docs/validation/2026-10-06-indicf5-app-pcm-equivalence.json` independently compares
all eight generated cue sample arrays to the reviewed diagnostic material. Every
cue matches exactly. The complete assembled track also matches exactly: 24 kHz,
1,248,000 frames, 52 seconds, with no extra tail. Thus backend integration
preserves the accepted delivery before AAC encoding. This is sample equality,
not a claim that WAV headers or MP4 files have identical bytes. The app render
has not received a separate human listening reply; the human acceptance belongs
to the original diagnostic video, whose underlying voice track is reproduced.

After stronger profile hash validation and checkpoint/vocabulary cache identity
checks, 20 targeted RVC/IndicF5 checks passed in 4.503 seconds. This includes a
successful RVC initialization with a cp1252 console and mocked engine/assets,
and rejection of malformed reference hashes. Log:
`docs/validation/2026-10-06-indicf5-rvc-console-checks-retry.log`.
The preceding targeted run failed because its asset mock did not intercept a
module import after earlier test-module replacement. It attempted an asset
download, which failed DNS resolution. The test now supplies the imported asset
module explicitly; it performs no download. The failed log is retained as
`docs/validation/2026-10-06-indicf5-rvc-console-checks.log`. This was a test-isolation
repair, not a runtime network permission or an installed dependency.

Remaining product work includes user-facing profile selection/reference
confirmation, portable-runtime setup/readiness, background preservation, translation
review feeding the render, calibrated resource estimates, other material and
release-platform checks. Backend routing is not equivalent to a finished UI or
release-ready app.
