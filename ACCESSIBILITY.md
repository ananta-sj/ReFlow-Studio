# Accessibility in ReFlow Studio

We want ReFlow's desktop workflows to be usable with a keyboard, readable at different sizes, and understandable without relying only on colour or sound. This is an ongoing goal, not a declaration of WCAG conformance or universal assistive-technology support.

## Current status and known limits

The source includes accessible names/focus styles for title-bar controls and simulated checks for startup recovery, Dashboard and dialogue-review state. Those checks do not establish native keyboard focus, screen-reader output, colour contrast or playback accessibility.

Native testing is still required for Windows, Linux and both Mac architectures, in both themes and at different display scales. Keyboard access to complex node/graph controls, dialogs, marketplace operations and dialogue auditions needs explicit verification. Dubbing quality comparisons can require listening; equivalent textual measurements do not fully convey voice identity or emotional delivery.

## Report a barrier

Use the [bug-report form](https://github.com/ananta-sj/ReFlow-Studio/issues/new/choose). Include the version/commit, OS, assistive technology and version (if relevant), input method, affected screen, exact action, and expected/observed result. Screenshots are optional. Remove personal information and do not share private audio or credentials. We do not require a particular assistive technology to accept a report.

## Contributor expectations

Preserve semantic labels, visible keyboard focus, logical navigation and reduced-motion behaviour where supported. Describe loading, empty, error and disabled states. Test both themes and scaling for UI changes. Report observed results and remaining gaps; do not label a component accessible solely because its static markup passes.

Progress is tracked in the [roadmap](docs/ROADMAP.md). This volunteer project does not promise remediation deadlines.
