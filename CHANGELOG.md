# Changelog

## Unreleased

## 1.0.0 — release preparation, 2026-10-21

Python package `1.0.0`; intended tag `v1.0.0`. Publication and final candidate
validation remain separate from this source preparation.

- Integrate the RC5 content-method catalog, bounded Host resource selection,
  dependency expansion and frozen Task methods from PR127.
- Add structured support/feedback and contribution guidance from PR128.
- Clarify current documentation and preserve dated evidence through the
  documentation and archive indexes from PR129.
- Replace retired Make/script entry points with the rebuilt CLI and current
  checks; retire the unvalidated legacy Docker/Dev Container entry and document
  the supported local Python installation instead.

- Integrate PR130's fixed-revision content/method reading, narrative comparison,
  direction adoption recovery, source evidence and bounded review handoffs.
- Preserve image request ownership when aborting, replacing or removing queued
  image work; release active leases synchronously on cancellation.

Exact-source validation and release assets are tracked in the
[release preparation record](docs/releases/1.0.0-preparation.md). Historical observations
below retain their original version and scope. Font rendering, professional
human review and desktop editing limitations remain in the first-run guide.

## 1.0.0rc4 — candidate, 2026-10-20

Release candidate of the rebuilt, local-first Deck Master core. Python
package version `1.0.0rc4`; proposed prerelease tag `v1.0.0-rc4`. The earlier
1.0.0 source preparation was not published; its formal release is cancelled.
This candidate supersedes the historical
v0.9 preview architecture; old project formats require the documented migration.

- One `deck-master` CLI and loopback Workbench for source-backed content,
  scoped design, editable SVG/PPT production, review, recovery and delivery.
- Four managed Codex Skills share one canonical method source; new Tasks
  freeze their exact ordered methods and applicable content policy.
- Recoverable input receipts and installation transactions preserve exact
  retries, interrupted work, cancellation and current authorization.
- Negotiated `work_context.v2` supports full context and bounded deduplication;
  history queries preserve committed ancestry and unknown outcomes.
- Normal installed native independent review uses an actual fresh Codex
  session and the existing authenticated receipt path. Literal MCP server names,
  including dots, quotes and Unicode, remain disabled in that session.
- Release installation, external Host requirements, first use, upgrade,
  font configuration limits and contribution guidance are documented.

The functional baseline PR125 (`d7ec4530`) passed both 7-job CI runs. The
maintainer's actual installed Host task completed native review, native-image
observations on two pages, real SVG/PPT rendering and formal delivery with
`handoff-check verified`. Chinese LibreOffice rendering required an existing
process-scoped Fontconfig configuration. Actual WPS editing was not verified
because the device locked. These observations are not a general desktop,
professional-review or operating-system certification.

See [first run and known limitations](docs/getting-started.md). Publishing a
tag/Release and activating a user's installation are separate operations.

## Pre-rebuild unreleased notes (historical)

These entries belong to the retired preview architecture and are retained as
history; its RC Gate and companion setup are not current release requirements.

- Enforce final artifact approval at every client export entry.
- Return a failing process status when RC Gate is blocked or failed.
- Preserve fixture run mode across state and routing commands.
- Package Skill OS registries and expand isolated release smoke coverage.
- Require delivery-grade evidence before benchmark reports qualify for RC.

## v0.9.14-preview.4

Status: Technical Preview (agent-operable).

Version mapping: GitHub release label `v0.9.14-preview.4` maps to Python
package version `0.9.14a4`. Skill Suite contract version remains `1.1.0`.
This patch preview supersedes `v0.9.14-preview.3` without changing the
high-density content or rendering behavior.

This patch fixes release-runtime packaging and capability discovery:

- Installed releases discover v2 high-density contracts from the canonical
  release `contracts/` directory as well as the source `docs/contracts/`
  directory.
- Python entrypoints inside the moved release virtual environment are
  repaired to point at the active release path instead of the staging path.
- Added regression coverage for installed contract discovery and moved
  virtual-environment launchers.

Validation includes the full release-runtime and high-density regression set:
`110 passed`, `4 subtests passed`, Ruff, compile checks, and `git diff --check`.

## v0.9.14-preview.3

Status: Technical Preview (agent-operable).

Version mapping: GitHub release label `v0.9.14-preview.3` maps to Python
package version `0.9.14a3`. Skill Suite contract version remains `1.1.0`.
This preview does not claim production readiness.

This preview adds the independently installable High-Density Builder route:

- MBB content enrichment with storyline selection, evidence binding, SCR, and
  page-level content planning.
- Content-safe ImageGen blueprint generation with page-number and internal-label
  prohibitions.
- Native SVG reconstruction with controlled icon, curve, table, text, and
  visual-registration gates.
- SVG-authoritative DrawingML PPTX compilation, readback, trace, and visual
  parity checks.
- Fail-closed migration handling for retired content-planning artifacts and
  release evidence that accurately reports unavailable private benchmarks.

Validation for this preview includes `1399 passed` and `105 subtests passed`,
Python 3.11/3.12 compile checks, Ruff, JSON contract validation, release smoke,
and local installation verification.

The fresh provider smoke, six-page external icon acceptance, and 73-page
external benchmark remain release gates and are not represented as completed
in this preview.

## v0.9.14-preview.2

Status: Technical Preview (agent-operable).

Version mapping: GitHub release label `v0.9.14-preview.2` maps to Python
package version `0.9.14a2`. This preview does not claim production readiness.

This preview carries the final release hygiene patch after
`v0.9.14-preview.1`, including Python 3.12 CI coverage, release checklist
closure, PPT Library handback wording cleanup, and refreshed Agent QA routing.

## v0.9.14-preview.1

Status: Technical Preview (agent-operable).

Version mapping: GitHub release label `v0.9.14-preview.1` maps to Python
package version `0.9.14a1`. This preview does not claim production readiness.

This preview focuses on open-source readiness:

1. Apache-2.0 project license.
2. Standard editable install through `pyproject.toml`.
3. Public first-run fixture demo and Review Desk path.
4. Backend readiness transparency when production companions are not configured.
5. M1 `preview-gate` separated from M2 `rc-gate`.
6. Review Desk local write protection with token and same-origin guard.
7. Source checkout verification commands that do not assume `deck-master` is already on PATH.

This preview does not carry formal GA support guarantees.
