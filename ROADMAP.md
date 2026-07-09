# Deck Master Roadmap

This roadmap tracks the path from the current public Technical Preview
(`v0.9.14-preview.2`) to a `1.0.0` release. It is a living document; priorities
may shift. See `docs/releases/2026-07-09-1.0.0-iteration-plan.md` for the
detailed sprint breakdown.

## Status

Deck Master is a public **Technical Preview** (agent-operable). The fixture
demo, Review Desk preview, backend readiness transparency, and `preview-gate`
are available. Production readiness is **not** claimed. The runtime is
verified locally (suite ready, rc-gate green on a maintainer machine) but the
1.0.0 gap is reproducible/traceable evidence + CI enforcement + governance,
not new functionality.

## 1.0.0 — definition

Deck Master 1.0.0 is installable in a clean environment, can produce at least
3 real benchmark cases end-to-end with public/configurable backends, and passes
`rc-gate` (full tier), `final-readiness`, Review Desk browser smoke, and
release-tree install/rollback, with open-source governance and security
boundaries in place.

## Milestones

### M1 — Public Technical Preview (done)

- Fixture demo from a public brief.
- Review Desk preview.
- Backend readiness transparency (`suite-status`, `agent-doctor`, `backend status`).
- `preview-gate` and `release-build`/`release-smoke`.

### M2 — Release-candidate closure (in progress)

- Two-tier `rc-gate`: CI-reproducible subset in CI (`--tier ci`), full tier
  locally / at release.
- Real benchmark closure: ≥3 real metadata cases with complete report pairs,
  aggregate `report_ready` (local-only evidence, archived as such).
- PPT Master production backend closure: reproducible clean-environment bind
  pinned to a tagged release + SHA.
- Review Desk full design-system alignment (`DESIGN.md`) and product polish.
- Release-tree install/verify/rollback evidence.
- GitHub community entry (issue/PR templates, CODEOWNERS, dependabot, ROADMAP).

### 1.0.0-rc.1

- Freeze features, fix blockers only.
- Full CI matrix (Python 3.11 + 3.12) green.
- rc-gate (full) green; benchmark aggregate `report_ready`.
- Release tree install/rollback green; `docs/releases/v1.0.0.md` published.
- External user can go from `0` to a working demo via README, and understands
  production configuration.

### 1.0.0

- RC stable for a burn-in period with no blockers.
- Tag `v1.0.0` and publish the release tree.

## Out of scope for 1.0.0

- Splitting the large `scripts/deck_master.py` CLI module (tracked as a
  follow-up refactor on its own branch).
- Multi-quarter rewrites or unrelated migrations.

## How to contribute

See `CONTRIBUTING.md`. For routing of common requests, see `AGENTS.md`.
