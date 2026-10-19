# Deck Master roadmap

The current increment is [RC4, based on merged PR123](docs/specs/deck-master-next-iteration-20261019/README.md).
Its six task cards are the development contract; current execution results
live only in the [candidate ledger](docs/reports/rc4/iteration-20261019/execution-ledger.json).
The package version, a built candidate, an active installation and a public
GitHub Release are separate facts. This roadmap does not announce a release.

## Current work

1. N1: recover ordinary input updates from committed receipts, preserve
   legacy requests, and align the bounded HTTP/Python entry points.
2. N2: recover interrupted installation transactions while preserving path
   ownership, opt-out behavior and exact rollback replay.
3. N3: freeze Task methods and argument validation policy; apply the Review
   methods required by the actual scope.
4. N4: negotiate complete, deduplicated v2 reading contexts and reduce
   repeated history decoding without weakening recovery evidence.
5. N5: keep active instructions, contract mirrors and candidate/install
   identities consistent.
6. N6: make a concrete canonical method improvement and apply it to a
   complete normal task, with actual revisions and applicable checks.

The existing Runtime, CAS, immutable sources, four Skills and native
image → SVG → editable PPT chain remain the architecture.
Content-only work ends with its requested content; it does not silently
start image or PPT production.

## Candidate closure

Use the current workflow for the unit matrix, real rendering, required
browser and installed/offline checks. Record unavailable capabilities on
the affected items. Engineering checks do not stand in for actual method
application, professional approval or user feedback.

Public release and activation of a user's installation require their own
authorization. Installation rollback does not lower a project's writer floor.
There is no committed date for a final 1.0.0 release.

## Later decisions

Use this candidate's evidence to choose further content/layout improvements
or a narrower service/Task boundary refactor. New providers, databases and
unrelated architecture rewrites are outside this increment.

Earlier preview milestones remain in
[the historical iteration plan](docs/archive/pre-rebuild/docs/releases/2026-07-09-1.0.0-iteration-plan.md).
Use [CONTRIBUTING](CONTRIBUTING.md) for development and
[AGENTS](AGENTS.md) for task routing.
