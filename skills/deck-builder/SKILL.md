---
name: deck-builder
description: Render standard-profile Deck Master runs and rebuild artifacts after page edits.
---

# Deck Builder

<!-- skill-os-contract:v1 -->

## Use When
Public build entry for HTML, PDF, PNG, PPTX, artifact manifest, render result, and editability metadata.

## Do Not Use
For other tasks, use the task route in [deck-master](../deck-master/SKILL.md).

For a selected-page edit, read [local edits](../deck-master/playbooks/local-edits.md). Preserve other pages and confirmed style; do not restart the whole-deck brief or planning interview.

## First Checks
Use current run state and available results; inspect only missing or affected inputs.
- producer handoff accepted
- page packages valid
- certified build backend ready

## Forcing Questions
Reuse confirmed answers and design decisions. Ask only for a missing decision that changes this task. Record existing authorization through the runtime when needed.

## Runtime Ownership
Deck Master stage `deck-builder`; commands preserve its artifact and approval contracts.

## Allowed Commands
```bash
deck-master build prepare --run-dir <run_dir>
deck-master build run --run-dir <run_dir>
deck-master build status --run-dir <run_dir>
deck-master render-status --run-dir <run_dir>
deck-master import-render-result --run-dir <run_dir> --input <render_result.json>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
build_manifest, artifact_manifest, render_result.v2, final_artifacts

## Next Skill
deck-quality

## Stop Conditions
- build_backend_unavailable
- render_failed
- preview_manifest_used_without_adapter

## Safety Rules
Keep internal notes out of customer-visible artifacts. Reuse current validation; rerun checks affected by changes. Client export requires approval for the current version.
