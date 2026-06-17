---
name: deck-review
description: Deck Master review and delivery entry for quality gates, Review Cockpit state, findings, repair loops, export readiness, and delivery readiness. Use when the user asks whether a Deck Master run or generated deck is ready to deliver.
---

# Deck Review

Use this skill for review, repair, quality, and delivery decisions inside Deck
Master.

## First Checks

Read setup and run state before judging delivery:

```bash
~/.deck-master/bin/deck-master setup-status --include-suite --output json
~/.deck-master/bin/deck-master run-state --run-dir <run_dir> --run-id <run_id>
```

If setup or suite readiness is blocked, guide the Agent-driven setup ceremony:
explain what is missing, confirm workspace when needed, run safe setup or
repair commands, then verify status again.

## Runtime Ownership

Delivery readiness is decided by Deck Master run state. Do not mark delivery
ready while workspace, render, quality, or import gates are blocked.

## Allowed Commands

```bash
~/.deck-master/bin/deck-master quality-gate draft --run-dir <run_dir> --run-id <run_id>
~/.deck-master/bin/deck-master quality-gate render --run-dir <run_dir> --run-id <run_id> --artifact <artifact>
~/.deck-master/bin/deck-master import-quality-findings --run-dir <run_dir> --run-id <run_id> --input <findings.json>
~/.deck-master/bin/deck-master import-render-result --run-dir <run_dir> --run-id <run_id> --input <render_result.json>
~/.deck-master/bin/deck-master export --run-dir <run_dir> --run-id <run_id>
```

## Forbidden Shortcuts

- Do not judge only from a standalone PPTX, HTML, or PDF.
- Do not ignore blocking findings or stale render state.
- Do not export final delivery while Deck Master run-state blocks it.

## Output Expectations

Review output must be visible through Deck Master artifacts such as
`quality_reports/*`, `render_results/render_result.json`, Review Cockpit state,
and export queues.
