---
name: deck-brief
description: Deck Master briefing entry for turning raw materials, deep research reports, and meeting notes into customer-visible deck brief inputs.
triggers:
  - create deck brief
  - summarize deck materials
  - turn research into ppt brief
  - deck brief
---

# Deck Brief

Use this skill when the user provides source material and wants Deck Master to
extract the business problem, audience, claims, evidence, and deck intent.

## Allowed Commands

```bash
~/.deck-master/bin/deck-master import-context-pack --run-dir <run_dir> --input <context_pack.json>
~/.deck-master/bin/deck-master build-brief --run-dir <run_dir>
~/.deck-master/bin/deck-master build-claim-map --run-dir <run_dir>
```

## Boundary

Keep internal production notes out of customer-visible content. Production notes
belong in source metadata, speaker notes, or internal planning fields.


<!-- skill-os-contract:v1 -->

## Use When
Turn raw material and research into deck brief inputs.

## Do Not Use
Do not use outside its lane in the Skill OS workflow. Do not treat a successful command return code as stage completion.

## First Checks
- init handoff accepted
- context manifest available
- material inventory fresh

## Forcing Questions
- brief.decision_object: 这次沟通要让受众做出什么决策？
- brief.success_criteria: 成功标准是什么？怎么算赢？
- brief.non_negotiable_constraints: 有哪些不可谈判的约束？
- brief.forbidden_claims: 有哪些主张是明确禁用的？
- brief.evidence_gap: 当前证据存在哪些缺口？

## Runtime Ownership
Skill OS workflow runtime; stage `deck-brief`. Stage completion is validated by the contract entry/exit validator and handoff/approval runtime, not by command return code.

## Allowed Commands
```bash
deck-master build-brief --run-dir <run_dir>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
deck_brief, claim_map_seed

## Next Skill
deck-planner

## Stop Conditions
- blocking_question
- irresolvable_constraint
- fatal_evidence_gap

## Safety Rules
Keep internal-only production notes out of customer-visible content. Never bypass the final client export approval. Obey the stage contract's transition policy.
