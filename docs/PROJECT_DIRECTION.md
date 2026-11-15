# ReFlow Studio: purpose and current limits

ReFlow is intended to coordinate media tools and AI engines so people can make
family-friendly edits, adapt dialogue, and dub media while retaining the scene's
meaning, characters, background sound and dramatic intent.

These are separate workflows, with different requirements:

| Workflow | Intended processing | Current acceptance status |
| --- | --- | --- |
| Beep/mute selected words | Identify words, align precise intervals, edit only those intervals, remix/export | Existing profanity-provider hooks do not establish a validated word-level censor-only workflow. Needs dedicated acceptance tests. |
| Clean dialogue replacement in the same language | Rewrite only flagged phrases, preserve meaning/register, generate the same character voice, fit and remix | Not established as reliable; rewritten wording, identity and performance require review. |
| Translate and dub | Transcribe, identify characters, adapt dialogue with context, synthesize, check timing/meaning and remix | Components exist; reliable unattended multi-character episodes/movies remain unvalidated. |

Beep/mute mode should retain the original dialogue elsewhere. It does not need
translation or synthesized replacement speech. With an appropriate dialogue stem,
background sound can continue under a censored word; source separation may still
leave voice residue or remove wanted sound. Muting the complete soundtrack would
also mute effects/music in that interval and should be a distinct user choice.

Translation models handle language conversion; they do not by themselves provide
all scene-aware rewriting, censorship policy, emotional acting, voice identity,
timing and quality supervision. A coordinator needs explicit decisions, bounded
retries, durable evidence and honest escalation when a result remains uncertain.
Voice cloning is not proof of identical emotional performance or lip movement.

## Indian-language candidates: research only, November 15, 2026

Sarvam's official documentation lists Indian-language/English translation,
code-mixed speech generation and a separate cross-lingual voice-cloning beta.
Its listed translation languages do not include Japanese. It could be evaluated
for Hindi/Hinglish output or an English-to-Hindi step; Japanese comprehension
would still need a compatible component. The documented hosted APIs require an
account/key, usage billing and sending the relevant text/reference audio to the
service. Their availability does not establish an equivalent local installation.
No Sarvam integration, account access, upload or API request was performed here.

AI4Bharat offers IndicTrans2 for Indian-language translation and reference-guided
IndicF5 speech. Both have already been explored in this project; they are not
newly discovered fixes. The current IndicF5 model card points to Indic-Speak as
its successor; that is a research lead, not a tested or installed replacement.

Indian-language specialization is a reason to compare candidates, not evidence
that they will solve the actual scene. Evaluate natural grammar, code-mixing,
negation, relationships, duration, speaker identity, emotion and cost separately.
Do not download more models or use hosted services without owner authorization.

Official references:

- https://docs.sarvam.ai/api/getting-started/models
- https://docs.sarvam.ai/api-reference/text-to-speech/convert
- https://docs.sarvam.ai/api-reference/voice-cloning/clone
- https://models.ai4bharat.org/
- https://huggingface.co/ai4bharat/IndicF5

## Proposed next practical milestone

First validate censor-only editing on a short permitted sample: mark intended
words, inspect alignment, confirm untouched speech remains original, preserve
the background as well as the source allows, and verify exported synchronization.
Then separately evaluate clean replacement of one phrase. Require a continuous
multi-character scene before full-episode trials. This sequence is a proposal;
this source-preparation task does not implement or validate those workflows.

The current source contains recovery, GPU routing, review and cleanup improvements
beyond the published RC2 binaries. It is development source, not a new stable
release or a guarantee of studio-quality dubbing. Failed model experiments remain
disabled. Runtime/model licensing review remains pending for distribution.
