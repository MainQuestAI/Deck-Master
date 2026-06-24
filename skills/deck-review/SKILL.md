---
name: deck-review
description: Deck Master review and delivery entry for quality gates, Review Cockpit state, findings, repair loops, export readiness, and delivery readiness. Use when the user asks whether a Deck Master run or generated deck is ready to deliver.
triggers:
  - review a deck run
  - check deck quality gates
  - check delivery readiness
  - import review findings
  - export approved page queue
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


<!-- skill-os-contract:v1 -->

## Use When
Review, repair, export readiness, and delivery checks.

## Do Not Use
Do not use outside its lane in the Skill OS workflow. Do not treat a successful command return code as stage completion.

## First Checks
- quality handoff accepted
- final artifacts present
- final readiness computable

## Forcing Questions
- review.risk_acceptance: 残留风险是否可接受？
- review.final_version: 最终交付版本是否已确定？
- review.delivery_target: 交付对象与交付方式是什么？
- review.approver: 最终审批人是谁？

## Runtime Ownership
Skill OS workflow runtime; stage `deck-review`. Stage completion is validated by the contract entry/exit validator and handoff/approval runtime, not by command return code.

## Allowed Commands
```bash
deck-master export --run-dir <run_dir>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
export_queue, final_readiness, delivery_validation

## Next Skill
client_export

## Stop Conditions
- review_rejected
- final_readiness_failed
- missing_final_approval

## Safety Rules
Keep internal-only production notes out of customer-visible content. Never bypass the final client export approval. Obey the stage contract's transition policy.
