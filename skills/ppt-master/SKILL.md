---
name: ppt-master
description: Deck Master compatibility entry for the full PPT Master backend used by deck-builder. Use only to inspect or hand back production render results through Deck Master.
triggers:
  - render deck preview
  - build html render artifact
  - import render result
  - check render status
  - ppt master
---

# PPT Master Backend Compatibility Entry

PPT Master is the full production backend used by `deck-builder`. This
compatibility entry is kept for existing prompts and local installs.

Use `deck-builder` as the public Deck Master build entry. In an active Deck
Master run, every backend output must return through Deck Master import or state
update paths.

## Use When

- A Deck Master run is blocked at `needs_builder_backend`, `needs_build`, or `needs_render`.
- You need to inspect whether a full PPT Master backend is installed and production-capable.
- A real PPT Master backend has produced a `deck_render_result.v2` handback that must be imported.

## Do Not Use When

- You only need planning, sourcing, quality review, or export readiness. Use the corresponding `deck-*` skill.
- The run is production or benchmark and only `render --fixture-safe` is available.
- You are trying to create client-deliverable files from the bundled contract-smoke renderer.

## First Checks

```bash
~/.deck-master/bin/deck-master setup-status --include-suite --output json
~/.deck-master/bin/deck-master run-state --run-dir <run_dir> --run-id <run_id>
```

## Allowed Commands

```bash
~/.deck-master/bin/deck-master suite-status --target codex --output json
~/.deck-master/bin/deck-master build status --run-dir <run_dir> --run-id <run_id>
~/.deck-master/bin/deck-master render-status --run-dir <run_dir> --run-id <run_id>
~/.deck-master/bin/deck-master import-render-result --run-dir <run_dir> --run-id <run_id> --input <render_result.json>
```

Fixture/dev-only contract smoke:

```bash
~/.deck-master/bin/deck-master render --run-dir <run_dir> --run-id <run_id> --format html --fixture-safe
```

## Output Rule

The canonical render result is `render_results/render_result.json` with
`schema_version: deck_render_result.v2`. Legacy render result paths are accepted
only as import inputs and must be normalized into the canonical path.

Production/client export requires a certified backend result. Contract-smoke or
fixture-safe outputs are internal verification materials and must stay marked
`non_client_deliverable`.


<!-- skill-os-contract:v1 -->
## Public Stage
Maps to public stage: deck-builder. This is a compatibility wrapper; prefer the public `deck-builder` skill for new runs.
