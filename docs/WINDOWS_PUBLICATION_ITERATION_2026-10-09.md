# Windows publication recovery — 9 October 2026

## Outcome and scope

Job-owned publication now tolerates a brief Windows access/sharing denial without exposing a partial review or replacing a valid result prematurely. The change applies to the existing RenderContext publisher used by saved review documents, prepared review folders, generated media and output bundles. No package/model/tool installation, download, model inference or provider API call was performed.

This is a proven repair for controlled transient-lock cases, not proof that the original intermittent failure had the same owner or will never recur. Persistent locks and genuine permission errors still fail explicitly. Release readiness remains pending.

## Historical failure and causal reproduction

The first engine-setup regression run recorded `PermissionError: [WinError 5]` in `RenderContext.publish`, while renaming a newly prepared review folder into the review store. Ten isolated repeats and later complete runs passed without changing publication. That evidence established intermittency, but did not identify the process or handle causing the denial.

This increment uses Windows `CreateFileW` handles on disposable workspace fixtures. The handle permits reading/writing but omits delete sharing. Raw `os.replace` results were:

| Held handle | Observed error | After releasing the handle |
| --- | --- | --- |
| Prepared folder itself | WinError 32 | Publication succeeds |
| A review file inside the prepared folder | WinError 5 | Folder publication succeeds |
| Pending result file | WinError 32 | Replacement succeeds |
| Existing destination result file | WinError 5 | Replacement succeeds |

In every denied attempt, pending data and any old destination remained intact. The child-file case reproduces the same error and folder-renaming operation as the historical failure. The original lock holder remains unknown: no antivirus, indexer, player or other process is blamed without evidence. Receipt: `validation/2026-10-09-windows-publication-reproduction.json`. The diagnostic uses only its own temporary files and closes every handle before cleanup.

## Production behavior

`core/render_context.py:RenderContext.publish` now allows at most four atomic replacement attempts for Windows `PermissionError` codes 5 and 32. Waiting intervals are 50, 100 and 200 milliseconds: 350 milliseconds total, plus the operating system's replacement-call time. This is a bounded recovery window, not an indefinite loop or a hard I/O deadline. The policy matches the existing JSON transaction writer's recognized Windows errors/backoff.

Each attempt checks cancellation and performs `os.replace` under the job lock. Between attempts, the lock is released and the cancellation event supplies the wait. Stop from another thread can therefore acquire the lock, set cancellation and prevent the next publication. A replacement that already succeeds remains published if Stop arrives afterwards, preserving the existing contract.

Non-Windows failures, unknown permission codes and other I/O errors are not retried. An existing destination directory, or a pending directory conflicting with an existing destination, also fails without retry rather than treating a destination conflict as a temporary sharing error. The final persistent failure is re-raised; no successful status is fabricated and no destination is deleted to make replacement work. Caller-owned cleanup/recovery rules remain unchanged.

For files, the old result remains available until a successful atomic replacement. For new review directories, the complete staged directory becomes visible only after its rename succeeds. The publisher itself does not delete pending data on failure; higher-level staging contexts retain their existing cleanup behavior. Failed review preparation still publishes no new review record. No corruption, revision, asset-hash or acceptance checks were weakened.

## Verification

`dev/windows_lock_fixture.py` provides a Windows-only, scoped handle helper. `dev/diagnose_windows_publication.py` records the raw lock/error/release observations. `dev/test_windows_publication.py` checks transient recovery, bounded persistent failure, old/pending-data preservation, directory conflicts, unsupported errors/platforms and cancellation from another thread during backoff. Four tests use actual Windows handles, including persistent destination denial and recovery after child/pending/destination handle release. These are filesystem operations, not just mocked exception sequences.

The first focused run passed nine tests in 0.744 seconds; its retained log is `validation/2026-10-09-windows-publication-focused.log`. A file-to-existing-directory conflict test was subsequently added and is included in the final complete suite.

`dev/verify_windows_review_publication.py` additionally runs the existing real review-preparation/persistence fixture while deliberately holding its staged `review.json` open. The initial directory rename raises real WinError 5. Releasing that handle permits the retry to publish a valid saved review, with source audio/transcript/translation assertions still passing. The fixture also checks that a later simulated translation failure publishes nothing. Recognition/translation are fixture responses; media preparation, persistence, Windows handles and publication are real. One integration test passed in 1.379 seconds. Receipt/log: `validation/2026-10-09-windows-review-publication-integration.json/.log`.

**717 backend tests across 41 modules passed in 111.047 seconds**, with zero failures/errors and unchanged tested production sources and saved registry/settings. Receipt/log: `validation/2026-10-09-windows-publication-backend-complete.json/.log`. The evidence runner now includes `core/render_context.py` and a separate publication label, preserving earlier iteration receipts. Expected simulated engine-error messages in the log remain fixture output rather than new live-engine failures.

Final source fingerprints and accepted-video identity passed in `validation/2026-10-09-windows-publication-evidence-integrity.json`. The accepted editorial video retains SHA-256 `0e4dc4a51253b5b4a0172ec2842647f0f2b643480135d6c27e4876b0442bf0a2`. There are no frontend source changes in this increment; no new visual interaction claim is made.

## Remaining work

The original external lock holder remains unidentified. Locks lasting longer than the recovery window still produce a failure; future recurrence should preserve diagnostics and identify the handle owner before expanding the policy. This change does not establish network-filesystem behavior, Linux/macOS packaging, input-independent dubbing quality, other-engine runtime readiness or full-video success. Live dialogue-assistance evaluation remains deferred, and no new user-facing audio/video was generated.
