# ReFlow product readiness after architecture repair

Status: in progress. The user chose **translation and voice quality first**.
Current release verdict: **not ready for a public fully featured release**.
See `RELEASE_READINESS_2026-10-04.md` for the current gates and release scope.
The user dropped the 500 MB target on 2026-10-04 and asked
for an exceptional, distinctive product. This document separates verified
capabilities from product gaps. It makes no unsupported competitor comparison.

## What is working and evidenced

| Capability | Current evidence | Practical limit |
| --- | --- | --- |
| Subtitle translation | Actual offline NLLB workflow; cue timings retained; eight-case decoding comparison improved the isolated greeting with five beams | Production now uses five beams; broader semantic quality remains unaccepted |
| Audio dubbing | Bounded single-voice continuation grouping lets the first complete news sentence pass automatic speech/timing; guards refuse to cut audible words | Eight-second rerun fails recognition bounds; fifteen-second run fails cue two (3.143 s needed, 2.720 s available). Recognition correction and cue regeneration remain necessary; first-cue fit is not quality acceptance |
| Video dubbing with visual stages | Earlier eight-second Wav2Lip/GFPGAN/NudeNet chain decoded all 40 frames and retained subtitles/stems | Evidence predates new speech timing/loudness changes; current full chain, moving faces, occlusion and multiple speakers unverified |
| MuseTalk | Fresh one-second offline five-frame acceptance | Every frame currently requires a detectable face; quality unreviewed |
| F5 voice generation | Explicit and automatic-reference acceptance; two automatic-reference requests used one worker and one transcription, then cleaned up | CPU latency is substantial; human quality unreviewed |
| Cancellation | Job-owned cleanup and output preservation; actual XTTS token stop in 0.11 s | One tensor operation/model loading is not instantly interruptible |
| Nodes | Ten rendered nodes; common submitted parameters; mute/template regressions checked | Fixed pipeline order; extra voices alternate segments; no speaker identification or arbitrary DAG execution |
| Model recovery | Pinned sources, integrity checks, owned storage, transactional installation, offline/error/cancellation checks | Live marketplace services and every user-supplied model require their own acceptance |
| Portable Windows desktop | Own copied Python, all six pages, bridge/library checks, no captured JavaScript errors | Automated acceptance; manual layout and Linux/macOS unverified |
| Regression checks | 487 backend checks pass after accepted tempo repair; retained 83 frontend checks and build (frontend unchanged) | Fixtures cannot establish real media quality or all hardware support |
| Speech tempo quality | Bundled Rubber Band replaces atempo; both Hindi controls user accepted, production reproduces exact approved PCM; acceleration/slowing pitch and cancellation checked | Other passages/languages and combined generation/mastering need quality acceptance; alternate FFmpeg builds must include the filter |
| Current real-video dubbing | Actual44-second Sample2 with separation/subtitles/supplied Hindi reference reached9 translated cues; first speech cue fits | Failed cue2 needs3.011s/2.600s; recognition/translation/context/boundary issues; no final mix/mux or full video acceptance |
| Cue correction and review | Dashboard single-voice audio review: edit source/translation, retranslate, audition/regenerate, accept fitting takes and assemble exact saved audio | Video/multi-speaker/timing editing and human quality acceptance remain open; invalid recognition bounds can prevent preparation |

The detailed ledger and receipts are in `ARCHITECTURE_ITERATION_2026-10-03.md`
and `validation/`. No release, commit or push was performed.

## The most important quality gap

Dashboard now includes a single-voice audio review workspace to correct text,
audition/regenerate cues and reuse accepted takes. It is bounded to audio; video
and multi-speaker review remain missing. Automatic jobs can still faithfully
synthesize an incorrect translation. NLLB translated the isolated greeting “Good morning.” into Hindi
“शुभ दोपहर.”, changing morning to afternoon. M2M100 also produced a semantically
incorrect greeting in its recorded acceptance. Five-beam NLLB corrected that
isolated greeting in the comparison corpus; this is a narrow improvement, not
human acceptance of the translations. Replacing a model or adding more
packages does not by itself establish quality across accents, languages and
domain terms.

A proposed review workflow would show source audio/video, timed source text,
translation and assigned voice together; allow text/timing/voice corrections;
audition individual cues; and regenerate only changed cues before final mixing.
It must preserve original/generated/user-edited text separately and invalidate
dependent audio when text, voice, reference, language or timing changes. This is
a product proposal, not an implemented feature or permission to add a framework.

