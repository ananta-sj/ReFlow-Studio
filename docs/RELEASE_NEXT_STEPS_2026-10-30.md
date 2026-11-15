# Remaining release work — 30 October 2026

The user reported: “all the dubs loook and sound goood... what's left?”
The dubs they reviewed are accepted for sound and appearance. The exact reviewed
filenames were not enumerated; this does not approve unreviewed experimental
takes, every optional engine, future generations or a distribution artifact.
Historical receipts' human-acceptance fields describe their earlier state and
are preserved. The latest final code passed 976 backend tests and actual legacy
and isolated XTTS execution checks. The latest frontend evidence remains a
successful production build and 83 contract checks.

## Remaining work

1. **Freeze the Windows release scope and runtime bundle.** Assemble current
   source and tested engine profiles into one reproducible candidate. Separate
   desktop/engine candidates have scoped technical acceptance, but the default
   portable builder still uses the older shared Python runtime. Remaining legacy
   engine dependencies must be accounted for before replacing it. Review the
   exact files shipped and exclude personal settings, credentials, media, model
   connections and diagnostic data.
2. **Verify the new-user setup.** Test extraction to a different folder and a
   clean Windows machine, startup prerequisites, empty model state, chosen-engine
   setup, required authentication/reference enrollment, interrupted downloads,
   useful errors and offline restart. This computer's configured development
   folder does not establish first-use acceptance for another user.
3. **Run representative complete workflows on the candidate.** Cover longer
   video, audio-only and subtitle exports, batches, cancellation, application
   restart/recovery, output preservation and synchronization. Include noisy or
   multi-speaker sources within the advertised scope. Existing unit checks and
   approved dubs cover specific cases, not every candidate workflow.
4. **Resolve optional-feature readiness.** The scoped current registry inventory
   found 37 voice entries and zero installed voices; actual RVC conversion remains
   unverified. Lip-sync/other visual engines and GPU routes have differing levels
   of execution/runtime acceptance. Validate advertised routes with real assets,
   or clearly mark/exclude unfinished routes from the first release. Do not
   download additional models or install software without the user's approval.
5. **Settle the application license and distribution inventory.** The current
   root LICENSE.txt contains Python's license/history; an application license
   choice remains pending. Complete the notices and model/component distribution
   review for the exact chosen bundle. This checklist makes no legal clearance
   claim and assigns no license.
6. **Align release automation and finish the artifact.** The current GitHub
   workflow builds PyInstaller executables from broad requirements on three OS
   runners; it does not run the full regression suite or produce the verified
   Windows portable candidate. Align it with the chosen release path, then check
   the final version, instructions, manifest, checksums, release notes and source
   snapshot. Linux/macOS should remain experimental unless independently tested.

The next concrete milestone is a **Windows portable release candidate** with a
defined supported feature set and a documented fresh-install test. No release
has been published, license selected, dependency installed or model downloaded
in response to this status question.

## Size correction

The old 500 MB target was explicitly withdrawn in the release-readiness ledger.
It is not a release requirement. The measured 2,824,731,999-byte default core is
a packaging observation, not a size-based release rejection. The first 30 October
audit has been corrected accordingly.

## Evidence

- [Final tested-source summary](validation/2026-10-30-context-final-summary.json)
- [Multilingual repairs and actual execution](MULTILINGUAL_CONTEXT_REPAIR_2026-10-30.md)
- [Release ledger, including later engine/runtime entries](RELEASE_READINESS_2026-10-04.md)
- [Desktop candidate scope](DESKTOP_CANDIDATE_ACCEPTANCE_2026-10-14.md)
- [Outstanding license discussion](LICENSE_DECISION_BRIEF_2026-10-12.md)
