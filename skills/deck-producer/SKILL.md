---
name: deck-producer
description: Produce or revise selected Deck Master pages and import generation results.
---

# Deck Producer

<!-- skill-os-contract:v1 -->

## Use When
Generation sessions, dispatch packages, and canonical generation result import.

## Do Not Use
For other tasks, use the task route in [deck-master](../deck-master/SKILL.md).

For a selected-page edit, read [local edits](../deck-master/playbooks/local-edits.md). Preserve other pages and confirmed style; do not restart the whole-deck brief or planning interview.

## First Checks
Use current run state and available results; inspect only missing or affected inputs.
- sourcing handoff accepted
- sourcing plan fresh
- required page set known

## Forcing Questions
Reuse confirmed answers and design decisions. Ask only for a missing decision that changes this task. Record existing authorization through the runtime when needed.

## Runtime Ownership
Deck Master stage `deck-producer`; commands preserve its artifact and approval contracts.

## Allowed Commands
```bash
deck-master generation-session create --run-dir <run_dir>
deck-master generation-session status --run-dir <run_dir>
deck-master run-generation --run-dir <run_dir>
deck-master generation-session dispatch --run-dir <run_dir>
deck-master generation-session import-results --run-dir <run_dir> --input <result.json>
deck-master refresh-preview-from-generation --run-dir <run_dir>
deck-master build-preview --run-dir <run_dir>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
deck_generation_result.v2, preview_refresh

## Next Skill
deck-builder

## Stop Conditions
- blocking_question
- internal_field_leak
- missing_required_page_package

## Safety Rules
Keep internal notes out of customer-visible artifacts. Reuse current validation; rerun checks affected by changes. Client export requires approval for the current version.