## Work that would make the current foundation stronger

1. **Quality acceptance corpus.** Use authorized source media with reviewed text
   and translations. Cover accents, quiet speech, music, overlapping speech,
   language changes, names/numbers, domain terms and long cues. Review cloned
   voice similarity, intelligibility, clipping and duration fit; review visual
   sync and artifacts with moving/occluded faces. Preserve failures alongside
   passes. Do not treat a nonempty response or playable file as semantic success.
2. **Credible resource guidance.** Current estimates are explicitly uncalibrated
   heuristics. Add measured workload history before promising elapsed time;
   distinguish download/setup from inference and mixing. Measure worker-inclusive
   RAM/VRAM and define safe admission policies for actual devices. Current audio
   buffer estimates exclude model memory and cannot prevent all memory pressure.
3. **Useful parallelism.** Current workers overlap preparation/mastering while
   sharing inference safely. Benchmark independent-model concurrency with a
   memory budget before enabling simultaneous heavy engines. The prior F5/video
   overlap demonstrated why a worker count alone is insufficient scheduling.
4. **Truthful Nodes.** Keep the existing fixed order clear. Arbitrary branches,
   preview nodes, dependencies and resumable intermediate artifacts require
   an execution graph and typed artifacts, not additional decorative nodes.
5. **Engine and platform completeness.** Obtain an authorized RVC checkpoint for
   real conversion acceptance. Test configured cloud vendors with credentials,
   actual contracts and media. Run clean relocated builds on Linux and macOS;
   validate GPU routes on hardware that has those backends. Unavailable features
   should explain their prerequisites instead of appearing ready.

## Latest listening feedback and correction

The user reported low playback volume and slow Hindi delivery. Voice mastering
now uses the existing FFmpeg for measured loudness adjustment targeting -14 LUFS
and -1.5 dBTP, with validation and atomic publication. Short cues without a gated
measurement use peak normalization; final mixed-output loudness remains to be
verified. No new tool or package was installed.

Retained comparison previews measure -14.39 LUFS / -1.47 dBTP for English and
-14.44 LUFS / -1.29 dBTP for Hindi. Hindi's preview uses pitch-preserving 1.1x
tempo; the user accepted its volume and preferred its pace, but still found the
last word drawn out. On further listening the user identified unnatural voice
delivery as the underlying concern, rather than speed. Naturalness is rejected
for the presented previews; volume acceptance does not imply voice acceptance.
Ending acceleration remains an experiment and is not promoted into production.
At that stage the production speech-rate default remained unchanged.
The user heard no improvement when EQ/compression/tempo changes were bypassed.
This makes generation/reference quality the leading investigation; it does not
prove one specific model setting is responsible. A fresh controlled XTTS
comparison is testing the current settings, lower sampling temperature, and
sentence splitting disabled, with the same Hindi text/reference/seed and no
tempo change. Production settings stayed unchanged during these comparisons.
The offline comparison completed in 142.719 s. Baseline/unsplit raw files were
identical for this text, ruling out that toggle as an improvement for this
example. Lower temperature produced a different, slightly longer candidate;
its naturalness awaits listening review. No setting was promoted to production.
Latest detailed review supersedes the blanket diagnosis: the greeting, pause
and main Hindi phrase sound good to the user; only the stretched final `है`
feels unnatural. The three-second whole-line preview was too fast. A retained
ending-only diagnostic preserves the first 2.872 s of the moderate preview
exactly, then accelerates the approximate final-word region. Its boundary is
unverified and listening acceptance is pending; it is not a production feature.
The user subsequently preferred the ending-edited preview with an additional
22% whole-line tempo increase, describing it as "much much better". This 3.129 s
clip is the retained listening target. It combines a manual approximate ending
edit and whole-line acceleration; a global 1.22x default alone would not
reproduce it. Broader Hindi naturalness and longer-line acceptance remain open.
Two longer Hindi passages have now completed offline generation and playback/
duration validation: 5.778 s and 6.685 s after the comparable overall 1.342x
pace adjustment. Their endings were left unedited, including a final `है` in
the second passage. Raw/original-pace files are retained. The user approved both
(`so good`) and explicitly authorized applying their pace to Hindi dubbing.

Production Hindi dubbing now uses the approved 1.342x tempo after mastering,
preserving pitch, retaining cue pauses and refusing to cut audible words. It
does not slow Hindi speech to fill unused cue time or accelerate beyond the
reviewed pace to force a fit. Other languages retain their prior timing behavior.
The manually estimated ending edit from the short clip is not generalized.
This policy applies to shared audio/video dubbing for resolved Hindi, across
voices; actual listening evidence covers the recorded XTTS/reference samples.

