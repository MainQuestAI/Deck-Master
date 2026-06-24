---
name: deck-quality
description: Deck Master quality entry for draft, render, delivery, customer-visible safety, evidence, confidentiality, and brand gates.
triggers:
  - run deck quality gate
  - check customer visible safety
  - check delivery blockers
  - deck quality
---

# Deck Quality

Use this skill before client export or whenever a deck may contain internal
language, placeholder text, stale artifacts, or evidence issues.

## Allowed Commands

```bash
~/.deck-master/bin/deck-master quality-gate draft --run-dir <run_dir>
~/.deck-master/bin/deck-master quality-gate customer-visible-safety --run-dir <run_dir> --artifact <pptx>
~/.deck-master/bin/deck-master quality-gate delivery --run-dir <run_dir> --artifact <pptx>
~/.deck-master/bin/deck-master import-quality-findings --run-dir <run_dir> --input <findings.json>
```

## Blocking Rule

P0 findings block client export. Internal export may be used only for repair and
must stay marked degraded.


<!-- skill-os-contract:v1 -->

## Use When
Quality gates, customer-visible safety, evidence, confidentiality, and delivery blockers.

## Do Not Use
Do not use outside its lane in the Skill OS workflow. Do not treat a successful command return code as stage completion.

## First Checks
- builder handoff accepted
- render artifacts present
- quality rules loaded

## Forcing Questions
- quality.rule_conflict: 是否存在规则冲突或需人工判断项？

## Runtime Ownership
Skill OS workflow runtime; stage `deck-quality`. Stage completion is validated by the contract entry/exit validator and handoff/approval runtime, not by command return code.

## Allowed Commands
```bash
deck-master quality-gate --run-dir <run_dir>
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
Keep internal-only production notes out of customer-visible content. Never bypass the final client export approval. Obey the stage contract's transition policy.
