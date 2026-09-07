---
name: deck-init
description: Initialize a new Deck Master workspace and material inventory.
---

# Deck Init

<!-- skill-os-contract:v1 -->

## Use When
Project workspace initialization with material, reference, process, delivery, and metadata directories.

## Do Not Use
For other tasks, use the task route in [deck-master](../deck-master/SKILL.md).

## First Checks
Use current run state and available results; inspect only missing or affected inputs.
- workspace root exists and is writable
- raw material roots are reachable
- workspace policy available

## Forcing Questions
Reuse confirmed answers and design decisions. Ask only for a missing decision that changes this task. Record existing authorization through the runtime when needed.

## Runtime Ownership
Deck Master stage `deck-init`; commands preserve its artifact and approval contracts.

## Allowed Commands
```bash
deck-master init-project --workspace <workspace> --name <project_name>
deck-master validate-workspace --workspace <workspace>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
deck_project, material_inventory, workspace_policy, run_bindings

## Next Skill
deck-brief

## Stop Conditions
- missing_material_roots
- workspace_not_writable
- unresolvable_privacy_boundary

## Safety Rules
Keep internal notes out of customer-visible artifacts. Reuse current validation; rerun checks affected by changes. Client export requires approval for the current version.
