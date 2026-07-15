# Changelog

## Unreleased

- Enforce final artifact approval at every client export entry.
- Return a failing process status when RC Gate is blocked or failed.
- Preserve fixture run mode across state and routing commands.
- Package Skill OS registries and expand isolated release smoke coverage.
- Require delivery-grade evidence before benchmark reports qualify for RC.

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
