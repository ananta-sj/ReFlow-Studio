# Security policy

## Supported versions

Security fixes target `main` and the newest Desktop Preview. Older preview builds are not maintained independently. This volunteer project does not promise a response deadline or certify that previews are free of vulnerabilities.

## Report a vulnerability privately

Use [GitHub private vulnerability reporting](https://github.com/ananta-sj/ReFlow-Studio/security/advisories/new) when the repository offers **Report a vulnerability**. Describe the affected version/commit, impact, minimal reproduction and suggested mitigation.

Do **not** open a public issue with exploit details, API keys, tokens, private audio/video or personal paths. Redact logs and use a synthetic reproduction. If private reporting is unavailable, wait for the maintainer to enable it; do not publish sensitive details as a workaround. Maintainers must enable private vulnerability reporting in repository settings before advertising it as available.

If a credential has leaked, revoke or rotate it with its provider immediately. Removing it from a file or Git history does not invalidate it.

## Scope

Reports about the desktop bridge, subprocess execution, downloads/model installation, archive extraction, credential handling, dependency supply chain and release automation are welcome. Report upstream model/library flaws to the upstream project as well. External models and user-configured providers have their own security and licensing terms.

Automated scans complement review and runtime testing. A green build is not proof of security or dubbing quality. Never upload real secrets or private media to demonstrate an issue.
