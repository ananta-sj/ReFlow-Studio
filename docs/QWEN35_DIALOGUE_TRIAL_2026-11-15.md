# Qwen3.5 dialogue adaptation trial — November 15, 2026

The owner-approved replacement downloaded and verified 5,680,522,464 bytes of
`unsloth/Qwen3.5-9B-GGUF`, revision
`3885219b6810b007914f3a7950a8d1b469d598a5`, Q4_K_M. SHA-256:
`03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8`.
Only after verification, the failed 4,624,649,312-byte HY-MT 7B trial weight file
was retired. Its profile and diagnostics remain. Active application configuration
and models were unchanged. The shared runner was reused without installation.

The existing runner crashed with Windows exit status 3221226505 on both CPU and
RTX when using the combined chat/schema options. Minimal generation succeeded
on CPU and RTX. An isolated fallback using the publisher's text-only
non-thinking prompt format, without the runner's chat/schema machinery, completed
real dialogue generation. This narrows the failure to the option path, but does
not establish which individual option caused it. Strict JSON, completion,
Hindi-content, repetition, fact and word-budget checks remain outside the runner.

## Results and limits

Two seven-turn scene passes were evaluated with at most two candidates per turn:
one with the previous Hindi draft and shared register context; another without
that flawed draft, with explicit per-turn speaker/addressee and preceding source
dialogue. Known scene roles were supplied as fixtures, not automatically inferred.

The first pass made the mother address another mother, mistranslated “Yes, he
did” as “he went,” and initially dropped the direction north. The existing
direction alarm caught the last error and the retry restored it. The village
line remained over budget. The Europe rewrite became short enough on retry,
but retained awkward Hindi.

Removing the flawed draft and clarifying the active speaker fixed the incorrect
address in the departure line. All seven final candidates fit the word budgets,
but this was not semantic success: the village line contained malformed Hindi,
the short reply still became “he went” despite preceding context, and the
grandfather line omitted France and left the subject unclear. The Europe line
was shorter but still awkward. Model-reported `uncertain=false` did not reliably
identify these failures.

The candidate is **not approved for production dialogue adaptation**. No speech
was generated from these scene candidates and no episode export was started.
Word count and narrow fact checks cannot substitute for meaning, register,
acting, actual speech duration or continuous listening. A different prompt
improves individual lines but has not established a reliable automatic route.

Five independent controls also completed. Negated-request and quantity outputs
preserved their basic meaning. Family-reference, female-refusal and female-past-
action initially used Romanized Hindi and were rejected; one bounded retry
returned Devanagari. The refusal then preserved female agreement, but the family
reference and past-action answers still had incorrect Hindi grammar. Passing the
format or word-budget check was not recorded as meaning/acting acceptance.

The four output-validation tests pass, including rejection of unfinished output,
reasoning, wrong field types, and extra content after a terminal marker. The
source manifest was refreshed; no commit, push or release was performed.

Raw reports and completion logs are retained locally in
`docs/validation/qwen35-trial-20261115`; they are excluded from source publication.
The weights remain isolated for reproducibility. Further downloads or a runner
replacement require separate owner approval. This trial does not establish
episode/movie readiness.

Publisher references:

- https://huggingface.co/Qwen/Qwen3.5-9B
- https://huggingface.co/Qwen/Qwen3.5-9B/raw/main/chat_template.jinja
- https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/tree/3885219b6810b007914f3a7950a8d1b469d598a5
