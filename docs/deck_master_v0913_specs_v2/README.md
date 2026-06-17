# Deck Master v0.9.13 Spec Pack v0.2

This pack supersedes the first v0.9.13 draft. The v1 spec pack has been removed from this repository, and this directory is the active v0.9.13 development baseline.

It integrates the review findings around:

- PPT Master as P0 required default build/render capability.
- `full_suite_ready=true` as final acceptance gate.
- Codex and Claude Code target parity.
- Explicit CLI override policy.
- Required executable capability contract.
- Canonical render result path: `render_results/render_result.json`.
- Agent-driven setup ceremony in Skill docs.
- Pure-read `setup-status` / `suite-status` regression tests.
- Temporary HOME install / QA smoke.
- Removal of external/companion wording in the normative path.
- `.DS_Store` exclusion.

Recommended execution order:

1. A — Manifest, Release Tree, Full Suite Readiness
2. B — Required Capability Packages and PPT Master P0 Render Path
3. C — Core Skill Split and Target Routing
4. D — Suite Install / Migration / Setup for Codex and Claude Code
5. E — Runtime Discovery and Capability Integration
6. F — Acceptance / Regression / Release Readiness

Related diagnostic:

- `../diagnostics/deck-master-current-implementation-user-story-2026-06-17.md`
