# Deck Master Roadmap

This roadmap tracks the path from the current public Technical Preview
(`v0.9.14-preview.4`) to a `1.0.0` release. It is a living document; priorities
may shift. See `docs/archive/pre-rebuild/docs/releases/2026-07-09-1.0.0-iteration-plan.md` for the
detailed sprint breakdown.

## Status

Deck Master is a public **Technical Preview** (agent-operable). The fixture
demo, review workbench, and honest per-step diagnostics
are available. Production readiness is **not** claimed. The runtime is
verified locally on a maintainer machine (history in docs/archive/pre-rebuild/), but the
1.0.0 gap is reproducible/traceable evidence + CI enforcement + governance,
not new functionality.

## 1.0.0 — definition

Deck Master 1.0.0 is installable in a clean environment, can produce at least
3 real benchmark cases end-to-end with public/configurable backends, and passes
the rebuilt export gate (`deck-master export --purpose delivery`), Review Workbench, and
release-tree install/rollback, with open-source governance and security
boundaries in place.

## Milestones

### M1 — Public Technical Preview (done)

- Fixture demo from a public brief.
- Review Desk preview.
- Per-step toolchain diagnostics (`deck-master doctor --step …`).
- CI gates: `.github/workflows/rebuild.yml` (unit matrix / real rendering / report).

### M2 — Release-candidate closure (in progress)

- CI gates: `.github/workflows/rebuild.yml` (unit matrix / real rendering / report), full history
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
- rebuilt gate green (`.github/workflows/rebuild.yml`); benchmark history archived.
- Release tree install/rollback green; `docs/archive/pre-rebuild/docs/releases/v1.0.0.md` published.
- External user can go from `0` to a working demo via README, and understands
  production configuration.

### 1.0.0

- RC stable for a burn-in period with no blockers.
- Tag `v1.0.0` and publish the release tree.

## Out of scope for 1.0.0

- Splitting the large legacy CLI module (history in `docs/archive/pre-rebuild/`; tracked as a
  follow-up refactor on its own branch).
- Multi-quarter rewrites or unrelated migrations.

## How to contribute

See `CONTRIBUTING.md`. For routing of common requests, see `AGENTS.md`.
