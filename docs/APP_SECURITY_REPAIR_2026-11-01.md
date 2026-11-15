# App security repair — 1 November 2026

Scope: React interface and frontend build dependencies. Python bridge, providers,
model downloads, checkpoint loading, runtime dependencies and packaging are deferred
to the backend/security-runtime review requested for later. Existing workspace edits
were preserved. No release or installer was published.

Reviewed the full project audit of 3 October, architecture audit of 9 October and
the 30 October audit/repair report. These contain historical findings and are not
evidence that each finding still exists today.

## Changes

- Updated Vite from installed 8.1.5 to 8.3.5, including its lockfile dependencies.
  The initial npm bulk advisory response identified five Vite advisories, one high,
  three moderate and one low. See validation/2026-11-01-frontend-advisories.json.
- Catalog project links now accept only absolute HTTP/HTTPS URLs without embedded
  credentials, whitespace, control characters or backslashes. File, script, data,
  relative and custom-protocol links are rejected. New windows explicitly receive
  noopener/noreferrer protections.
- Added document policy blocking objects, frames, base-URL replacement and form
  submission, plus a no-referrer policy. This is deliberately a limited policy;
  it does not prevent all script injection or top-level navigation.
- API-key inputs disable autocomplete, spellcheck and automatic capitalization.
  Browser/password-manager behavior can override autocomplete hints. Keys already
  use password fields, component memory and the OS credential-store bridge.

## Verification

- Final live npm audit: zero known vulnerabilities across the locked dependency
  graph. See validation/2026-11-01-frontend-audit-final.json. This is advisory
  coverage at check time, not a guarantee of absence of vulnerabilities.
- TypeScript and Vite production build passed after the dependency upgrade.
- All 83 existing frontend checks passed; new URL rejection/acceptance checks pass.
- Lint completed with existing warnings; the added URL helper has no lint warning.
- No raw HTML rendering or direct frontend fetch/WebSocket calls were found in
  the searched application sources.

## Remaining acceptance and deferred work

Native desktop interaction with the new policy has not been exercised. A complete
security sign-off still requires checking bridge exposure/navigation, native shell
behavior and released artifacts, plus the deferred Python findings. Historical
audit items A28 (filesystem deletion), A30 (credential origins), A34 (installation)
and A32/A33 (runtime dependency integrity) belong to that follow-up. Several have
prior repair reports; verify their present implementation before calling them open
or fixed. Do not describe this interface pass as clearing all app security risks.
