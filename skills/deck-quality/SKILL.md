---
name: deck-quality
description: Run the relevant Deck Master quality gates on current artifacts or import quality findings.
---

# Deck Quality

<!-- skill-os-contract:v1 -->

## Use When
Quality gates, customer-visible safety, evidence, confidentiality, and delivery blockers.

## Do Not Use
For other tasks, use the task route in [deck-master](../deck-master/SKILL.md).

## First Checks
Use current run state and available results; inspect only missing or affected inputs.
- builder handoff accepted
- render artifacts present
- quality rules loaded

## Forcing Questions
Reuse confirmed answers and design decisions. Ask only for a missing decision that changes this task. Record existing authorization through the runtime when needed.

## Runtime Ownership
Deck Master stage `deck-quality`; commands preserve its artifact and approval contracts.

## Allowed Commands
```bash
deck-master quality-gate draft --run-dir <run_dir>
deck-master quality-gate customer-visible-safety --run-dir <run_dir> --artifact <pptx>
deck-master quality-gate delivery --run-dir <run_dir> --artifact <pptx>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
quality_report, customer_visible_safety_gate, delivery_gate

## Next Skill
deck-review

## Stop Conditions
- p0_finding
- p1_finding
- customer_visible_safety_blocked

## Safety Rules
Keep internal notes out of customer-visible artifacts. Reuse current validation; rerun checks affected by changes. Client export requires approval for the current version.
