---
name: deck-sourcing
description: Deck Master sourcing entry for deciding which pages need historical assets, new production, evidence screenshots, or project-specific reference material.
triggers:
  - source deck assets
  - find reusable slides
  - search ppt library
  - decide page sourcing
---

# Deck Sourcing

Use this skill after page tasks exist and before new page production starts.

## Allowed Commands

```bash
~/.deck-master/bin/deck-master search-library --run-dir <run_dir>
~/.deck-master/bin/deck-master import-library-selection --run-dir <run_dir> --input <selection.json>
~/.deck-master/bin/deck-master decide-sourcing --run-dir <run_dir>
~/.deck-master/bin/deck-master record-library-feedback --run-dir <run_dir> --page-task-id <page> --candidate-id <candidate> --outcome <outcome>
```

## Decision Rule

Use existing assets when they match the page claim, audience, visual pattern,
and evidence need. Send pages to production when reuse would weaken the story.


<!-- skill-os-contract:v1 -->

## Use When
Historical asset sourcing and page sourcing decisions.

## Do Not Use
Do not use outside its lane in the Skill OS workflow. Do not treat a successful command return code as stage completion.

## First Checks
- planner handoff accepted
- page tasks fresh
- sourcing roots available

## Forcing Questions
- sourcing.source_authority: 每个关键主张的来源权威性是否足够？
- sourcing.reuse_license: 复用的历史资产是否取得了使用许可？
- sourcing.freshness: 引用数据或案例是否在可接受时效内？
- sourcing.screenshot_consent: 截图或客户素材是否获得展示授权？
- sourcing.generation_strategy: 缺失资产采用检索复用还是新生产？

## Runtime Ownership
Skill OS workflow runtime; stage `deck-sourcing`. Stage completion is validated by the contract entry/exit validator and handoff/approval runtime, not by command return code.

## Allowed Commands
```bash
deck-master decide-sourcing --run-dir <run_dir>
deck-master workflow status --run-dir <run_dir>
deck-master run-state --run-dir <run_dir>
```

## Exit Artifacts
library_selection, sourcing_plan, asset_feedback

## Next Skill
deck-producer

## Stop Conditions
- blocking_question
- unresolved_permission
- missing_generation_strategy

## Safety Rules
Keep internal-only production notes out of customer-visible content. Never bypass the final client export approval. Obey the stage contract's transition policy.
