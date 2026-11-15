# Language rollout and NLLB's role

## What is being validated now

The immediate acceptance target is a reliable English-to-Hindi video workflow.
The product goal remains multilingual dubbing, with other supported source and
target languages. “Any language to Hindi” is not an established capability:
recognition, translation and speech generation all need support and real tests.

Hindi leads because it is the user's current priority and has exposed quality
failures. Good individual recordings did not generalize to the failing video
line. A complete English-to-Hindi video has not yet passed the current workflow.
Earlier English clips sounded good to the user, but that also does not certify
all English video workloads.

## The models do different jobs

| Stage | Input and output | Role in the tested local workflow |
| --- | --- | --- |
| Speech recognition | Original audio → words and timestamps | Whisper |
| Translation | Original words → target-language text | NLLB local provider |
| Speech generation | Target text + voice reference → spoken audio | XTTS; IndicF5 is being evaluated |
| Timing and assembly | Spoken cues + source media → final video/subtitles/stems | ReFlow pipeline and FFmpeg |

NLLB translates text; it does not produce voice audio or clone a speaker. It is
already used in the isolated local video validation. Other configured routes
exist, so this is not a statement that every application configuration selects
NLLB automatically.

The diagnostic Hindi sentence `मेरे पास यह रिपोर्ट है।` was supplied directly
to the speech model, with correct Hindi token routing. The user rejected its
audio as non-Hindi/unintelligible. No fresh translation was involved in those
isolated tests. Replacing the translator cannot repair that particular failed
recording. Conversely, fixing the speech engine cannot repair a mistranslated
sentence or incorrect source recognition.

## Where NLLB still needs quality work

The retained video has uncertain English recognition, literal Hindi translations
and thoughts split across cues. Improve source transcription and review complete
sentences before evaluating translations. Preserve meaning and tone, then assign
the reviewed text to sensible timing windows. Never shorten away meaning or cut
speech merely to get a render through its duration guard.

The implemented NLLB adapter loads a fixed sequence-to-sequence translator. It
validates source/target language tokens and does not accept custom translation
instructions. Instructions such as “make it conversational” or “use a formal
tone” require a different supported route or an explicit review/editing stage;
they cannot simply be added as a prompt to this NLLB adapter.

Translation languages and speech languages are separate capability lists. The
app's language menu is not a guarantee that every engine can translate and speak
every listed language. Unsupported exact routes should be rejected rather than
silently substituting a related language or script. Hinglish and Punjabi script
variants particularly require explicit treatment.

## Why evaluate IndicF5

XTTS currently reproduces a previously accepted Hindi question exactly, but also
reproduces a rejected sentence exactly. Reference substitution, punctuation
controls and bounded repetition changes have not demonstrated a reliable repair.
That is a speech-generation reliability problem, with its underlying mechanism
still unresolved.

IndicF5 is a separate candidate, not a replacement for NLLB. Its official
documentation lists Hindi among 11 Indian languages and requires reference
audio plus an accurate transcript of that reference. The user approved an
isolated evaluation. It has not been integrated or accepted for production.
Other engines can remain useful for other targets if their tests pass.

[Official IndicF5 documentation](https://github.com/AI4Bharat/IndicF5/blob/main/README.md).

## Recommended rollout

1. Validate Hindi speech across both user voices, varied wording, negation,
   longer passages, pronunciation and naturalness.
2. Complete an English-to-Hindi video with meaning, cue fitting, subtitles,
   background preservation, no residual original dialogue and final listening.
3. Test selected additional supported source languages into Hindi. A good Hindi
   voice does not establish source recognition or translation accuracy for them.
4. Validate additional output languages, beginning with English and then a
   user-selected priority set. Choose a speech engine per language based on
   evidence rather than forcing one engine to cover everything.
5. Expand the acceptance matrix: voice, source/target language pair, text style,
   speaker count, material length, hardware and actual application workflow.

Recognition, translation infrastructure, review, job handling and media assembly
are reusable. Language-specific models, exact scripts, pronunciation, voice
identity, delivery and human meaning/listening checks still need individual
validation. Wider platform, install and optional-feature acceptance remain
separate release gates.

## Relevant implementation and evidence

- `core/providers/translation/nllb_local.py`: actual NLLB text translation.
- `core/languages.py`, `core/source_language.py`: exact translation routes.
- `core/speech_language.py`: separate speech support checks.
- `core/pipeline.py`: recognition/translation/generation/assembly stages.
- `docs/HINDI_GENERATION_INVESTIGATION_2026-10-06.md`: accepted and failed controls.
- `docs/HANDOFF_FULL_VIDEO_VALIDATION_2026-10-04.md`: wider architecture/readiness.

This is the rollout recommendation, not a promise that untested language pairs
or advertised features are already ready.
