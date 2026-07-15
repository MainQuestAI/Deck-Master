---
name: deck-learn
description: Deck Master learning entry for delivery outcomes, reusable asset feedback, benchmark results, and workspace learning packs.
triggers:
  - record deck feedback
  - build learning pack
  - record delivery outcome
  - deck learn
---

# Deck Learn

Use this optional skill after review, delivery, or benchmark completion.

<!-- skill-os-contract:v1 -->

## Use When
Delivery outcomes, reusable asset feedback, benchmark results, and workspace learning packs.

## Do Not Use
Do not use outside its lane in the Skill OS workflow. Do not treat a successful command return code as stage completion.

## First Checks
- delivery outcome recorded
- feedback events available

## Forcing Questions
- learn.desensitization: 沉淀前是否完成脱敏？
- learn.reuse_scope: 可复用范围是什么？
- learn.win_loss_reason: 本轮胜负的核心原因是什么？

## Runtime Ownership
Skill OS workflow runtime; stage `deck-learn`. Stage completion is validated by the contract entry/exit validator and handoff/approval runtime, not by command return code.

## Allowed Commands
```bash
deck-master record-library-feedback --run-dir <run_dir> --apply
deck-master delivery record-outcome --run-dir <run_dir>
deck-master build-learning-pack --workspace <workspace>
deck-master show-learning-pack --workspace <workspace>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
workspace_learning_pack, feedback_queue

## Next Skill
(terminal)

## Stop Conditions
- desensitization_failed
- delivery_not_recorded

## Safety Rules
Keep internal-only production notes out of customer-visible content. Never bypass the final client export approval. Obey the stage contract's transition policy.