Replaying retained real XTTS audio through the production segment path reproduced
both approved longer clips exactly in PCM and audio format. The replay did not
rerun synthesis. Targeted checks passed 61 tests in 20.848 s. The portable QA
application was refreshed with 167 files and no size mismatches. Full news-dub
acceptance remains open: the earlier line-fit failure requires its own resolution
and is not closed by this pacing integration. Final full backend verification
passed 463 checks in 73.201 s; no commit, push or release was made.

The failing news sentence has since been reviewed with longer source context.
Recognition corrected `Before long` and exposed a continuation split across
cues. Complete-context NLLB and a proposed concise manual translation now fit
the complete source-sentence window in 6.009 s and 5.030 s respectively. The
concise version has a retained background-mix preview. Source/translation/mix
listening acceptance is pending; no production grouping or translation rule
was changed. This manual unit review does not certify the unchanged automatic
workflow. Details: `TRANSLATION_TIMING_REVIEW_2026-10-04.md`.
The user confirmed no audible original English in that mix, but rejected its
choppy final words. Two fresh generation candidates now fit (4.839 s / 5.030 s)
and await listening review. An actual alternative exposed a mastering true-peak
excess; gain-only correction plus remeasurement now handles that finite excess
without changing timing or weakening rejection. Full regression validation:
464 PASS in 82.713 s. The user accepted the 4.839 s fresh-reading candidate;
that exact audio is retained in a selected background-mix preview. Acceptance
is specific to that voice reading; its final mix and broader model naturalness
remain separate review gates. No production seed/translation policy was changed.
The user then clarified that the excerpt contains no music or ambient sound.
The residual separator stem was incorrectly described as such. For this unit,
the selected mix is superseded by the exact accepted voice plus digital silence
to its original sentence boundary; no residual track is added. General project
background settings/features remain unchanged. This correction is documented in
the detailed sentence review and its voice-only receipt.
Original samples are preserved. These measurements establish level/peak
behavior, not naturalness, intelligibility or user acceptance.

An earlier backend suite passed 460 checks in 61.020 s; focused loudness,
mastering and speech checks passed 56 in 17.391 s. The owned portable QA copy
was refreshed with 167 application files and no size mismatches. Frontend
evidence is retained from the earlier unchanged build. The real audio timing
failure above remains an open product gate despite these regression passes.

## Proposed product emphasis

Build around a controllable local dubbing workflow: reviewable intermediate
results, per-cue voice control, synchronized previews, reliable stems, traceable
model selection and cancellation/recovery that preserves work. These are concrete
product directions based on the existing architecture. Distinctiveness and
market position need user/workflow validation; they are not proven by the current
test count. New engines, tools and frameworks still require the user's approval.

Core-size reduction is no longer a requirement. Preserve useful offline engines;
continue removing confirmed generated/redundant files and report setup/model disk
requirements accurately. The withdrawn small-core proposal remains historical
analysis only.

## Latest follow-up: XTTS native playback rate

The local checkpoint loader mislabeled24000-Hz decoder samples as22050-Hz WAVs.
The application now uses the actual loaded decoder rate, preserving custom rates
and CPU recovery. Full backend490 PASS124.375s; portable QA168 files/no size
mismatches. Native-rate voice comparisons are pending human listening. Seeded
cleaned-reference repeats match exactly, but3.943s still exceeds2.600s; an
unprocessed-reference control4.944s also fails. This repairs pitch/duration
metadata, not the complete dubbing workflow. Previous evidence above remains
historical. See `XTTS_PLAYBACK_RATE_REPAIR_2026-10-04.md`.

## Accepted Hindi decoding and processing integrated

Raw greedy coverage and its normalized/tempo-processed copies pass user listening
on four exact Sujata/Abhishek question/meeting takes. Hindi local XTTS now uses
greedy selection; clonedHindi mastering uses loudness-only processing. All493
backend checks pass93.946s, four segment outputs match accepted PCM and a fresh
actual XTTS adapter/segment inference matches approved raw/final data. QA168files
refreshed without mismatches. See `HINDI_QUALITY_PRODUCTION_2026-10-04.md`.
This closes the decoding/processing runtime gap, not complete-video or universal
voice quality. Automatic reference preparation/cue fitting/semantics/full video
and remaining release gates still require validation.

