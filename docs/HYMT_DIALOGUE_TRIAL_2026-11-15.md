# HY-MT dialogue trial: not approved for production

The user-approved replacement is installed in the isolated trial directory. The 1,908,528,288-byte official Q8 model passed SHA-256 verification. Only the failed Qwen weights were retired; the verified portable runner is shared and remains installed. Active app model connections were not changed.

Direct Japanese translation, contextual Japanese translation, aligned English subtitle translation, and English translation with preceding dialogue were evaluated. The last variant supplies four preceding source turns, rather than trusting earlier model translations. Known character roles are test fixtures, not evidence of automatic identification.

The model produces more coherent Hindi than the rejected Qwen trial, but fails the whole-scene meaning check. In both English-source variants, “his father” becomes “अपने पिता” while the speakers are his wife and daughter. The grandfather-location line omits “north of Paris.” Preceding dialogue improves the short reply “Yes, he did” to “हाँ, उन्होंने ऐसा ही कहा,” but does not resolve those other errors. These are semantic failures, not GPU failures. No rejected scene was sent into a long speech-generation pass.

Raw inputs, timing/provenance evidence and outputs are under `docs/validation/hymt-trial-20261114`. The history variant uses a distinct `-history` filename and does not overwrite the earlier experiment. Automatic completion checks establish that generation finished; they do not establish correct meaning.

The focused recovery, queue, diarization, repair and caption-alignment suite passed 52 tests. This does not establish natural acting or full-episode reliability. Auxiliary caption alignment and the new translator are not enabled in the production route. Existing character assignment coverage remains insufficient for unattended episode dubbing.

Remaining work is semantic acceptance with relationship/geography preservation, reliable character coverage, then real multi-character speech timing and listening checks before enabling a full episode. Installing this replacement alone does not resolve these requirements.
