# Character matching and retained timing takes

The source-caption workflow now has an episode-local fallback for uncertain
voice matches. It learns a small classifier from labelled source examples already
present in the same media. It downloads no additional model. At least two named
characters with multiple examples are required. Generic crowd roles are not
treated as confirmed individual characters.

The fallback keeps a score margin and a minimum acoustic similarity, and does
not assign short interjections, mixed-speaker captions, blocked intervals or
conflicting explicit labels. Proposed assignments never become training examples
or supporting evidence for further promotions. Long-media training solves the
smaller linear system instead of allocating a matrix quadratic in every cue.

On the cached episode evidence, automatic assignments increased from 184 to 194
of 363 cues. In the separately known mother–daughter scene, 12 of 14 cues matched
the expected character and two remained unresolved, compared with 11 correct and
three unresolved previously. The labelled holdout and withheld-minute checks
each reported 10 correct, 45 rejected and zero wrong. These are limited checks:
the additional unlabelled assignments are not all independently verified, and
this does not establish full-episode readiness or general anime accuracy.

For failed runs with retained timing evidence, the Dashboard now shows the saved
take's measured duration, available window and excess duration. **Load saved
overlong take** opens that existing recording for listening without regenerating
it. The bridge restricts it to the selected application run, checks its size and
checksum, and validates that it is a bounded WAV. Playing it never marks it
accepted. Changed or missing files require recovery rather than silent playback
of another file.

Natural dialogue adaptation remains unresolved. This development does not enable
the unaccepted translation trial or create a completed episode dub.
